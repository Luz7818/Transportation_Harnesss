# sdk/ —— 官方 Python SDK（导入名 `harness_client`）

> 用途：说明本目录负责什么、每个文件干什么，以及怎么装、怎么用。
> 下面是目录说明；用法正文从「transportation-harness-sdk」一节继续。

本目录是一个**独立可安装的 Python 包**（`pyproject.toml` + `harness_client/`），
把后端 `/api/*` 封装成方法与强类型模型：脚本、CI、外部系统靠它接入评测与自进化，
不需要自己拼 HTTP。它是 `docs/openapi.json` 的薄封装 —— 端点改动必须同步这里
（约定与重导步骤见 [AGENTS.md](../AGENTS.md)）。

## 文件清单

| 文件 | 干什么 | 备注 |
| --- | --- | --- |
| `pyproject.toml` | 包元数据：名 `transportation-harness-sdk`、版本 `1.5.0`、依赖只有 `httpx>=0.27`、`harness-client` 命令行入口、hatchling 构建 | 与服务端版本需同步（`FastAPI(version=...)` 与根 `pyproject.toml`） |
| `harness_client/client.py` | `TransportationHarnessClient`：30 个公开方法（含 `close`），其中 29 个对应 API 操作 —— `/api/settings` 的 GET/PUT 刻意不接 | 凭据两条通道：`token=` 走 `X-API-Token`，`username`+`password` 自动登录并持有会话 Cookie |
| `harness_client/models.py` | 强类型返回：`EvalResult`（含 `report_id`、`failed_cases()`）、`CaseResult`、`CheckResult`、`CompareResult`（含 `regressed`）、`CompareRow` | 只对「评测结果」与「版本对比」两类核心负载建模；其余端点返回原生 dict，避免模型层与后端强耦合 |
| `harness_client/cli.py` | `harness-client` 命令行：`health` / `versions` / `datasets` / `analyze` / `eval` | 地址与令牌取 `HARNESS_BASE_URL` / `HARNESS_TOKEN`，默认 `http://127.0.0.1:8765`；出错统一退出码 1 并把 `错误:…` 写 stderr |
| `harness_client/errors.py` | `HarnessAuthError`（401）与 `HarnessAPIError`（其它非 2xx，带 `.status`） | pydantic 校验错误数组会被拼成一句可读文本 |
| `harness_client/__init__.py` | 导出与 `__version__ = "1.5.0"` | 只 re-export，不含逻辑 |
| `dist/transportation_harness_sdk-1.5.0-py3-none-any.whl` / `.tar.gz` | 构建产物，按约定入库 | 改了包内容要重新构建再提交，别手改 |
| `README.md` | 本文件 | — |

## 别动

- 不要给 SDK 加 `/api/settings`：那枚机器令牌与小程序共用，服务器配置接口刻意不认它。
- 不要让 SDK 依赖服务端代码（`harness/`、`webapp/`）：它只走 HTTP，这样才能独立 `pip install`。
- 不要为「方便」把返回全部改成 dict：`run_eval` / `compare` 的强类型是 CI 守回归的接口。

# transportation-harness-sdk

交通分析自进化 Harness 的官方 Python SDK(导入名 `harness_client`)。

```bash
pip install ./sdk            # 从仓库本地安装
# 或发布后:pip install transportation-harness-sdk
```

```python
from harness_client import TransportationHarnessClient

# base_url 换成你的服务地址(本地跑就是 http://127.0.0.1:8765);
# token 是服务端启动时设的 AUTH_TOKEN 那一串(仓库里不记录真实值)
with TransportationHarnessClient(base_url="http://<你的服务器地址>:8765",
                                 token="<AUTH_TOKEN 的值>") as client:
    print(client.health())
    result = client.run_eval(version="v2")          # 强类型 EvalResult
    print(result.accuracy, result.report_id)
    comparison = client.compare(result.report_id, other_report_id)
    print(comparison.regressed)                      # 回归列表,非空即阻止合入

# 没有 AUTH_TOKEN 时也可以走登录通道(SDK 自动持有会话 Cookie):
# TransportationHarnessClient(base_url="http://<你的服务器地址>:8765",
#                             username="admin", password="<你的口令>")
```

命令行:

```bash
harness-client health --base-url http://<你的服务器地址>:8765 --token <AUTH_TOKEN 的值>
harness-client eval --version v2            # 不传 --base-url/--token 时取本地默认与
                                            # HARNESS_BASE_URL / HARNESS_TOKEN 环境变量
```

完整接入文档见 [docs/INTEGRATION.md](../docs/INTEGRATION.md)。
