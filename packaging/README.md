# packaging/ —— 单文件 exe 封装

> 用途：把整个 Web 看板打包成一个双击即用的 `TransportationHarness.exe`，说明构建方法、
> 数据落在哪、报错时去哪看。普通使用不需要读仓库其他文档。

## 文件清单

| 文件 | 干什么 | 写入 |
| --- | --- | --- |
| `exe_entry.py` | exe 入口启动器：定位数据家目录 → 播种初始资产 → 日志落盘 → uvicorn 守护线程 → 开独立窗口（默认）或无头服务（`--server`） | `harness-home/`（播种与日志，见下） |
| `harness.ico` | exe 图标，由 `webapp/static/assets/icon-512.png` 一次性转换（重转才需动） | 不写 |
| `harness.spec` | PyInstaller 配置：onefile + windowed；种子资产经 `datas` 打入 exe | `dist/`、`build/`（均已 gitignore） |
| `build_exe.bat` | 一键构建：首次自动在 `packaging/.venv` 建独立环境装 fastapi/uvicorn/pywebview/pyinstaller，再跑 PyInstaller | `packaging/.venv/`（gitignore 的 `.venv/` 规则覆盖） |

## 构建与使用

```bat
packaging\build_exe.bat
```

成功输出末行 `DONE: ...\dist\TransportationHarness.exe`。构建只依赖 Python 3.11+ 与网络
（装依赖）；换机器、删掉 `packaging\.venv` 重来都是安全的。

双击 exe 后的行为（默认 GUI 模式）：

- **弹出独立应用窗口**（pywebview/WebView2 渲染看板，无浏览器地址栏与标签页，任务栏显示应用图标）；
  服务跑在守护线程里，**关闭窗口即优雅停机**（最多等 3 秒处理完在途请求）。
- 数据家目录 = **exe 旁 `harness-home/`**（首选，便携）；exe 所在位置不可写（如 Program Files）
  时自动回退 `%LOCALAPPDATA%\TransportationHarness`；环境变量 `HARNESS_HOME` 显式指定时最优先。
- 首次启动播种：exe 内置的 `cases/ evalsets/ reports/ llm_cache/ pipeline/data/ webapp/static/`
  复制到数据家目录，`.env.example` 复制为 `.env` —— **缺了才复制**，升级 exe、重启都不覆盖已有数据；
  删除 `harness-home/` 即完整重置。
- **单实例**：程序已在运行时再次双击，弹原生提示后退出，不会叠加第二个服务。
- **平时全程无黑窗口**；启动失败（端口被占、`AUTH_TOKEN` 过短、WebView2 缺失等）弹原生 MessageBox
  展示错误与日志末尾。运行日志与 uvicorn 输出在 `harness-home/exe.log`（超 5MB 清空重来）。
- 窗口为 private 模式：**每次启动需重新登录**（换来零缓存残留、升级无旧 UI 风险）；
  本机自用想免登录可在 `harness-home/.env` 设 `AUTH_MODE=open`。
- 首次启动会随机生成管理员初始口令，只写进 **`harness-home/首次启动-初始口令.txt`** 这一处；
  登录改密后可删除该文件。

### 无头服务模式（`--server`）

`TransportationHarness.exe --server` 与源码 `python webapp/app.py` 行为一致：阻塞运行、
不弹窗口，供公网/局域网部署与脚本使用。从终端启动时接管父控制台（banner 与 uvicorn
日志直接可见）；双击启动（无终端）时输出落 `harness-home/exe.log`，报错弹黑窗口。

## 和谁打交道

- **入口契约**：`webapp/app.py` 的 `main()`（源码直跑与 exe 共用同一入口）与
  `harness/paths.py` 的 `HARNESS_HOME` 约定 —— 全仓数据目录都从它定位，
  启动器在导入任何业务模块之前设好该变量，这是本目录与仓库其余部分的唯一耦合点。
- **种子资产**：`cases/`、`evalsets/`、`reports/`、`llm_cache/`、`pipeline/data/`、`webapp/static/`
  的当前内容会被打进 exe。想让 exe 带着新的评测资产出厂，先更新这些目录再重新构建。
- **改这里之后要跑**：仓库门禁（`ruff check .` + `python -m pytest` + `python scripts/verify.py`
  + `python scripts/check_release.py`）必须全绿；再跑一次 `packaging\build_exe.bat` 确认能出包，
  并把 exe 复制到独立空目录双击冒烟（见下）。

## 冒烟清单（出新包后手动过一遍）

1. 把 `dist/TransportationHarness.exe` 复制到**空目录**（别在仓库根跑，避免和源码数据混在一起）双击；
2. **独立窗口**弹出并加载看板（不是浏览器），登录口令在 `首次启动-初始口令.txt`；
3. 看板里沉淀一条 case → 确认 `harness-home/cases/<标签>/` 多了一个 JSON；
4. **关闭窗口** → 进程自动退出（端口释放），再次双击 → 数据还在（持久化）；
5. 窗口开着时再双击一次 → 弹"程序已在运行"提示，原窗口不受影响；
6. 占用 8765 端口后双击 → MessageBox 显示绑定错误与日志末尾；
7. `TransportationHarness.exe --server` 从终端启动 → banner 进终端、服务阻塞运行，Ctrl+C 退出。

## 别动

- `exe_entry.py` 里 `os.environ["HARNESS_HOME"] = ...` 必须发生在 `import webapp.app` 之前：
  `harness/paths.py` 在被导入那一刻读取该变量，晚了整条路径链就定位到临时解包目录了。
- 播种逻辑是「缺了才复制」：改成无条件复制会覆盖用户数据；改成按版本戳刷新则需要迁移逻辑，
  当前规模（<1MB 资产）不值得。
- `harness.spec` 的 `hiddenimports` 列表对应 uvicorn 的动态导入（loop/http/websockets/lifespan
  都是运行期按字符串 import 的），静态分析看不见；删了它们 exe 会在启动时报
  `ModuleNotFoundError`。升级 uvicorn 大版本后若冒烟失败，先核对这个列表。
- `console=False`（windowed）不能改成 `console=True` 来「方便看日志」：那样每次双击都会留一个
  黑窗口；日志已经在 `harness-home/exe.log`。报错分两路：GUI 模式走 `_messagebox`（原生弹窗），
  `--server` 模式走 `_error_console`（黑窗口），都在 `exe_entry.py` 里。
- `webview.start()` 必须在主线程调用（pywebview 的平台后端要求），uvicorn 因此放守护线程；
  两者的启停顺序（先健康就绪再开窗、关窗后 `should_exit`）不要对调，否则会出现空白窗口或僵尸端口。
- pywebview 的 hooks-contrib 钩子（`hook-webview` / `hook-clr` / `hook-clr_loader`）负责打包
  WebView2 支撑文件；`harness.spec` 里 `webview.platforms.winforms` / `edgechromium` 两个
  hiddenimports 是平台后端入口，删了会在启动时报 `ModuleNotFoundError`。
- 未签名 exe 被杀软误报（PyInstaller onefile 常见现象）不是本目录能修的问题；
  需要分发给第三方时走代码签名，别通过改打包参数「绕杀软」。
