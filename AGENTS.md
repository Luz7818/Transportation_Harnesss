# AGENTS.md —— 项目协作与代码开发规范（唯一权威入口）

> 用途：给 AI 编码助手与后续维护者。这里是规范入口与索引：目标、原则、流程、模块规则、
> 维护矩阵、阅读清单都在这份文件里。细则一律链接到对应文件，冲突时以细则文件为准并回改本文件。
> 本文件是被其他文档引用的事实来源：端点数、测试数、命令、路径以这里的「当前状态」为准，
> 别的文档只链接。

## 项目目标

- 定位：FastAPI 单进程服务 + 文件型评测资产的交通分析自进化评测系统：线上 badcase 沉淀为
  可重放 replaycase → 版本化评测集 → 逐版本验证「提升且无回归」→ 归档报告。
- 核心功能：评测重放、一键自进化、badcase 沉淀（看板/小程序/API）、PWA 看板、Python SDK/CLI、
  LLM 智能层（草稿/判分/诊断，全可降级）。
- 技术栈：Python 3.11+，运行时 `fastapi` + `uvicorn`（复核：`pyproject.toml` 的
  `dependencies`——requirements 两文件已并入 pyproject 单源，见提交 `f834605`）。
- 详情：[README.md](README.md)、[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 开发原则

1. 正确性优先。
2. 可维护性优先。
3. 代码简洁、项目简洁。
4. 小步迭代。
5. 单模块开发。
6. 每个改动必须有明确设计与验收标准。
7. 禁止一次生成整个项目。
8. 禁止跳步开发。

执行口径：先想后写（假设与歧义先挑明）；最简优先（不加没要求的功能与抽象——一切皆 JSON 文件、
不引数据库是有意取舍）；外科手术式改动（不动无关代码，每行改动可追溯到需求）；目标驱动
（先有可验证判据再动手，宣称完成前先跑通 [docs/TESTING.md](docs/TESTING.md) 的四条门禁）。

## 开发流程

**分析 → 设计 → 实现 → 测试 → 文档更新 → Git提交 → 等待确认**。不得跳过任何阶段。

| 阶段 | 产出物 | 放行标准 |
| --- | --- | --- |
| 分析 | 影响面清单（框架/被测管线/端点/SDK/前端哪一侧，是否触及鉴权与资产契约） | 影响面说全 |
| 设计 | 方案说明（契约/命名/归档影响、回退方式） | 验收标准已定义；与更简方案比较过 |
| 实现 | 代码 | 只含设计内改动，符合 [docs/CODE-STYLE.md](docs/CODE-STYLE.md) |
| 测试 | 门禁结果 | `ruff check .` + `pytest` + `verify.py` + `check_release.py` 全过 |
| 文档更新 | 受影响文档 diff（端点改动含 OpenAPI/API.md/help.html/SDK 同步） | 维护矩阵逐项过完 |
| Git提交 | 提交 | 符合 [docs/GIT.md](docs/GIT.md)，一批一提交 |
| 等待确认 | —— | 等人确认后推送 |

## 模块开发规则

- 一个智能体一次只开发一个模块；模块完成后才能进入下一模块。
- 如需同时开发，使用多个子智能体，每个子智能体同样一次只开发一个模块。

模块完成标准（全部满足才算完成）：

1. 功能完成：达到 [TODO.md](TODO.md) 中该任务的验收标准。
2. 测试通过：符合 [docs/TESTING.md](docs/TESTING.md)。
3. 最简原则：代码和项目架构都保持最简洁，无冗余抽象与重复实现。
4. [TODO.md](TODO.md) 更新：勾选完成项、明确下一项。
5. [HISTORY.md](HISTORY.md) 追加变更记录（破坏契约升主版本，加能力升次版本，修缺陷升补丁）。
6. 受影响的 docs 更新（按需；端点改动必须同步 OpenAPI/API.md/help.html/SDK）。
7. [README.md](README.md) 更新（如有面向使用者的变化）。
8. Commit message 符合 [docs/GIT.md](docs/GIT.md)。

## 文档维护规则

| 事件 | 需更新 |
| --- | --- |
| 模块完成 | `TODO.md`、`HISTORY.md`、受影响 docs |
| 版本发布 | `HISTORY.md` 新条目 + 版本四处同步 + tag |
| 架构决策（分层、判分、存储、安全模型变化） | `docs/ARCHITECTURE.md` + `HISTORY.md` 记录缘由 |
| 端点/请求体变化 | `export_openapi.py` 重导 + `docs/API.md` + `static/help.html` + `sdk/` |
| 增删一级或二级目录 | 仓根 `目录说明.md` + 本文件 |
| 端点数/测试数/评测资产数变化 | 本文件「当前状态」 |
| 新对话/新任务开始 | 按下方阅读清单阅读 |

## 开发前阅读清单

每个新对话/新任务，按顺序阅读：

1. 本文件（`AGENTS.md`）
2. [TODO.md](TODO.md)
3. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)（数据流、仓库地图、鉴权事实、设计决策、
   常见任务表在这里）
4. [docs/GET-START.md](docs/GET-START.md)
5. [HISTORY.md](HISTORY.md)
6. 与任务相关的 [docs/CODE-STYLE.md](docs/CODE-STYLE.md)、[docs/TESTING.md](docs/TESTING.md)、[docs/GIT.md](docs/GIT.md)

阅读完成后**不要写代码**：先做架构评审，输出——项目理解 / 核心模块 / 模块依赖关系 / 潜在风险 /
建议优化项 / 推荐开发顺序 / 是否发现架构问题——然后等待确认。

## Git 索引

- Git 规范：[docs/GIT.md](docs/GIT.md)（评测归档的处理规则、敏感信息绝不入库、CI、
  一批一提交）

## 当前状态

| 项 | 值 | 复核命令 |
| --- | --- | --- |
| 测试 | `210 passed`(本机实测 30–55 s 之间浮动,含真起 uvicorn 的 SDK 用例;耗时受机器负载影响,别当判据) | `python -m pytest` |
| 测试分布 | 15 个文件共 210 例,最大 `test_webapp.py` 39 例、`test_settings_api.py` 37 例、`test_llm.py` 30 例 | `python -m pytest --collect-only -q` |
| 静态检查 | `All checks passed!`,退出码 0 | `ruff check .` |
| 端到端校验 | `VERIFY PASS`,退出码 0;雨天评测集同样 PASS | `python scripts/verify.py` |
| 发布一致性 | `RELEASE CHECK PASS`:版本四处一致 + `docs/openapi.json` 与 app 当前 schema 逐键一致(29 路径) | `python scripts/check_release.py` |
| API 面 | `/api/*` 31 个操作(27 条路径),另有 3 条页面路由 | `python -c "import json;s=json.load(open('docs/openapi.json',encoding='utf-8'));print(len(s['paths']),sum(len(v) for v in s['paths'].values()))"` |
| SDK 面 | 30 个公开方法(含 `close`),其中 29 个对应 API 操作 —— `/api/settings` 的 GET/PUT 刻意不接 | `python -c "import ast;print(len([n for n in ast.walk(ast.parse(open('sdk/harness_client/client.py',encoding='utf-8').read())) if isinstance(n,ast.FunctionDef) and not n.name.startswith('_')]))"` |
| 评测资产 | 18 条 replaycase(8 个标签目录)、2 个评测集(15 + 3 条)、6 个数据集、`reports/` 归档随运行增长 | `python -c "import glob;print(len(glob.glob('cases/*/*.json')),len(glob.glob('evalsets/*.json')),len(glob.glob('pipeline/data/*.json')),len(glob.glob('reports/*')))"` |
| 得分轨迹 | evalset_v1:v0 1/13 → v1 11/13 → v2 13/13;evalset_scenario_rain:0/3 → 2/3 → 3/3 | `python scripts/verify.py` |
| CI | 两条矩阵 job:`test (3.11)`、`test (3.12)`;当前分支 HEAD 的徽章为 `passing`(复核见右)。本机没有 `gh`,但徽章与 Actions 接口对**公开仓都免认证**;要提交号与耗时再用 `/actions/runs`(匿名限 60 次/小时/IP,别拿它轮询) | `python -c "import urllib.request as u;b=u.urlopen(u.Request('https://github.com/Luz7818/Transportation_Harnesss/workflows/CI/badge.svg',headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read().decode();print('passing' in b)"` 应为 `True`;步骤清单见 `.github/workflows/ci.yml` |
| CI 步骤 | `ruff check .` → `pytest` → `python scripts/verify.py` → `python scripts/check_release.py`,另装 `pip install -e .[dev]`（requirements 已并入 pyproject 单源）与 `pip install ./sdk` | `cat .github/workflows/ci.yml` |
| 线上服务 | **已下线**（2026-10-06 决策）：TCP 8765 自 10-02 起连续失联 6 天,本机无主机访问渠道,每日探针连败失去信号价值。已撤 `probe.yml` 与 README 徽章;`scripts/probe_live.py` 保留(复活时本地探测用)。复活路径见 [DEPLOY.md](docs/DEPLOY.md) 与 HISTORY 当日条目 | `git log --oneline -- "**/probe.yml"`(恢复点) |
| 版本 | 应用与 SDK 均为 `2.0.0`(四处同步:根 `pyproject.toml`、`sdk/pyproject.toml`、`sdk/harness_client/__init__.py`、`FastAPI(..., version=...)`;一致性已由 check_release 断言进 CI) | `python scripts/check_release.py` |
| 发布 | `HISTORY.md` 从 2.0.0 起向前记录;tag 命名 `v主.次.补` | `head -20 HISTORY.md` |

## 已知坑（省下一次的调查时间）

- **裸 `pytest` 与 `python -m pytest` 的 `sys.path` 不同**：`pythonpath = ["."]`
  （`pyproject.toml`）是修这个问题的——缺了它 `tests/` 全部在收集期
  `ModuleNotFoundError: No module named 'harness'`。别删掉或改成 conftest 单点兜底。
- **`tests/test_sdk.py` 的隔离夹具别拆**：`server_url` 会把 `AUTH_FILE` 与 `_AUTH_STORE`
  换到临时文件，拆了单跑就读到本机真实 `webapp/auth.json` 而 401。
- **本机 `webapp/auth.json` 的 `default_credentials` 已翻转为 false**（1.6.0 轮换通道）；
  `/api/health` 原样回显该布尔。线上服务已下线（2026-10-06），复活部署后按 DEPLOY.md 重配探针。
- **Windows 控制台/管道编码**：捕获输出前 `set PYTHONIOENCODING=utf-8`（脚本自身有
  `reconfigure`，但没走这条的进程在 GBK 控制台经管道会乱码）。
- **评测脚本会往 `reports/` 写文件**：干净工作区试跑后，要么一起提交（归档即历史），
  要么删干净再提交，别留半套不一致的归档。
- **`/api/settings` 默认关闭**：不要为了让页面能用而把 `SETTINGS_ENABLED` 写进仓库任何文件。
- **`ruff` 的 `per-file-ignores`**：`webapp/app.py`、`scripts/*.py`、`tests/conftest.py`
  允许 E402（先插 sys.path 再 import 是刻意的运行模式），别为了"干净"调顺序。
- 2026-10-05 已清理：根目录 `batch_demo_ids.txt` 与 `cases/` 两个空目录；
  `storage.safe_label()` 对空标签兜底返回「未分类」，目录会自动重建。
- 不要放宽 `MIN_IMPROVEMENT`/`EVOLVE_MAX_ROUNDS`/回归一票否决；不要给产物加时间戳之外的
  可变值；不要把运行产物当源码修；不要在文档写公网 IP/真实令牌/口令取值；不要新增第二个
  会话格式或判分入口；不要让测试读真实资产；不要把机器令牌加进 `/api/settings` 准入；
  不要只改 API.md 或只改 help.html 之一，不要手改 `docs/openapi.json`。
