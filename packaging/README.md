# packaging/ —— 单文件 exe 封装

> 用途：把整个 Web 看板打包成一个双击即用的 `TransportationHarness.exe`，说明构建方法、
> 数据落在哪、报错时去哪看。普通使用不需要读仓库其他文档。

## 文件清单

| 文件 | 干什么 | 写入 |
| --- | --- | --- |
| `exe_entry.py` | exe 入口启动器：定位数据家目录 → 播种初始资产 → 日志落盘 → 自动开浏览器 → 调 `webapp.app.main()` | `harness-home/`（播种与日志，见下） |
| `harness.spec` | PyInstaller 配置：onefile + windowed；种子资产经 `datas` 打入 exe | `dist/`、`build/`（均已 gitignore） |
| `build_exe.bat` | 一键构建：首次自动在 `packaging/.venv` 建独立环境装 fastapi/uvicorn/pyinstaller，再跑 PyInstaller | `packaging/.venv/`（gitignore 的 `.venv/` 规则覆盖） |

## 构建与使用

```bat
packaging\build_exe.bat
```

成功输出末行 `DONE: ...\dist\TransportationHarness.exe`。构建只依赖 Python 3.11+ 与网络
（装依赖）；换机器、删掉 `packaging\.venv` 重来都是安全的。

双击 exe 后的行为：

- 数据家目录 = **exe 旁 `harness-home/`**（首选，便携）；exe 所在位置不可写（如 Program Files）
  时自动回退 `%LOCALAPPDATA%\TransportationHarness`；环境变量 `HARNESS_HOME` 显式指定时最优先。
- 首次启动播种：exe 内置的 `cases/ evalsets/ reports/ llm_cache/ pipeline/data/ webapp/static/`
  复制到数据家目录，`.env.example` 复制为 `.env` —— **缺了才复制**，升级 exe、重启都不覆盖已有数据；
  删除 `harness-home/` 即完整重置。
- 监听回环地址时 1.5 秒后自动打开系统浏览器；`HOST=0.0.0.0` 等部署场景不自动开。
- **平时全程无控制台**；启动失败（端口被占、`AUTH_TOKEN` 过短等）才弹一个黑窗口打印完整错误，
  按回车关闭。运行日志与 uvicorn 输出在 `harness-home/exe.log`（超 5MB 清空重来）。
- 首次启动会随机生成管理员初始口令，只写进 **`harness-home/首次启动-初始口令.txt`** 这一处；
  登录改密后可删除该文件。停止服务用任务管理器结束 `TransportationHarness.exe` 进程。

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
2. 自动弹出浏览器看到看板，登录口令在 `首次启动-初始口令.txt`；
3. 看板里沉淀一条 case → 确认 `harness-home/cases/<标签>/` 多了一个 JSON；
4. 关掉浏览器、结束进程、再次双击 → 数据还在（持久化）；
5. 占用 8765 端口后再双击 → 弹出黑窗口显示端口占用错误，按回车退出。

## 别动

- `exe_entry.py` 里 `os.environ["HARNESS_HOME"] = ...` 必须发生在 `import webapp.app` 之前：
  `harness/paths.py` 在被导入那一刻读取该变量，晚了整条路径链就定位到临时解包目录了。
- 播种逻辑是「缺了才复制」：改成无条件复制会覆盖用户数据；改成按版本戳刷新则需要迁移逻辑，
  当前规模（<1MB 资产）不值得。
- `harness.spec` 的 `hiddenimports` 列表对应 uvicorn 的动态导入（loop/http/websockets/lifespan
  都是运行期按字符串 import 的），静态分析看不见；删了它们 exe 会在启动时报
  `ModuleNotFoundError`。升级 uvicorn 大版本后若冒烟失败，先核对这个列表。
- `console=False`（windowed）不能改成 `console=True` 来「方便看日志」：那样每次双击都会留一个
  黑窗口；日志已经在 `harness-home/exe.log`。报错弹窗由 `exe_entry.py` 的 `_error_console` 负责。
- 未签名 exe 被杀软误报（PyInstaller onefile 常见现象）不是本目录能修的问题；
  需要分发给第三方时走代码签名，别通过改打包参数「绕杀软」。
