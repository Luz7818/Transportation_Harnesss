"""运行时配置(.env)读写:Web 看板「系统设置」面板背后的唯一写入通道。

约定(与 webapp/app.py 的 `_load_dotenv` 解析格式严格一致):

- 只操作项目根的 `.env`(已 gitignored,永不入库);逐行 `KEY=VALUE`,
  注释、空行与本模块不认识的键**原样保留**,改哪几行只动哪几行;
- 写盘 = 临时文件 + `os.replace` 原子替换;替换前把旧文件备份到 `backups/`(同样 gitignored);
- 键的元数据集中在 `SETTING_SPECS`:是否密钥(响应里一律掩码)、是否启动期才生效
  (改完必须重启进程)、说明与示例 —— 接口据此把结果分成 `hot_reloaded` / `requires_restart`;
- 值写入前统一校验:去首尾空白、拒绝内嵌换行与控制字符(防配置注入)、按键逐个做格式校验;
- 本模块只负责「读什么 / 怎么写 / 值合不合法」;**谁能访问由 webapp/app.py 的准入判定把关**
  (默认关闭 + 仅本机或已登录会话),因此这里不出现任何 HTTP/鉴权代码。
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
BACKUP_DIR = ROOT / "backups"
BACKUP_KEEP = 20                    # .env 备份只保留最近 N 份

# 写文件互斥锁:同步端点跑在线程池里,并发写必须串行化(与 harness.storage 同一套做法)
_WRITE_LOCK = threading.Lock()

_TRUE_WORDS = ("1", "true", "yes", "on")
_FALSE_WORDS = ("0", "false", "no", "off")
_BOOL_KEYS = ("SETTINGS_ENABLED", "COOKIE_SECURE")   # 取值只能是布尔字面量的键
_BOOL_WORDS = _TRUE_WORDS + _FALSE_WORDS
_MAX_VALUE_LENGTH = 512             # 配置值是单行文本,超长一律视为误输入或注入
_ORIGIN_RE = re.compile(r"^(\*|https?://[^\s,]+)$")


@dataclass(frozen=True)
class SettingSpec:
    """一个配置项的元数据:接口输出与写入校验都由它驱动。"""

    key: str
    description: str
    default: str = ""
    secret: bool = False            # 密钥:响应里掩码,永不回显明文
    restart_required: bool = False  # 启动期才生效(进程只在启动时读一次)
    example: str = ""               # 占位示例(绝不放真实值)


# 顺序即看板展示顺序;分两组:服务/鉴权(多为启动期生效)→ LLM 智能层(全部热生效)
SETTING_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec("HOST", "监听地址;公网部署填 0.0.0.0", default="127.0.0.1",
                restart_required=True, example="0.0.0.0"),
    SettingSpec("PORT", "监听端口", default="8765", restart_required=True, example="8765"),
    SettingSpec("AUTH_MODE", "login(浏览器需登录)| open(免登录,仅限内网演示)",
                default="login", restart_required=True, example="login"),
    SettingSpec("SETTINGS_ENABLED", "运行时配置接口总开关;默认关闭,开启后非本机访问仍需登录",
                default="0", restart_required=True, example="1"),
    SettingSpec("COOKIE_SECURE", "设 1 时会话 Cookie 只经 HTTPS 回传(HTTPS 部署建议开启)",
                default="0", restart_required=True, example="1"),
    SettingSpec("AUTH_TOKEN", "机器客户端令牌(X-API-Token,小程序/脚本共用)"
                             ";请填长随机串,留空表示不启用",
                secret=True, restart_required=True,
                example="python -c \"import secrets;print(secrets.token_urlsafe(32))\""),
    SettingSpec("CORS_ORIGINS", "允许的跨域来源,逗号分隔;配置具体来源才会启用带 Cookie 的跨域凭证",
                default="*", restart_required=True, example="https://your-frontend.example.com"),
    SettingSpec("ADMIN_USER", "初始管理员用户名(仅首次创建 auth.json 时生效)",
                default="admin", restart_required=True),
    SettingSpec("ADMIN_PASSWORD", "初始管理员口令(仅首次创建 auth.json 时生效;"
                                 "日常改密请用界面,改完即时生效)",
                secret=True, restart_required=True),
    SettingSpec("LLM_BASE_URL", "OpenAI 兼容端点,如 https://api.deepseek.com/v1",
                restart_required=False, example="https://api.example.com/v1"),
    SettingSpec("LLM_API_KEY", "模型密钥;留空则整条 LLM 链路自动降级为离线确定性 Mock",
                secret=True, example="sk-…"),
    SettingSpec("LLM_MODEL", "模型名", default="gpt-4o-mini", example="deepseek-chat"),
    SettingSpec("LLM_EXTRA_BODY", "可选 JSON 对象,原样并入请求体(如关闭思考模式)",
                example='{"enable_thinking": false}'),
)

SPECS_BY_KEY: dict[str, SettingSpec] = {spec.key: spec for spec in SETTING_SPECS}


def flag_is_on(raw: str | None) -> bool:
    """布尔型环境变量的统一解析:1/true/yes/on(忽略大小写与空白)视为开。"""
    return (raw or "").strip().lower() in _TRUE_WORDS


def mask_secret(value: str) -> str:
    """密钥掩码:只回「前 2 字符***(长度)」;空串表示未配置。"""
    if not value:
        return ""
    return f"{value[:2]}***({len(value)})"


def read_env_file() -> dict[str, str]:
    """解析 .env 为键值(同名键取最后一次);文件不存在返回空 dict。"""
    if not ENV_FILE.is_file():
        return {}
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _line_key(line: str) -> str | None:
    """取出一行 .env 的键;注释/空行/非法行返回 None(与 app.py 的解析口径一致)。"""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    return stripped.partition("=")[0].strip()


def _live_value(spec: SettingSpec, file_values: dict[str, str]) -> str:
    """当前生效值:进程环境变量优先(启动时 .env 已并入),其次 .env,最后默认值。"""
    env = os.environ.get(spec.key)
    if env is not None:
        return env
    return file_values.get(spec.key, spec.default)


def _source_of(spec: SettingSpec, file_values: dict[str, str]) -> str:
    """取值来源:env(进程环境变量)/ file(.env)/ default(都没配,用内置默认值)。"""
    if os.environ.get(spec.key) is not None:
        return "env"
    if spec.key in file_values:
        return "file"
    return "default"


def _entry(spec: SettingSpec, file_values: dict[str, str]) -> dict:
    live = _live_value(spec, file_values)
    return {
        "key": spec.key,
        "set": bool(live),
        "value": mask_secret(live) if spec.secret else live,
        "secret": spec.secret,
        "restart_required": spec.restart_required,
        "source": _source_of(spec, file_values),
        "default": mask_secret(spec.default) if spec.secret else spec.default,
        "example": spec.example,
        "description": spec.description,
    }


def snapshot() -> dict:
    """配置快照:按生效时机分成 hot_reloaded / requires_restart 两组,密钥一律掩码。"""
    file_values = read_env_file()
    groups: dict[str, list[dict]] = {"hot_reloaded": [], "requires_restart": []}
    restart_pending: list[str] = []
    for spec in SETTING_SPECS:
        entry = _entry(spec, file_values)
        groups["requires_restart" if spec.restart_required else "hot_reloaded"].append(entry)
        # .env 已改、进程尚未读到 → 重启后才生效(只在启动期读取的键才可能落在这里)
        if (spec.restart_required and spec.key in file_values
                and file_values[spec.key] != os.environ.get(spec.key)):
            restart_pending.append(spec.key)
    return {
        "env_file": str(ENV_FILE.relative_to(ROOT)) if ENV_FILE.is_relative_to(ROOT) else str(ENV_FILE),
        "env_file_exists": ENV_FILE.is_file(),
        "secrets_masked": True,
        "hot_reloaded": groups["hot_reloaded"],
        "requires_restart": groups["requires_restart"],
        "restart_pending_keys": restart_pending,
        "note": ("hot_reloaded 里的键保存后立即生效;"
                 "requires_restart 里的键只在服务启动时读取,已写入 .env,"
                 "必须重启进程才生效(AUTH_TOKEN / ADMIN_PASSWORD / CORS_ORIGINS 等)。"
                 "密钥值只回掩码,界面不要回填。"),
    }


def _validate_value(spec: SettingSpec, value: str) -> None:
    """按键逐个做格式校验(value 已去空白、非空);非法即抛 ValueError。"""
    key = spec.key
    if len(value) > _MAX_VALUE_LENGTH:
        raise ValueError(f"{key} 的值过长(上限 {_MAX_VALUE_LENGTH} 字符)")
    if key == "AUTH_MODE" and value not in ("login", "open"):
        raise ValueError("AUTH_MODE 只能是 login 或 open")
    if key in _BOOL_KEYS and value.lower() not in _BOOL_WORDS:
        raise ValueError(f"{key} 只能是 {' / '.join(_BOOL_WORDS)}")
    if key == "HOST" and re.search(r"[\s/]", value):
        raise ValueError("HOST 只能是 IP 或主机名,不要带协议头/端口/空格")
    if key == "PORT" and not (value.isdigit() and 1 <= int(value) <= 65535):
        raise ValueError("PORT 必须是 1~65535 的整数")
    if key == "CORS_ORIGINS":
        origins = [o.strip() for o in value.split(",") if o.strip()]
        bad = [o for o in origins if not _ORIGIN_RE.fullmatch(o)]
        if bad:
            raise ValueError(f"CORS_ORIGINS 含非法来源 {bad}(需以 http:// 或 https:// 开头,或 *)")
    if key == "LLM_EXTRA_BODY":
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM_EXTRA_BODY 不是合法 JSON:{exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("LLM_EXTRA_BODY 必须是 JSON 对象")
    if key == "ADMIN_PASSWORD" and not (6 <= len(value) <= 64):
        raise ValueError("ADMIN_PASSWORD 长度需在 6~64 位之间")
    if key == "AUTH_TOKEN" and len(value) < 16:
        raise ValueError("AUTH_TOKEN 太短,起不到保护的作用(建议 ≥ 32 字符随机串)")


def clean_updates(values: dict[str, object]) -> dict[str, str]:
    """把请求体整理成「键 → 待写入值」;空串表示删除该项。非法即抛 ValueError(此时尚未写盘)。"""
    if not isinstance(values, dict) or not values:
        raise ValueError('values 必须是非空对象,形如 {"LLM_MODEL": "deepseek-chat"}')
    updates: dict[str, str] = {}
    for key, raw in values.items():
        spec = SPECS_BY_KEY.get(str(key))
        if spec is None:
            raise ValueError(f"未知配置项 {key!r};可配置的键:{', '.join(SPECS_BY_KEY)}")
        if not isinstance(raw, str):
            raise ValueError(f"{spec.key} 的值必须是字符串(空串表示删除该项)")
        if "\r" in raw or "\n" in raw:
            raise ValueError(f"{spec.key} 的值不能包含换行 —— .env 是逐行格式,换行可用于注入配置")
        value = raw.strip()
        if any(ord(ch) < 32 for ch in value):
            raise ValueError(f"{spec.key} 的值不能包含控制字符")
        if value:
            _validate_value(spec, value)
        updates[spec.key] = value
    return updates


def _prune_backups() -> None:
    backups = sorted(BACKUP_DIR.glob("env.*.bak"), key=lambda p: p.name)
    for stale in backups[:-BACKUP_KEEP]:
        stale.unlink(missing_ok=True)


def _backup_env_file() -> None:
    """覆盖前留一份旧 .env;文件名按时间戳,同秒冲突再追加序号。"""
    if not ENV_FILE.is_file():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"env.{time.strftime('%Y%m%d_%H%M%S')}.bak"
    seq = 1
    while target.exists():
        target = target.with_name(target.name + f".{seq}")
        seq += 1
    shutil.copy2(ENV_FILE, target)
    _prune_backups()


def _restrict_to_owner(path: Path) -> None:
    """POSIX 下把密钥文件收紧为仅属主可读写;Windows 的 ACL 语义不同,跳过。"""
    if os.name != "posix":
        return
    with contextlib.suppress(OSError):  # 收紧失败不应阻断保存(例如只读挂载点)
        os.chmod(path, 0o600)


def _compose_env(lines: list[str], updates: dict[str, str]) -> list[str]:
    """改写已有键所在行(重复行合并为一条),新键追加到末尾;其余行原样保留。"""
    out: list[str] = []
    written: set[str] = set()
    for line in lines:
        key = _line_key(line)
        if key is None or key not in updates:
            out.append(line)
            continue
        if key in written:      # 同名重复行:只保留改写后的第一条,避免后写覆盖新值
            continue
        written.add(key)
        if updates[key]:        # 空值 = 删除该项,整行不再输出
            out.append(f"{key}={updates[key]}")
    for key, value in updates.items():
        if value and key not in written:
            out.append(f"{key}={value}")
    return out


def _current_lines() -> list[str]:
    if not ENV_FILE.is_file():
        return []
    return ENV_FILE.read_text(encoding="utf-8").splitlines()


def write_env_file(updates: dict[str, str]) -> None:
    """原子写入 .env(写前备份);updates 的值须先经 clean_updates 校验。"""
    with _WRITE_LOCK:   # 读-改-写整体串行,并发保存不会互相覆盖
        out = _compose_env(_current_lines(), updates)
        _backup_env_file()
        tmp = ENV_FILE.with_name(ENV_FILE.name + ".tmp")
        tmp.write_text("\n".join(out) + ("\n" if out else ""),
                       encoding="utf-8", newline="\n")
        _restrict_to_owner(tmp)
        os.replace(tmp, ENV_FILE)


def apply_updates(values: dict[str, object]) -> dict:
    """保存配置:校验 → 备份 → 原子写 .env → 仅对热生效键同步进程环境。

    启动期才生效的键**不会**改动本进程的 os.environ:这正是"重启才生效"的实现语义,
    也意味着不可能通过本接口在线换掉正在生效的 AUTH_TOKEN / 管理口令。
    """
    updates = clean_updates(values)
    write_env_file(updates)
    result: dict[str, list[str]] = {"updated": [], "removed": [],
                                    "hot_reloaded": [], "requires_restart": []}
    for key, value in updates.items():
        spec = SPECS_BY_KEY[key]
        result["updated" if value else "removed"].append(key)
        if spec.restart_required:
            result["requires_restart"].append(key)
            continue
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
        result["hot_reloaded"].append(key)
    return {name: sorted(keys) for name, keys in result.items()}
