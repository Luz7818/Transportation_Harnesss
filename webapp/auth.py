"""本地账号与会话:replaycase/评测资产是项目核心资产,公网或多人使用时需要登录。

- 账号存储在 webapp/auth.json(首次启动自动创建,默认 admin/harness123,可用
  环境变量 ADMIN_USER / ADMIN_PASSWORD 覆盖初始值);
- 密码只存 PBKDF2-HMAC-SHA256(salt + 12 万次迭代),不落明文;历史遗留的
  单轮 SHA-256 哈希在登录校验通过后透明升级为 PBKDF2;
- 登录失败限流:同一用户名连续失败 5 次锁定 10 分钟,成功登录即清零,
  缓解公网口令暴力破解;
- 会话为 HMAC 签名令牌(载荷 = 用户名 + 过期时间,7 天有效),放在 HttpOnly Cookie 里;
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
DEFAULT_PASSWORD = os.getenv("ADMIN_PASSWORD", "harness123")

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


def load_store() -> dict:
    if AUTH_FILE.exists():
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    salt = secrets.token_hex(16)
    store = {
        "secret": secrets.token_hex(32),
        "default_credentials": True,
        "users": [{"username": DEFAULT_USER, "salt": salt,
                   "password_hash": _hash(salt, DEFAULT_PASSWORD)}],
    }
    AUTH_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    from_env = "ADMIN_PASSWORD" in os.environ
    print(f"[auth] 已初始化账号 {DEFAULT_USER} / "
          f"{'环境变量 ADMIN_PASSWORD 注入的密码' if from_env else '默认密码 harness123'}(请登录后尽快修改)")
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
