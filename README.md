# Transportation Harness · 交通分析自进化评测系统

![Transportation Harness 品牌横幅](webapp/static/assets/banner.svg)

> 用途：给第一次打开这个仓库的人。看完知道它是什么、能不能解决你的问题、怎么在离线环境里跑起来。

线上分析系统最贵的三件事：badcase 散在聊天记录里没人认领、改好一处改坏三处、
新版本好不好全靠嘴说。这个项目把这三件事变成可执行的东西：
一条反馈沉淀成一个**可重放的评测用例**（replaycase），用例汇成**版本化评测集**，
每次迭代必须「提升且无回归」才算数。跑一遍自进化的实测结果是
v0 1/13 → v1 11/13 → v2 13/13（复核：`python scripts/verify.py`）。

评测框架 `harness/` 与「交通」无关：被测对象只要满足 `analyze(segments: list[dict]) -> dict`
并注册进版本表即可，换成别的分析管线闭环同样成立。LLM 层只接在闭环的薄弱环节
（反馈起草用例、结论文本打分、失败诊断），不配置密钥时全程走离线确定性 Mock。

**规模与门禁**：16 条 replaycase · 2 个评测集 · 6 个情景数据集 · 3 个管线版本 ·
190 个测试（复核：`python -m pytest --collect-only -q`）

## 30 秒跑通（离线、零配置、零成本）

```bash
pip install -r requirements.txt

# Windows cmd；PowerShell 用 $env:AUTH_MODE="open"；Linux/macOS 用 AUTH_MODE=open python webapp/app.py
set AUTH_MODE=open && python webapp/app.py
```

终端出现这两行即为启动成功（`AUTH_MODE=open` 只是免登录，仅限本机演示）：

```
交通分析自进化 Harness -> http://127.0.0.1:8765(鉴权模式:open);/api/settings 未启用(设 SETTINGS_ENABLED=1 开启)
INFO:     Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)
```

浏览器打开 <http://127.0.0.1:8765>：欢迎页 → 侧边栏 5 个页签（评测看板 / Case 管理 /
版本对比 / 分析提交 / 设置）。拨测接口给的真实响应：

```bash
curl http://127.0.0.1:8765/api/health
```

```json
{"status":"ok","app_version":"1.5.0","auth_mode":"open","default_credentials":true,
 "versions":["v0","v1","v2"],"case_count":16,"evalset_count":2,"report_count":11}
```

不启动服务也能跑闭环（纯命令行，同样离线）：

```bash
python scripts/run_eval.py --version v0      # 看基线错在哪:1/13 通过(7.7%)
python -m harness.evolve                     # 基线 → 逐版本验证 → 归档报告
python scripts/verify.py                     # 端到端不变量校验,预期 VERIFY PASS
```

完整步骤（含真实报错与处理办法）见 [docs/getting-started.md](docs/getting-started.md)。

## 界面

| 评测看板 | 智能助手面板（Runtime 状态 / 草稿 / 诊断） |
| --- | --- |
| ![评测看板](docs/images/dashboard.png) | ![智能助手](docs/images/assistant.png) |

三栏布局可拖拽，深色模式一键切换；页面已按 PWA 打包，localhost 或 HTTPS 下可安装、可离线浏览最近一次数据。

## 能做什么

| 入口 | 做什么 | 用什么 | 细节 |
| --- | --- | --- | --- |
| 跑评测 | 重放整个评测集并逐条判分、归档报告 | `python scripts/run_eval.py --version v2 [--md]` | [scripts/README.md](scripts/README.md) |
| 一键自进化 | 基线测量 → 逐登记版本验证 → 回归检查 → 归档 | `python -m harness.evolve [--evalset 名称] [--baseline v2]` | [harness/README.md](harness/README.md) |
| 沉淀 badcase | 反馈 → 可重放用例，自动进评测集 | 看板「Case 管理」或 `POST /api/cases` | [cases/README.md](cases/README.md)、[docs/API.md](docs/API.md) |
| 看板（PWA） | 得分趋势、进化时间线回放、版本逐用例差分、在线读写 `.env` | 浏览器打开 `/`，文档中心 `/help` | [webapp/README.md](webapp/README.md) |
| 微信小程序 | 外业现场提交 badcase、看进化结果 | 微信开发者工具导入 `miniprogram/` | [miniprogram/README.md](miniprogram/README.md) |
| Python SDK / CLI | 程序化调用、CI 里守回归 | `pip install ./sdk` → `harness-client eval --version v2` | [sdk/README.md](sdk/README.md)、[docs/INTEGRATION.md](docs/INTEGRATION.md) |

LLM 相关能力（草稿助手、LLM-as-Judge、失败诊断双智能体）见 [docs/LLM.md](docs/LLM.md)；
全部接口清单见 [docs/API.md](docs/API.md) 与机器可读的 `docs/openapi.json`。

## 进化结果概览

下表全部由 `python scripts/verify.py` 与 `python -m harness.evolve` 在仓库自带资产上重放得到，
归档在 `reports/`（最新一次完整记录：`reports/evolution_20260920_213232.json`）。

| 版本 | 这一轮改了什么 | 得分（复核：`python scripts/run_eval.py --version v0` 等） | 回归 |
| --- | --- | --- | --- |
| v0 | 基线：按车速分四档、饱和度漏乘车道数、延误公式方向反、缺数据即崩 | 1/13（7.7%），唯一通过的是回归保护用例 rc-0013 | — |
| v1 | 分级改看 V/C 五级、公式修正、缺失数据降级、生成处置建议 | 11/13（84.6%），新通过 10 条 | 0 条 |
| v2 | 边界升级（V/C∈[0.75,0.8) 且速度比<0.35）、全局指数按流量加权、空数据防御 | 13/13（100%），新通过 2 条 | 0 条 |

雨天情景评测集 `evalset_scenario_rain`（3 条）上：v0 0/3 → v1 2/3 → v2 3/3
（复核：`python scripts/verify.py --evalset evalset_scenario_rain`）。

## 目录怎么分

不知道东西在哪个路径，先看 [目录说明.md](目录说明.md)：整棵目录树、每个目录的入口都在里面，它只做导航。谁负责什么以 `AGENTS.md` 的「仓库地图」为准。

| 目录 | 负责 |
| --- | --- |
| `harness/` | 评测框架：数据结构、存储、重放、判分、报告、自进化 |
| `pipeline/` | 被测对象：v0/v1/v2 三版分析管线 + 6 个情景数据集 |
| `llm/` | LLM 层：Runtime、判分器、两条工作流、缓存与审计 |
| `webapp/` | FastAPI 后端（31 个 `/api` 操作）与单文件 PWA 前端 |
| `cases/` `evalsets/` `reports/` | 评测资产：用例库、评测集清单、归档 |
| `scripts/` | 命令行工具：种子沉淀、评测、校验、备份、OpenAPI 导出 |
| `sdk/` `miniprogram/` | 官方 Python SDK 与微信小程序客户端 |
| `tests/` | 190 个测试（复核：`python -m pytest --collect-only -q`） |

逐个目录的说明见各目录下的 `README.md`；架构决策与关键约定在 [AGENTS.md](AGENTS.md)。

## 已知局限

1. **版本只有三个，且都是"事后重写"的样例**。v1/v2 是针对已知 badcase 手工迭代的产物，
   新增 v3 需要人来写算法，harness 只负责验证与守回归，不会自动生成新版本。
2. **基线传最后一个已登记版本会失败**：`python -m harness.evolve --baseline v2` 抛
   `IndexError: list index out of range`，对应 API 返回 `500`（原因见 [AGENTS.md](AGENTS.md) 已知坑）。
   增量验证请用「上一个版本」作基线，例如登记 v3 后用 `--baseline v2`。
3. **结论文本质量没有真实模型判分**。`conclusion_quality` 检查由 `llm/judge.py` 走 LLM 打分，
   未配置密钥时是确定性启发式；仓库现有用例只用到 `conclusion_keyword`，
   所以「100%」衡量的是结构化断言，不等于结论可读性已达人工水准。
4. **交通数据是合成快照**（`pipeline/data/*.json`，`captured_at` 为 2026-08-31），
   未接卡口/GPS 实时源；换真实数据要自己加 ingest 端点或改 `storage.load_dataset`。
5. **小程序正式发布有硬门槛**：必须 HTTPS + 已备案域名并在小程序后台配置合法域名，
   当前默认部署是 `http://<地址>:8765`，只适合开发与内网使用（见 [DEPLOY.md](DEPLOY.md)）。
6. **单进程文件存储**：并发靠进程内锁（沉淀、自进化各一把），多实例部署时锁不跨进程，
   需要外层串行化或改数据库。

## 环境要求

Python 3.11+（CI 跑 3.11 与 3.12 两条矩阵）。运行时依赖只有 `fastapi` 与 `uvicorn`
（复核：`cat requirements.txt`）；开发/测试另需 `pytest`、`httpx`、`ruff`、`Pillow`
（复核：`cat requirements-dev.txt`）。默认全程离线：不需要网络、不需要模型密钥。
Docker 部署见 [DEPLOY.md](DEPLOY.md)。

## 许可

MIT（[LICENSE](LICENSE)）。

---

准备改动这个仓库的 AI 助手或开发者，请先读 [AGENTS.md](AGENTS.md)。
