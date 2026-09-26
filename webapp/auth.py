"""本地账号与会话:replaycase/评测资产是项目核心资产,公网或多人使用时需要登录。

- 账号存储在 webapp/auth.json(首次启动自动创建,已被 .gitignore 排除):
  初始口令优先取环境变量 ADMIN_PASSWORD;未提供时用 secrets 生成随机强口令并只在控制台
  打印一次(仓库与文档里不存在任何可复述的默认口令,也就无需在说明书里写它);
- 密码只存 PBKDF2-HMAC-SHA256(salt + 12 万次迭代),不落明文;历史遗留的
  单轮 SHA-256 哈希在登录校验通过后透明升级为 PBKDF2;
- 登录失败限流:同一用户名连续失败 5 次锁定 10 分钟,成功登录即清零,
  缓解公网口令暴力破解;
- 会话为 HMAC 签名令牌(载荷 = 用户名 + 过期时间,7 天有效),网页放 HttpOnly Cookie,
  小程序/脚本无法带 Cookie,故同一枚令牌也可以 `Authorization: Bearer <令牌>` 提交,
  签发与校验都走本模块的 make_token / parse_token,不存在第二套会话格式;
- 修改密码走 /api/auth/password,改完立即用新密码重签会话。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

AUTH_FILE = Path(__file__).resolve().parent / "auth.json"
SESSION_TTL = 7 * 24 * 3600
DEFAULT_USER = os.getenv("ADMIN_USER", "admin")

# 初始口令字符集去掉易混字符(0/O、1/l/I),长度 20 → 约 116 bit 熵
_INITIAL_PASSWORD_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
INITIAL_PASSWORD_LENGTH = 20

PBKDF2_ITERATIONS = 120_000          # OWASP 推荐量级;单次校验约几十毫秒,登录场景可接受
ALGO_PBKDF2 = "pbkdf2_sha256"
ALGO_LEGACY = "sha256"               # v1.2 及之前的哈希算法,仅用于透明迁移
LOCKOUT_THRESHOLD = 5                # 连续失败次数达到阈值即锁定
LOCKOUT_SECONDS = 600                # 锁定时长(秒)

# 登录限流状态:username -> {"fails": int, "locked_until": float};进程内即可,
# 多实例部署时在最外层网关限流
_login_guard: dict[str, dict] = {}
_guard_lock = threading.Lock()


def _hash(salt: str, password: str, algo: str = ALGO_PBKDF2) -> str:
    if algo == ALGO_PBKDF2:
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                     salt.encode("utf-8"), PBKDF2_ITERATIONS)
        return f"{ALGO_PBKDF2}${PBKDF2_ITERATIONS}${digest.hex()}"
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def _verify_hash(user: dict, password: str) -> bool:
    stored = user["password_hash"]
    if stored.startswith(f"{ALGO_PBKDF2}$"):
        _, iterations, digest = stored.split("$", 2)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                        user["salt"].encode("utf-8"), int(iterations))
        return hmac.compare_digest(digest, candidate.hex())
    # 旧格式(单轮 SHA-256):校验通过后由调用方升级
    return hmac.compare_digest(stored, _hash(user["salt"], password, ALGO_LEGACY))


def _upgrade_hash(store: dict, user: dict, password: str) -> None:
    """把旧算法口令哈希就地升级为 PBKDF2 并持久化(登录成功时触发)。"""
    user["salt"] = secrets.token_hex(16)
    user["password_hash"] = _hash(user["salt"], password)
    _save(store)


def generate_initial_password() -> str:
    """随机强初始口令:仅在 auth.json 不存在且未提供 ADMIN_PASSWORD 时使用。"""
    return "".join(secrets.choice(_INITIAL_PASSWORD_ALPHABET)
                   for _ in range(INITIAL_PASSWORD_LENGTH))


def load_store() -> dict:
    if AUTH_FILE.exists():
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    password = os.getenv("ADMIN_PASSWORD") or ""
    generated = not password            # 没给初始口令 → 随机生成,绝不落回任何公开默认值
    if generated:
        password = generate_initial_password()
    salt = secrets.token_hex(16)
    store = {
        "secret": secrets.token_hex(32),
        # 随机口令只打印这一次,不是"默认口令",因此无需在登录页提醒改密;
        # ADMIN_PASSWORD 注入的口令沿用原语义(首次创建 → 提示改密)
        "default_credentials": not generated,
        "users": [{"username": DEFAULT_USER, "salt": salt,
                   "password_hash": _hash(salt, password)}],
    }
    AUTH_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    if generated:
        print(f"[auth] 已初始化账号 {DEFAULT_USER},随机生成的初始口令为 {password}"
              f"(仅此一次打印,请立即登录修改)")
    else:
        print(f"[auth] 已初始化账号 {DEFAULT_USER} / "
              f"环境变量 ADMIN_PASSWORD 注入的密码(请登录后尽快修改)")
    return store


def login_locked(username: str) -> int:
    """该用户名剩余锁定秒数;0 表示未锁定。"""
    with _guard_lock:
        state = _login_guard.get(username)
        if not state:
            return 0
        remain = state["locked_until"] - time.time()
        return max(0, int(remain))


def record_login_failure(username: str) -> None:
    with _guard_lock:
        state = _login_guard.setdefault(username, {"fails": 0, "locked_until": 0.0})
        state["fails"] += 1
        if state["fails"] >= LOCKOUT_THRESHOLD:
            state["locked_until"] = time.time() + LOCKOUT_SECONDS
            state["fails"] = 0


def record_login_success(username: str) -> None:
    with _guard_lock:
        _login_guard.pop(username, None)


def verify_password(store: dict, username: str, password: str) -> bool:
    if login_locked(username):
        return False
    for user in store["users"]:
        if hmac.compare_digest(user["username"], username):
            if _verify_hash(user, password):
                record_login_success(username)
                if not user["password_hash"].startswith(f"{ALGO_PBKDF2}$"):
                    _upgrade_hash(store, user, password)  # 旧哈希透明升级
                return True
            record_login_failure(username)
            return False
    # 用户名不存在时也消耗一次虚拟校验,避免通过响应时间探测用户名
    hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b"timing", PBKDF2_ITERATIONS)
    return False


def change_password(store: dict, username: str, old: str, new: str) -> bool:
    if not verify_password(store, username, old):
        return False
    if not (6 <= len(new) <= 64):
        raise ValueError("新密码长度需在 6~64 位之间")
    for user in store["users"]:
        if user["username"] == username:
            user["salt"] = secrets.token_hex(16)
            user["password_hash"] = _hash(user["salt"], new)
    if username == DEFAULT_USER:  # 默认账号改密后,登录页不再提示初始口令
        store["default_credentials"] = False
    _save(store)
    return True


def _save(store: dict) -> None:
    tmp = AUTH_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, AUTH_FILE)


def make_token(store: dict, username: str) -> str:
    payload = f"{username}.{int(time.time()) + SESSION_TTL}"
    raw = payload.encode("utf-8")
    sig = hmac.new(store["secret"].encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(raw).decode("ascii") + "." + sig


def token_expires_at(token: str) -> int | None:
    """会话令牌载荷里的过期时间(unix 秒);解析失败返回 None。

    只用于登录响应里告知客户端"这枚令牌何时失效",不做任何鉴权判定 ——
    鉴权一律走 parse_token 的签名 + 有效期校验。
    """
    try:
        raw = base64.urlsafe_b64decode(token.rsplit(".", 1)[0].encode("ascii"))
        return int(raw.decode("utf-8").rsplit(".", 1)[1])
    except Exception:
        return None


def parse_token(store: dict, token: str) -> str | None:
    try:
        b64, sig = token.rsplit(".", 1)
        raw = base64.urlsafe_b64decode(b64.encode("ascii"))
        expect = hmac.new(store["secret"].encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            return None
        username, expiry = raw.decode("utf-8").rsplit(".", 1)
        if int(expiry) < int(time.time()):
            return None
        return username
    except Exception:
        return None
