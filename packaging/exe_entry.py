"""单文件 exe 启动器:默认双击 = 独立桌面窗口(WebView2 渲染看板);--server = 无头服务。

GUI 模式(默认):准备便携数据家目录 → 播种初始资产 → uvicorn 守护线程 →
健康就绪后开 pywebview 窗口,关窗即优雅停机;重复启动探测到本程序已在跑时弹
原生提示,不在原进程上叠加;致命错误走原生 MessageBox(无黑窗)。
--server 模式:与源码 python webapp/app.py 行为一致(阻塞 uvicorn,报错黑窗),
从终端启动时接管父控制台,banner 与日志直接可见。

数据家目录约定:
- exe 旁 harness-home/(便携,首选;U 盘/桌面场景数据随 exe 走);
- exe 所在位置不可写(如 Program Files)时回退 %LOCALAPPDATA%/TransportationHarness;
- 环境变量 HARNESS_HOME 显式指定时最优先(webapp/app.py 的 harness.paths 同读该变量)。
播种只在目标缺失时进行 —— 升级 exe、重启都绝不覆盖用户已有数据;删除 harness-home
即完整重置。源码模式请直接 python webapp/app.py,本文件自动透传,不做任何包装。
"""

from __future__ import annotations

import contextlib
import io
import json
import multiprocessing
import os
import shutil
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

# 首启播种清单(exe 内置只读资产 → 数据家目录,缺了才复制,绝不覆盖)
_SEED_DIRS = ("cases", "evalsets", "reports", "llm_cache", "pipeline/data", "webapp/static")
_SEED_FILES = (".env.example",)      # 复制为 .env:全是注释模板,不含任何会改变行为的实际值
_LOG_NAME = "exe.log"
_LOG_MAX_BYTES = 5 * 1024 * 1024     # 日志超限清空重来:它只服务排障,不承担历史归档
_WINDOW_TITLE = "交通分析自进化 Harness"
_HEALTH_WAIT_SECONDS = 10            # 等 uvicorn 就绪的上限(首启解包+播种在秒级,足够)
_ATTACH_PARENT_PROCESS = -11         # kernel32 AttachConsole 的标准参数

# 供 __main__ 选择报错方式(MessageBox 或黑窗);main() 内赋值
_log_path: Path | None = None
_gui_mode = "--server" not in sys.argv

# 健康探测强制直连:本机系统代理可能拦截回环请求(实测会),探测必须绕开它
_direct_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _bundle_dir() -> Path:
    """PyInstaller onefile 的解包目录(只读);源码直跑时为本文件所在目录。"""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _home_dir() -> Path:
    """数据家目录:优先 HARNESS_HOME → exe 旁 harness-home → %LOCALAPPDATA% 兜底。"""
    override = os.environ.get("HARNESS_HOME")
    if override:
        return Path(override).expanduser().resolve()
    base = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[1])
    home = base / "harness-home"
    try:
        home.mkdir(parents=True, exist_ok=True)
        probe = home / ".write-probe"   # mkdir 成功不代表可写(ACL/只读挂载),落一枚探针确认
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        home = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "TransportationHarness"
        home.mkdir(parents=True, exist_ok=True)
    return home


def _seed(bundle: Path, home: Path) -> None:
    """首次播种:内置资产缺了才复制,已存在的目录/文件一律不动。"""
    for rel in _SEED_DIRS:
        src, dst = bundle / rel, home / rel
        if src.is_dir() and not dst.exists():
            shutil.copytree(src, dst)
    for rel in _SEED_FILES:
        src, dst = bundle / rel, home / rel
        if src.is_file() and not dst.exists():
            shutil.copy2(src, dst)
    env_src = bundle / ".env.example"
    if env_src.is_file() and not (home / ".env").exists():
        shutil.copy2(env_src, home / ".env")


def _open_log(home: Path) -> Path:
    """stdout/stderr 落盘:窗口/无头模式下 uvicorn 日志与运行期告警全写这里。"""
    global _log_path
    log = home / _LOG_NAME
    with contextlib.suppress(OSError):
        if log.exists() and log.stat().st_size > _LOG_MAX_BYTES:
            log.unlink()
    # 进程级日志流:随进程存活直到退出,不能用 with 关闭(否则后续 print 全部失效)
    stream = open(log, "a", buffering=1, encoding="utf-8", errors="replace")  # noqa: SIM115
    sys.stdout = sys.stderr = stream
    _log_path = log
    return log


def _log_tail(lines: int = 12) -> str:
    """取运行日志末尾若干行:uvicorn 端口占用等错误只进日志不抛消息串,报错须带上它。"""
    if _log_path is None or not _log_path.is_file():
        return ""
    try:
        text = _log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    tail = "\n".join(text.splitlines()[-lines:]).strip()
    return f"---- 运行日志末尾({_log_path.name}) ----\n{tail}" if tail else ""


def _error_console(title: str, detail: str) -> None:
    """无头模式的报错:分配控制台打印完整错误,按回车后退出(正常路径绝不弹窗)。

    windowed 模式的进程原本没有控制台,AllocConsole 现场开一个;已有控制台
    (如源码直跑)则沿用现有 stdout。输出统一 UTF-8,避免中文乱码。
    """
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        if kernel32.AllocConsole():
            kernel32.SetConsoleOutputCP(65001)
            # 控制台流同样随进程存活,不能用 with 包住
            sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)  # noqa: SIM115
            sys.stderr = sys.stdout
            sys.stdin = open("CONIN$", encoding="utf-8", errors="replace")  # noqa: SIM115
    print("=" * 64)
    print(f"启动失败:{title}")
    print("=" * 64)
    print(detail.rstrip())
    tail = _log_tail()
    if tail:
        print(tail)
    print("\n按回车键关闭窗口…")
    with contextlib.suppress(Exception):
        input()


def _messagebox(title: str, detail: str) -> None:
    """GUI 模式的报错/提示:原生 MessageBox,无黑窗、无需 WebView2。"""
    if os.name != "nt":
        print(f"{title}: {detail.rstrip()}", file=sys.stderr)
        return
    import ctypes

    ctypes.windll.user32.MessageBoxW(0, detail.rstrip(), f"{_WINDOW_TITLE} - {title}", 0x10)


def _fatal(title: str, detail: str) -> None:
    """按启动模式报告致命错误:GUI=MessageBox;无头=控制台黑窗。"""
    if _gui_mode:
        tail = _log_tail()
        _messagebox(title, detail.rstrip() + (f"\n\n{tail}" if tail else ""))
    else:
        _error_console(title, detail)


def _attach_parent_console() -> bool:
    """无头模式从终端启动时接管父控制台(windowed exe 默认不连终端,打印不可见)。

    已有控制台或接管失败返回 False(双击启动的场景),调用方退回日志落盘。
    """
    if os.name != "nt":
        return False
    import ctypes

    kernel32 = ctypes.windll.kernel32
    if kernel32.GetConsoleWindow():
        return True
    if not kernel32.AttachConsole(_ATTACH_PARENT_PROCESS):
        return False
    # 控制台流随进程存活,不能用 with 包住
    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)  # noqa: SIM115
    sys.stderr = sys.stdout
    return True


def _window_url(host: str, port: int) -> str:
    """窗口/探测用的访问地址:0.0.0.0 与回环一律走 127.0.0.1,其余按 HOST 直连。"""
    if host in ("0.0.0.0", "::", "", "127.0.0.1", "localhost", "::1"):
        return f"http://127.0.0.1:{port}"
    return f"http://{host}:{port}"


def _probe_health(base_url: str) -> dict | None:
    """强制直连探测 /api/health:应答含 app_version 才认定是本程序,否则 None。"""
    try:
        with _direct_opener.open(base_url + "/api/health", timeout=2) as resp:
            payload = json.loads(resp.read())
    except Exception:
        return None
    return payload if isinstance(payload, dict) and "app_version" in payload else None


def _wait_healthy(base_url: str, worker: threading.Thread) -> bool:
    """轮询等 uvicorn 就绪;服务线程中途死亡立即判负(错误详情在线程异常里)。"""
    deadline = time.monotonic() + _HEALTH_WAIT_SECONDS
    while time.monotonic() < deadline:
        if not worker.is_alive():
            return False
        if _probe_health(base_url) is not None:
            return True
        time.sleep(0.25)
    return False


def _import_app() -> tuple[object, str]:
    """导入 webapp.app 并捕获 import 期输出:首启时随机初始口令只在此刻打印一次,
    控制台不可见(窗口模式),必须落盘才找得回来。返回 (模块, 捕获文本)。"""
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        import webapp.app as webapp_app
    text = captured.getvalue()
    if text.strip():
        print(text, end="")   # 原样同步进 exe.log
    return webapp_app, text


def _note_initial_password(home: Path, captured: str) -> None:
    if "初始口令" not in captured:
        return
    note = home / "首次启动-初始口令.txt"
    if not note.exists():
        note.write_text(
            "本文件由 exe 首次启动生成;随机初始口令只打印这一次,"
            "登录后请尽快在窗口右上角「改密」,然后即可删除本文件。\n\n"
            + captured, encoding="utf-8")


def _run_gui(webapp_app) -> int:
    """GUI 主流程:单实例探测 → 守护线程起服务 → 健康就绪 → 开窗口至关窗停机。"""
    base_url = _window_url(webapp_app.HOST, webapp_app.PORT)
    if _probe_health(base_url) is not None:
        _messagebox("程序已在运行",
                    f"已在监听 {base_url},请使用已打开的窗口;\n"
                    "如需重新启动,请先结束原进程(任务管理器中的 TransportationHarness)。")
        return 0

    server = webapp_app.make_server()
    worker = threading.Thread(target=server.run, daemon=True, name="uvicorn")
    worker.start()
    if not _wait_healthy(base_url, worker):
        raise RuntimeError("服务线程未能就绪(端口被占用或启动失败,详见运行日志末尾)")

    import webview

    webview.create_window(_WINDOW_TITLE, base_url, width=1360, height=900,
                          min_size=(1100, 700))
    try:
        webview.start()   # 阻塞至窗口关闭;pywebview 默认 private 模式(Cookie 不持久)
    except Exception as exc:
        if "WebView2" in str(exc):
            raise RuntimeError(
                "WebView2 运行时缺失:请安装 Microsoft Edge WebView2 Runtime 后重试\n"
                "https://developer.microsoft.com/microsoft-edge/webview2/") from exc
        raise
    server.should_exit = True   # 关窗即停服:最多等 3s 处理完在途请求
    worker.join(3)
    return 0


def main() -> int:
    """启动器主流程;返回进程退出码。"""
    if not getattr(sys, "frozen", False):
        from webapp.app import main as webapp_main  # 源码直跑:透传,行为与 python webapp/app.py 一致
        webapp_main()
        return 0

    home = _home_dir()
    os.environ["HARNESS_HOME"] = str(home)   # 必须在导入任何业务模块之前:harness.paths 靠它定位
    _seed(_bundle_dir(), home)
    if not _gui_mode and _attach_parent_console():
        pass          # --server 从终端启动:输出直接进终端
    else:
        _open_log(home)   # GUI 模式 / 双击的 --server:stdout 落盘
    print(f"[exe] 数据目录:{home}")

    webapp_app, captured = _import_app()
    _note_initial_password(home, captured)

    if _gui_mode:
        return _run_gui(webapp_app)
    webapp_app.main()   # 无头:阻塞至 Ctrl+C/进程结束
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()   # PyInstaller 打包进程的惯例保护,必须最先执行
    try:
        code = main()
    except SystemExit as exc:          # sys.exit("消息") 是部署参数/依赖错误,报给人看
        if exc.code in (None, 0):
            sys.exit(0)
        _fatal("配置或启动参数错误", str(exc.code))
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
    except BaseException:
        _fatal("未预期的异常", traceback.format_exc())
        sys.exit(1)
    sys.exit(code)
