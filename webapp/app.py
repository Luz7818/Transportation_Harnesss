"""Web 界面后端:把 harness 的能力(分析提交 / Case 管理 / 评测看板 / 版本对比 / 一键自进化)暴露为 HTTP API。

本地启动:python webapp/app.py(默认 http://127.0.0.1:8765)
公网部署:支持环境变量配置(见 DEPLOY.md)
  HOST=0.0.0.0 PORT=8765  监听地址/端口
  AUTH_MODE=open          免登录(仅限内网演示);默认 login
  AUTH_TOKEN=xxx          设置后所有 /api/* 需要 X-API-Token 请求头(公网必开)
  CORS_ORIGINS=https://a.com,https://b.com   允许的跨域来源,默认 *
  SETTINGS_ENABLED=1      开启 /api/settings 运行时配置接口(默认关闭)

受保护的 /api/* 认可三种凭据,按此顺序判定(任一通过即放行):
  1. `X-API-Token: <AUTH_TOKEN>`     —— SDK / 脚本 / CI 等机器客户端;
  2. `Authorization: Bearer <会话令牌>` —— 小程序等带不了 Cookie 的客户端;
  3. `harness_session` Cookie         —— 网页看板(HttpOnly,登录时下发)。
会话令牌由 webapp/auth.py 的 HMAC 签名机制签发与校验,三处共用同一套,不存在第二套格式。
"""

from __future__ import annotations

import hmac
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_dotenv(path: Path) -> None:
    """极简 .env 加载(零依赖):KEY=VALUE 逐行,忽略注释;已存在的环境变量优先于文件。"""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv(ROOT / ".env")

try:
    from fastapi import FastAPI, HTTPException, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ModuleNotFoundError as exc:
    sys.exit(f"缺少依赖 {exc.name!r}:请先在当前 Python 环境执行  pip install -r requirements.txt")

from harness import activity as activity_mod
from harness import report as report_mod
from harness import storage
from harness.evolve import run_evolution
from harness.models import CheckSpec, ReplayCase
from harness.runner import ReplayRunner
from llm import runtime as llm_runtime
from llm import store as llm_store
from llm import workflows as llm_workflows
from llm.runtime import LLMError
from pipeline.versions import CHANGELOG, PIPELINES

from webapp import auth as auth_mod
from webapp import settings as settings_mod

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8765"))
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "").strip()      # 机器客户端(小程序/脚本)令牌,可选
AUTH_MODE = os.getenv("AUTH_MODE", "login")           # login(默认,需登录)| open(内网演示免登录)
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
COOKIE_NAME = "harness_session"
COOKIE_SECURE = settings_mod.flag_is_on(os.getenv("COOKIE_SECURE"))  # HTTPS 部署时设 1
# 运行时配置接口(/api/settings)总开关:默认关闭。它只在启动时读一次,
# 因此无法通过该接口本身给自己开权限;HOST 绑到非 loopback 时也不会默认开启。
SETTINGS_ENABLED = settings_mod.flag_is_on(os.getenv("SETTINGS_ENABLED"))

# 回环地址:uvicorn 直连本机时 client.host 落在这里
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
# 反向代理痕迹头:出现任意一个,就说明"对端地址"属于代理而非真实客户端
_PROXY_HINT_HEADERS = ("forwarded", "x-forwarded-for", "x-real-ip")

VALID_LEVELS = ("畅通", "基本畅通", "缓行", "拥堵", "严重拥堵", "数据缺失")

_CASE_LOCK = threading.Lock()    # 沉淀 case + 更新评测集是复合操作,整体串行化
_EVOLVE_LOCK = threading.Lock()  # 自进化循环全库读写,不允许并发执行
_AUTH_STORE = auth_mod.load_store()

app = FastAPI(title="交通分析自进化 Harness", version="1.5.0")

# allow_credentials=True 时浏览器规范禁止 Origin 为通配符 *,会直接拒绝带 Cookie 的跨域请求;
# 因此仅在显式配置了具体来源(多实例/前后端分离部署)时才开启 credentials
_allow_all_origins = CORS_ORIGINS == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*", "X-API-Token", "Authorization"],
    allow_credentials=not _allow_all_origins,
)
app.mount("/static", StaticFiles(directory=ROOT / "webapp" / "static"), name="static")


def _bearer_token(request: Request) -> str | None:
    """从 `Authorization: Bearer <令牌>` 取会话令牌(小程序带不了 Cookie,只能靠请求头)。"""
    scheme, _, value = request.headers.get("Authorization", "").partition(" ")
    value = value.strip()
    return value if scheme.lower() == "bearer" and value else None


def _session_user(request: Request) -> str | None:
    """已鉴权会话的用户名:Bearer 会话令牌与 harness_session Cookie 任一有效即可。"""
    for token in (_bearer_token(request), request.cookies.get(COOKIE_NAME)):
        if token and (username := auth_mod.parse_token(_AUTH_STORE, token)):
            return username
    return None


def _is_direct_loopback(request: Request) -> bool:
    """请求是否由本机直连发出。

    经 Nginx 反代后对端地址恒为 127.0.0.1,若只看地址就把每个公网访客当本机,
    等于没有这道门;因此带任一转发头的请求不算本机(它必然经过了代理),
    只认 TCP 对端地址,且不接受被代理改写过来源的请求 —— 这类请求一律要求已登录会话。
    """
    client = request.client
    host = ((client.host if client else "") or "").strip().strip("[]")
    if host.startswith("::ffff:"):        # IPv4-mapped IPv6(::ffff:127.0.0.1)
        host = host[len("::ffff:"):]
    if host not in _LOOPBACK_HOSTS and not host.startswith("127."):
        return False
    return not any(name in request.headers for name in _PROXY_HINT_HEADERS)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """访问控制:
    - AUTH_MODE=open:全部放行(仅限内网演示);
    - /api/auth/* 与 /api/health 始终放行(登录页与拨测需要);
    - /api/settings 交给端点自己做更严的准入判定(要区分本机直连与会话),
      不能被这里的通用 401 提前挡掉,否则本机未登录用户只会看到一个"请先登录";
    - 其余 /api/*:三种凭据按序裁决 —— X-API-Token(机器客户端)
      → Authorization: Bearer(小程序)→ 会话 Cookie(网页),任一通过即放行。
    """
    path = request.url.path
    exempt = (not path.startswith("/api/") or path.startswith("/api/auth/")
              or path in ("/api/health", "/api/settings"))
    if AUTH_MODE == "open" or exempt:
        return await call_next(request)
    # 时序安全比较:直接 == 逐字节短路,理论上可被响应时间侧信道逐位猜出令牌
    if AUTH_TOKEN and hmac.compare_digest(request.headers.get("X-API-Token", ""), AUTH_TOKEN):
        return await call_next(request)
    username = _session_user(request)
    if username:
        request.state.user = username
        return await call_next(request)
    return JSONResponse({"detail": "未登录或会话已过期"}, status_code=401)


@app.exception_handler(Exception)
async def on_unhandled(request: Request, exc: Exception):
    """兜底:任何未处理异常都以 JSON 返回,便于前端提示与日志排查。"""
    return JSONResponse(status_code=500,
                        content={"detail": f"服务器内部错误:{type(exc).__name__}: {exc}"})


class AnalyzeBody(BaseModel):
    version: str
    dataset_name: str


class CaseBody(BaseModel):
    title: str
    label: str
    dataset_name: str
    segment: str
    expected_level: str
    expected_saturation: float | None = None
    saturation_tol: float = 0.01
    notes: str = ""
    add_to_evalset: bool = True
    source: str = "网页提交"


class EvalRunBody(BaseModel):
    version: str
    evalset: str = "evalset_v1"


class EvolveBody(BaseModel):
    evalset: str = "evalset_v1"
    baseline: str = "v0"   # 基线版本:增量验证新版本时传当前最佳(如 v2)


class LoginBody(BaseModel):
    username: str
    password: str


class PasswordBody(BaseModel):
    old_password: str
    new_password: str


@app.post("/api/auth/login", tags=["auth"])
def api_login(body: LoginBody, response: Response) -> dict:
    locked = auth_mod.login_locked(body.username)
    if locked:
        raise HTTPException(429, f"失败次数过多,账号已锁定,请 {locked} 秒后重试")
    if not auth_mod.verify_password(_AUTH_STORE, body.username, body.password):
        remain = auth_mod.login_locked(body.username)
        detail = "用户名或密码错误"
        if remain:  # 本次失败恰好触发锁定,把剩余秒数一并告知
            detail = f"用户名或密码错误;连续失败过多,账号已锁定 {remain} 秒"
        raise HTTPException(401, detail)
    token = auth_mod.make_token(_AUTH_STORE, body.username)
    response.set_cookie(COOKIE_NAME, token, max_age=auth_mod.SESSION_TTL,
                        httponly=True, samesite="lax", path="/", secure=COOKIE_SECURE)
    # token 与 Set-Cookie 里那枚完全相同:带不了 Cookie 的客户端(小程序)改用它,
    # 之后每次请求发 `Authorization: Bearer <token>`;expires_at 为 unix 秒。
    return {"ok": True, "username": body.username,
            "token": token, "expires_at": auth_mod.token_expires_at(token)}


@app.post("/api/auth/logout", tags=["auth"])
def api_logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me", tags=["auth"])
def api_me(request: Request) -> dict:
    username = _session_user(request)
    if username:
        return {"username": username}
    if AUTH_MODE == "open":  # 内网演示模式:免登录,以演示身份进入工作台
        return {"username": "demo"}
    raise HTTPException(401, "未登录")


@app.post("/api/auth/password", tags=["auth"])
def api_change_password(request: Request, body: PasswordBody) -> dict:
    username = _session_user(request)
    if not username:
        raise HTTPException(401, "未登录")
    try:
        if not auth_mod.change_password(_AUTH_STORE, username, body.old_password, body.new_password):
            raise HTTPException(400, "原密码不正确")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    token = auth_mod.make_token(_AUTH_STORE, username)  # 重签会话,当前登录不中断
    response = JSONResponse({"ok": True})
    response.set_cookie(COOKIE_NAME, token, max_age=auth_mod.SESSION_TTL,
                        httponly=True, samesite="lax", path="/", secure=COOKIE_SECURE)
    return response


# ================= 运行时配置(/api/settings) =================

_SETTINGS_DISABLED_DETAIL = (
    "运行时配置接口未启用:/api/settings 能读写服务器本地的 .env(含密钥),默认关闭。"
    "确需使用请在服务启动环境里设 SETTINGS_ENABLED=1 并重启服务;"
    "开启后非本机访问仍必须携带已登录会话。"
)
_SETTINGS_REMOTE_DETAIL = (
    "/api/settings 仅允许本机直连或已登录会话访问。请二选一:"
    "① 在服务器本机打开看板(127.0.0.1);② 先调 POST /api/auth/login 取 token,"
    "再带 `Authorization: Bearer <token>` 重发。"
    "X-API-Token 机器令牌不能用于该接口(小程序等客户端同样持有它),"
    "经反向代理转发的请求也不算本机。"
)


def _settings_actor(request: Request) -> str:
    """准入判定:返回操作者标识(供审计日志),不合格抛 403。

    只认两种身份:已鉴权的**会话**(Bearer / Cookie)或本机直连。
    刻意不认 X-API-Token —— 那是与小程序共用的机器令牌,拿它就能改服务器配置,
    等于把"给自己签发任意凭据"的门槛降到了任何一个令牌持有者。
    """
    if not SETTINGS_ENABLED:
        raise HTTPException(403, _SETTINGS_DISABLED_DETAIL)
    username = _session_user(request)
    if username:
        return f"session:{username}"
    if _is_direct_loopback(request):
        return "loopback"
    raise HTTPException(403, _SETTINGS_REMOTE_DETAIL)


class SettingsBody(BaseModel):
    values: dict[str, Any]      # 键名与 .env 一致;值必须是字符串,空串表示删除该项


@app.get("/api/settings", tags=["settings"])
def api_get_settings(request: Request) -> dict:
    """配置快照:密钥一律掩码(前 2 字符***(长度)),按生效时机分成 hot_reloaded / requires_restart。"""
    _settings_actor(request)
    return settings_mod.snapshot()


@app.put("/api/settings", tags=["settings"])
def api_put_settings(request: Request, body: SettingsBody) -> dict:
    """保存配置:校验 → 备份 → 原子写 .env;热生效键立刻生效,其余重启后生效。"""
    actor = _settings_actor(request)
    try:
        changes = settings_mod.apply_updates(body.values)
    except ValueError as exc:      # 值不合法 / 未知键:未写盘,原样回 400
        raise HTTPException(400, str(exc)) from exc
    if changes["hot_reloaded"]:
        llm_runtime.reset_runtime()  # 热生效键目前全是 LLM_*:重建单例即读到新配置
    touched = sorted(set(changes["updated"]) | set(changes["removed"]))
    print(f"[settings] {actor} 保存了配置:{touched}"
          f"(需重启:{sorted(changes['requires_restart']) or '无'})")  # 只记键名,绝不记值
    return {"ok": True, **changes, "snapshot": settings_mod.snapshot()}


def _require_dataset(name: str) -> list[dict]:
    try:
        return storage.load_dataset(name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, f"未知数据集 {name!r}(可选:{[p.stem for p in storage.DATA_DIR.glob('*.json')]})") from exc


def _validate_case_body(body: CaseBody, segments: list[dict]) -> None:
    if not (1 <= len(body.title.strip()) <= 80):
        raise HTTPException(400, "标题长度需在 1~80 字符之间")
    if not (1 <= len(body.label.strip()) <= 20):
        raise HTTPException(400, "失败标签长度需在 1~20 字符之间")
    if not body.segment.strip():
        raise HTTPException(400, "必须指定路段 ID")
    if body.segment.strip() not in {s["segment_id"] for s in segments}:
        known = ", ".join(s["segment_id"] for s in segments)
        raise HTTPException(400, f"路段 {body.segment!r} 不在该数据集中(可用:{known})")
    if body.expected_level not in VALID_LEVELS:
        raise HTTPException(400, f"期望拥堵等级必须是 {'/'.join(VALID_LEVELS)}")
    if body.expected_saturation is not None and not (0 <= body.expected_saturation <= 3):
        raise HTTPException(400, "期望饱和度应在 0~3 之间")
    if not (0.0001 <= body.saturation_tol <= 0.5):
        raise HTTPException(400, "饱和度容差应在 0.0001~0.5 之间")


@app.get("/", tags=["pages"])
def index() -> FileResponse:
    return FileResponse(ROOT / "webapp" / "static" / "index.html")


@app.get("/help", tags=["pages"])
def help_center() -> FileResponse:
    """文档中心:核心概念 / 工作流 / 全量 API 参考(人读版;交互式调试见 /docs)。"""
    return FileResponse(ROOT / "webapp" / "static" / "help.html")


@app.get("/sw.js", tags=["pages"], include_in_schema=False)
def service_worker() -> FileResponse:
    """Service Worker 必须从根路径提供(SW 的作用域 = 脚本所在目录),否则无法控制页面。"""
    return FileResponse(ROOT / "webapp" / "static" / "sw.js", media_type="application/javascript")


@app.get("/api/health", tags=["metadata"])
def api_health() -> dict:
    return {
        "status": "ok",
        "app_version": app.version,
        "auth_mode": AUTH_MODE,
        "default_credentials": bool(_AUTH_STORE.get("default_credentials")),
        "versions": list(PIPELINES),
        "case_count": len(storage.load_cases()),
        "evalset_count": len(storage.list_evalsets()),
        "report_count": len(storage.list_reports()),
    }


@app.get("/api/evalsets", tags=["metadata"])
def api_evalsets() -> list[dict]:
    """评测集清单列表(含规模),供看板/客户端选择评测范围。"""
    return storage.list_evalsets()


@app.get("/api/activity", tags=["metadata"])
def api_activity(limit: int = 12) -> list[dict]:
    """最近动态:case 沉淀/评测运行/自进化/LLM 草稿的统一时间流(倒序)。"""
    return activity_mod.collect(limit, drafts=llm_store.list_drafts())


@app.get("/api/versions", tags=["metadata"])
def api_versions() -> list[dict]:
    return [{"version": v, "name": meta["name"], "changes": meta["changes"]}
            for v, meta in CHANGELOG.items()]


@app.get("/api/datasets", tags=["metadata"])
def api_datasets() -> list[dict]:
    return storage.list_datasets()


@app.get("/api/segments/{dataset}", tags=["metadata"])
def api_segments(dataset: str) -> dict:
    """返回数据集内全部路段,供前端下拉选择(免去手输路段 ID)。"""
    segments = _require_dataset(dataset)
    return {"dataset": dataset,
            "segments": [{"segment_id": s["segment_id"], "name": s["name"],
                          "volume": s.get("volume"), "speed": s.get("speed")}
                         for s in segments]}


@app.post("/api/analyze", tags=["analysis"])
def api_analyze(body: AnalyzeBody) -> dict:
    if body.version not in PIPELINES:
        raise HTTPException(404, f"未知版本 {body.version}(可选:{sorted(PIPELINES)})")
    segments = _require_dataset(body.dataset_name)
    return PIPELINES[body.version](segments)


@app.get("/api/cases", tags=["cases"])
def api_cases() -> list[dict]:
    return [c.to_dict() for c in storage.load_cases()]


@app.get("/api/cases/{case_id}", tags=["cases"])
def api_case(case_id: str) -> dict:
    """单条 replaycase 详情(含判分规则 checks)。"""
    case = storage.load_case(case_id)
    if case is None:
        raise HTTPException(404, f"case 不存在:{case_id!r}")
    return case.to_dict()


@app.delete("/api/cases/{case_id}", tags=["cases"])
def api_delete_case(case_id: str) -> dict:
    """删除误沉淀的 replaycase,并同步从所有评测集清单移除(评测集不悬空)。"""
    with _CASE_LOCK:
        deleted = storage.delete_case(case_id)
    if not deleted:
        raise HTTPException(404, f"case 不存在:{case_id!r}")
    return {"deleted": case_id}


class BatchDeleteBody(BaseModel):
    ids: list[str]


@app.post("/api/cases/batch-delete", tags=["cases"])
def api_batch_delete_cases(body: BatchDeleteBody) -> dict:
    """批量删除 replaycase(单锁内逐个删除并同步评测集清单);单次上限 200 条。"""
    deleted, missing = [], []
    with _CASE_LOCK:
        for cid in body.ids[:200]:
            if storage.delete_case(cid):
                deleted.append(cid)
            else:
                missing.append(cid)
    return {"deleted": deleted, "missing": missing}


def _rel_to_root(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:  # 数据目录被挂载到项目根之外时,退化为绝对路径
        return str(path)


@app.post("/api/cases", tags=["cases"])
def api_create_case(body: CaseBody) -> dict:
    """把一条线上反馈沉淀为 replaycase,并可立即加入当前评测集——反馈到评测集的最短路径。"""
    return _create_case_from_body(body)


def _create_case_from_body(body: CaseBody) -> dict:
    segments = _require_dataset(body.dataset_name)
    _validate_case_body(body, segments)
    checks = [CheckSpec(type="classify", segment=body.segment.strip(), expected=body.expected_level)]
    if body.expected_saturation is not None:
        checks.append(CheckSpec(type="metric", segment=body.segment.strip(), field="saturation",
                                expected=body.expected_saturation, tol=body.saturation_tol))
    with _CASE_LOCK:  # 沉淀与"加入评测集"必须原子,避免并发生成重复 case_id
        numbers = [int(m.group(1)) for c in storage.load_cases()
                   if (m := re.fullmatch(r"rc-(\d+)", c.case_id))]
        case = ReplayCase(
            case_id=f"rc-{max(numbers, default=0) + 1:04d}", title=body.title.strip(),
            label=body.label.strip(), dataset_name=body.dataset_name, checks=checks,
            source=(body.source or "网页提交")[:20], notes=body.notes.strip(),
        )
        path = storage.save_case(case)
        added = storage.add_case_to_evalset(case.case_id) if body.add_to_evalset else False
    return {"saved": _rel_to_root(path), "added_to_evalset": added, "case": case.to_dict()}


# ================= LLM 智能层(详见 docs/LLM.md) =================

class DraftBody(BaseModel):
    complaint: str
    dataset_name: str
    segment_id: str | None = None


class DraftConfirmBody(BaseModel):
    title: str | None = None
    label: str | None = None
    expected_level: str | None = None
    expected_saturation: float | None = None
    notes: str = ""


class DiagnoseBody(BaseModel):
    version: str = "v2"
    evalset: str = "evalset_v1"


@app.get("/api/llm/status", tags=["llm"])
def api_llm_status() -> dict:
    """LLM Runtime 状态:供应方(mock/真实端点)、模型、缓存与最近调用审计。"""
    return llm_runtime.status()


@app.post("/api/llm/drafts", tags=["llm"])
def api_llm_draft(body: DraftBody) -> dict:
    """坏例沉淀助手:反馈原文 → 结构化 replaycase 草稿(待人工确认,不直接入库)。"""
    try:
        return llm_workflows.draft_replaycase(body.complaint, body.dataset_name, body.segment_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, f"数据集不存在:{body.dataset_name!r}") from exc
    except LLMError as exc:
        raise HTTPException(502, f"LLM 调用失败:{exc}") from exc


@app.get("/api/llm/drafts", tags=["llm"])
def api_llm_drafts() -> list[dict]:
    return llm_store.list_drafts()


@app.delete("/api/llm/drafts/{draft_id}", tags=["llm"])
def api_llm_discard(draft_id: str) -> dict:
    if not llm_store.delete_draft(draft_id):
        raise HTTPException(404, f"草稿不存在:{draft_id!r}")
    return {"deleted": draft_id}


@app.post("/api/llm/drafts/{draft_id}/confirm", tags=["llm"])
def api_llm_confirm(draft_id: str, body: DraftConfirmBody) -> dict:
    """人工确认草稿 → 走与手工沉淀完全相同的校验/落盘路径(Human-in-the-loop)。"""
    draft = llm_store.load_draft(draft_id)
    if draft is None:
        raise HTTPException(404, f"草稿不存在:{draft_id!r}")
    if draft["status"] != "pending":
        raise HTTPException(409, f"草稿已处理(当前状态:{draft['status']})")
    provided = body.model_fields_set
    case_body = CaseBody(
        title=(body.title if "title" in provided and body.title else draft["title"]),
        label=(body.label if "label" in provided and body.label else draft["label"]),
        dataset_name=draft["dataset_name"],
        segment=draft["segment_id"] or "",
        expected_level=(body.expected_level if "expected_level" in provided and body.expected_level
                        else draft["expected_level"]),
        expected_saturation=(body.expected_saturation if "expected_saturation" in provided
                             else draft["expected_saturation"]),
        notes=body.notes or draft["complaint"][:200],
        add_to_evalset=True,
        source="LLM 草稿·人工确认",
    )
    result = _create_case_from_body(case_body)  # 复用与手工沉淀完全相同的校验与落盘
    draft["status"] = "confirmed"
    draft["confirmed_case_id"] = result["case"]["case_id"]
    llm_store.save_draft(draft)
    return {"saved": result["saved"], "added_to_evalset": result["added_to_evalset"],
            "case": result["case"], "draft_id": draft_id}


@app.post("/api/llm/diagnose", tags=["llm"])
def api_llm_diagnose(body: DiagnoseBody) -> dict:
    """失败诊断(分析者 + 评审者双角色):输出分标签根因与迭代建议,仅供参考。"""
    try:
        return llm_workflows.diagnose_failures(body.version, body.evalset)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(502, f"LLM 调用失败:{exc}") from exc


def _load_evalset_or_404(name: str) -> tuple[dict, list]:
    try:
        return storage.load_evalset(name), storage.load_evalset_cases(name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        known = ", ".join(e["evalset_id"] for e in storage.list_evalsets())
        raise HTTPException(404, f"评测集不存在 {name!r}(可选:{known})") from exc
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/eval/run", tags=["eval"])
def api_eval_run(body: EvalRunBody) -> dict:
    """对指定版本跑一遍指定评测集,归档 JSON 报告并返回完整结果。"""
    if body.version not in PIPELINES:
        raise HTTPException(404, f"未知版本 {body.version}(可选:{sorted(PIPELINES)})")
    evalset, cases = _load_evalset_or_404(body.evalset)
    er = ReplayRunner().run_evalset(body.version, PIPELINES[body.version], evalset, cases)
    payload = report_mod.build_payload(er, CHANGELOG)
    path = storage.save_report(body.version, payload)
    payload["report_id"] = path.stem
    return payload


@app.post("/api/evolve/run", tags=["eval"])
def api_evolve_run(body: EvolveBody | None = None) -> dict:
    """一键自进化:基线 → 逐登记版本验证(提升且无回归)→ 归档报告,返回逐轮摘要。

    请求体可省略(兼容旧客户端);baseline 传当前最佳版本即可增量验证新登记的版本。
    """
    evalset_name = body.evalset if body else "evalset_v1"
    baseline_version = body.baseline if body else "v0"
    if baseline_version not in PIPELINES:
        raise HTTPException(404, f"未知基线版本 {baseline_version!r}(可选:{sorted(PIPELINES)})")
    _load_evalset_or_404(evalset_name)  # 先校验,避免锁内才发现参数错误
    if not _EVOLVE_LOCK.acquire(blocking=False):
        raise HTTPException(409, "自进化循环正在运行中,请稍后再试")
    try:
        return run_evolution(evalset_name, baseline_version)
    finally:
        _EVOLVE_LOCK.release()


@app.get("/api/reports", tags=["reports"])
def api_reports() -> list[dict]:
    return storage.list_reports()


@app.get("/api/evolutions", tags=["reports"])
def api_evolutions() -> list[dict]:
    """自进化运行记录(时间倒序):看板时间线回放每次迭代的得分轨迹。"""
    return storage.list_evolutions()


@app.get("/api/evolutions/{evolution_id}", tags=["reports"])
def api_evolution(evolution_id: str) -> dict:
    try:
        return storage.load_evolution(evolution_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, f"进化记录不存在 {evolution_id!r}") from exc


@app.get("/api/reports/{report_id}", tags=["reports"])
def api_report(report_id: str) -> dict:
    try:
        return storage.load_report(report_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, f"报告不存在 {report_id!r}") from exc


def _pair_check_diffs(ra: dict, rb: dict) -> list[dict]:
    """checks 级差分:同一 case 在两份报告中的判分明细逐条配对(按 index,同一 case
    的 checks 顺序由其定义决定,两轮重放顺序一致)。只返回有变化的条目。"""
    ca, cb = ra.get("checks") or [], rb.get("checks") or []
    out = []
    for i in range(max(len(ca), len(cb))):
        a = ca[i] if i < len(ca) else None
        b = cb[i] if i < len(cb) else None
        if a is None or b is None:
            status = "added" if b else "removed"
        else:
            a_pass, b_pass = bool(a.get("passed")), bool(b.get("passed"))
            if a_pass and b_pass:
                continue  # 无变化
            if not a_pass and b_pass:
                status = "fixed"
            elif a_pass and not b_pass:
                status = "regressed"
            elif a.get("actual") == b.get("actual"):
                status = "both_failed"
            else:
                status = "changed"
        src = b or a
        out.append({
            "type": src.get("type"), "target": src.get("target"),
            "expected": src.get("expected"), "status": status,
            "a_detail": a and a.get("detail"), "b_detail": b and b.get("detail"),
        })
    return out


@app.get("/api/compare", tags=["reports"])
def api_compare(a: str, b: str) -> dict:
    try:
        pa, pb = storage.load_report(a), storage.load_report(b)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, f"报告不存在:{exc}") from exc
    ra = {r["case_id"]: r for r in pa["results"]}
    rb = {r["case_id"]: r for r in pb["results"]}
    rows = [{
        "case_id": cid,
        "title": rb[cid]["title"] if cid in rb else ra[cid]["title"],
        "label": rb[cid]["label"] if cid in rb else ra[cid]["label"],
        "a_passed": ra[cid]["passed"] if cid in ra else None,
        "b_passed": rb[cid]["passed"] if cid in rb else None,
        "a_score": ra[cid]["score"] if cid in ra else None,
        "b_score": rb[cid]["score"] if cid in rb else None,
        "check_diffs": (_pair_check_diffs(ra[cid], rb[cid])
                        if cid in ra and cid in rb else []),
    } for cid in sorted(set(ra) | set(rb))]
    return {
        "a": {"report_id": a, "version": pa["version"], "accuracy": pa["accuracy"]},
        "b": {"report_id": b, "version": pb["version"], "accuracy": pb["accuracy"]},
        "newly_passed": [cid for cid in rb if cid in ra and rb[cid]["passed"] and not ra[cid]["passed"]],
        "regressed": [cid for cid in rb if cid in ra and not rb[cid]["passed"] and ra[cid]["passed"]],
        "rows": rows,
    }


if __name__ == "__main__":
    import uvicorn

    banner = f"交通分析自进化 Harness -> http://{HOST}:{PORT}(鉴权模式:{AUTH_MODE})"
    if AUTH_TOKEN:
        banner += ";机器客户端可用 X-API-Token 访问"
    banner += (";运行时配置接口 /api/settings 已启用(仅本机直连或已登录会话)"
               if SETTINGS_ENABLED else ";/api/settings 未启用(设 SETTINGS_ENABLED=1 开启)")
    print(banner)
    uvicorn.run(app, host=HOST, port=PORT)
