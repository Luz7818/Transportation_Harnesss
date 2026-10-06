"""单文件 exe 启动器:准备便携数据家目录、播种初始资产,再拉起 Web 看板。

仅打包场景使用(PyInstaller windowed 模式,packaging/harness.spec 以本文件为入口):
正常运行全程无控制台,uvicorn 日志写入 harness-home/exe.log,监听回环地址时
自动打开系统浏览器;启动失败(端口占用 / 配置错误 / 依赖缺失)时才临时分配一个
控制台打印完整错误,按回车后退出。

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
import multiprocessing
import os
import shutil
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

# 首启播种清单(exe 内置只读资产 → 数据家目录,缺了才复制,绝不覆盖)
_SEED_DIRS = ("cases", "evalsets", "reports", "llm_cache", "pipeline/data", "webapp/static")
_SEED_FILES = (".env.example",)      # 复制为 .env:全是注释模板,不含任何会改变行为的实际值
_LOG_NAME = "exe.log"
_LOG_MAX_BYTES = 5 * 1024 * 1024     # 日志超限清空重来:它只服务排障,不承担历史归档

# 供 __main__ 的报错弹窗提示日志位置;main() 内赋值
_log_path: Path | None = None


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
    """隐藏控制台模式下 stdout/stderr 落盘:uvicorn 日志与运行期告警全写这里。"""
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
    """取运行日志末尾若干行:uvicorn 端口占用等错误只进日志不抛消息串,弹窗须带上它。"""
    if _log_path is None or not _log_path.is_file():
        return ""
    try:
        text = _log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    tail = "\n".join(text.splitlines()[-lines:]).strip()
    return f"\n---- 运行日志末尾({_log_path.name}) ----\n{tail}" if tail else ""


def _error_console(title: str, detail: str) -> None:
    """仅启动失败时调用:分配控制台打印完整错误,按回车后退出(正常路径绝不弹窗)。

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
    print(_log_tail())
    print("\n按回车键关闭窗口…")
    with contextlib.suppress(Exception):
        input()


def main() -> int:
    """启动器主流程;返回进程退出码。"""
    if not getattr(sys, "frozen", False):
        from webapp.app import main as webapp_main  # 源码直跑:透传,行为与 python webapp/app.py 一致
        webapp_main()
        return 0

    home = _home_dir()
    os.environ["HARNESS_HOME"] = str(home)   # 必须在导入任何业务模块之前:harness.paths 靠它定位
    _seed(_bundle_dir(), home)
    _open_log(home)
    print(f"[exe] 数据目录:{home}")

    # redirect_stdout 捕获 import 期间的输出:首启时 auth.json 不存在,
    # 随机初始口令只在此刻打印一次 —— 控制台隐藏后必须落盘才找得回来
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        import webapp.app as webapp_app
    if captured.getvalue().strip():
        print(captured.getvalue(), end="")   # 原样同步进 exe.log
        if "初始口令" in captured.getvalue():
            note = home / "首次启动-初始口令.txt"
            if not note.exists():
                note.write_text(
                    "本文件由 exe 首次启动生成;随机初始口令只打印这一次,"
                    "登录后请尽快在看板右上角「改密」,然后即可删除本文件。\n\n"
                    + captured.getvalue(), encoding="utf-8")

    # 回环监听才自动开浏览器:0.0.0.0 等局域网/公网部署由用户自行访问
    if webapp_app.HOST in ("127.0.0.1", "::1", "localhost"):
        url = f"http://127.0.0.1:{webapp_app.PORT}"
        opener = threading.Timer(1.5, webbrowser.open, args=(url,))
        opener.daemon = True
        opener.start()
    webapp_app.main()
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()   # PyInstaller 打包进程的惯例保护,必须最先执行
    try:
        code = main()
    except SystemExit as exc:          # sys.exit("消息") 是部署参数/依赖错误,弹窗示人
        if exc.code in (None, 0):
            sys.exit(0)
        _error_console("配置或启动参数错误", str(exc.code))
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
    except BaseException:
        _error_console("未预期的异常", traceback.format_exc())
        sys.exit(1)
    sys.exit(code)
