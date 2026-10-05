# 给 AI 的项目说明

> 用途：给 AI 编码助手与后续维护者。这里是事实与约束，不含介绍性文字。改动本仓库前先读这份。
> 本文件是被其他文档引用的事实来源：端点数、测试数、命令、路径以这里为准，别的文档只链接。

## 一句话

FastAPI 单进程服务 + 文件型评测资产的交通分析自进化评测系统：
线上 badcase 沉淀为可重放 replaycase → 版本化评测集 → 逐版本验证「提升且无回归」→ 归档报告；
配 PWA 看板、微信小程序、Python SDK、CLI 四个客户端，默认全程离线确定性（LLM 走 Mock）。

## 当前真实状态

| 项 | 值 | 复核命令 |
| --- | --- | --- |
| 测试 | `208 passed`(本机实测 30–55 s 之间浮动,含真起 uvicorn 的 SDK 用例;耗时受机器负载影响,别当判据) | `python -m pytest` |
| 测试分布 | 14 个文件共 208 例,最大 `test_webapp.py` 39 例、`test_settings_api.py` 37 例、`test_llm.py` 30 例 | `python -m pytest --collect-only -q` |
| 静态检查 | `All checks passed!`,退出码 0 | `ruff check .` |
| 端到端校验 | `VERIFY PASS`,退出码 0;雨天评测集同样 PASS | `python scripts/verify.py` |
| 发布一致性 | `RELEASE CHECK PASS`:版本四处一致 + `docs/openapi.json` 与 app 当前 schema 逐键一致(29 路径) | `python scripts/check_release.py` |
| API 面 | `/api/*` 31 个操作(27 条路径),另有 3 条页面路由 | `python -c "import json;s=json.load(open('docs/openapi.json',encoding='utf-8'));print(len(s['paths']),sum(len(v) for v in s['paths'].values()))"` |
| SDK 面 | 30 个公开方法(含 `close`),其中 29 个对应 API 操作 —— `/api/settings` 的 GET/PUT 刻意不接 | `python -c "import ast;print(len([n for n in ast.walk(ast.parse(open('sdk/harness_client/client.py',encoding='utf-8').read())) if isinstance(n,ast.FunctionDef) and not n.name.startswith('_')]))"` |
| 评测资产 | 18 条 replaycase(8 个标签目录)、2 个评测集(15 + 3 条)、6 个数据集、`reports/` 归档随运行增长 | `python -c "import glob;print(len(glob.glob('cases/*/*.json')),len(glob.glob('evalsets/*.json')),len(glob.glob('pipeline/data/*.json')),len(glob.glob('reports/*')))"` |
| 得分轨迹 | evalset_v1:v0 1/13 → v1 11/13 → v2 13/13;evalset_scenario_rain:0/3 → 2/3 → 3/3 | `python scripts/verify.py` |
| CI | 两条矩阵 job:`test (3.11)`、`test (3.12)`;当前分支 HEAD 的徽章为 `passing`(复核见右)。本机没有 `gh`,但徽章与 Actions 接口对**公开仓都免认证**;要提交号与耗时再用 `/actions/runs`(匿名限 60 次/小时/IP,别拿它轮询) | `python -c "import urllib.request as u;b=u.urlopen(u.Request('https://github.com/Luz7818/Transportation_Harnesss/workflows/CI/badge.svg',headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read().decode();print('passing' in b)"` 应为 `True`;步骤清单见 `.github/workflows/ci.yml` |
| CI 步骤 | `ruff check .` → `pytest` → `python scripts/verify.py` → `python scripts/check_release.py`,另装 `pip install -r requirements.txt -r requirements-dev.txt` 与 `pip install ./sdk` | `cat .github/workflows/ci.yml` |
| 线上探针 | `.github/workflows/probe.yml` 每天只读 `GET /api/health`,断言在线且 `default_credentials=false`;服务地址存仓库 secret `LIVE_HEALTH_URL`,**不入库**;线上未配置该 secret 或服务未收口前,探针会红 —— 这是设计,不是故障 | `cat scripts/probe_live.py` + `cat .github/workflows/probe.yml` |
| 版本 | 应用与 SDK 均为 `2.0.0`(四处同步:根 `pyproject.toml`、`sdk/pyproject.toml`、`sdk/harness_client/__init__.py`、`FastAPI(..., version=...)`;一致性已由 check_release 断言进 CI) | `python scripts/check_release.py` |
| 发布 | `CHANGELOG.md` 从 2.0.0 起向前记录;tag 命名 `v主.次.补` | `head -20 CHANGELOG.md` |

## 仓库地图

目录树本身与「每个目录的入口在哪」见仓根 [目录说明.md](目录说明.md)，本节只留职责与隐藏约束，两边不重复列目录。

| 路径 | 职责 | 关键点 |
| --- | --- | --- |
| `harness/` | 评测框架（领域无关） | `models.py` 数据结构 / `storage.py` 落盘与路径安全 / `runner.py` 重放 / `judge.py` 判分路由 / `report.py` 报告渲染 / `evolve.py` 自进化 / `activity.py` 看板时间流 |
| `pipeline/` | 被测对象 | `versions.py` 一处登记 `PIPELINES`/`CHANGELOG`；`data/*.json` 6 个情景数据集（数据即场景，代码不含工况） |
| `llm/` | LLM 层（可选装配） | `runtime.py` OpenAI 兼容 + Mock 降级、`judge.py` `conclusion_quality`、`workflows.py` 草稿/诊断、`store.py` 缓存+审计+草稿、`mocks.py` 离线确定性输出 |
| `webapp/` | HTTP 服务 + 前端 | `app.py` 全部端点与鉴权中间件、`auth.py` PBKDF2 口令 + HMAC 会话 + 登录限流、`settings.py` `.env` 读写与掩码、`static/index.html` 单文件看板（3199 行，含全部 JS）、`static/help.html` 文档中心、`static/sw.js` + `manifest.webmanifest` PWA |
| `cases/` | replaycase 库 | 按失败标签分目录，一个 case 一个 `<case_id>.json` |
| `evalsets/` | 评测集清单 | `{"evalset_id","description","created_at","case_ids"}`，`case_ids` 顺序即重放顺序 |
| `reports/` | 归档产物 | `report_<v>_<时间>.json`、`evolution_<时间>.json`、`report_evolution_<时间>.md` |
| `scripts/` | 命令行工具箱 | `seed_cases.py`、`seed_scenario_cases.py`、`run_eval.py`、`verify.py`、`backup.py`、`export_openapi.py`、`generate_pwa_icons.py`、`check_release.py`(版本同步+OpenAPI 漂移断言)、`probe_live.py`(线上只读探针) |
| `sdk/` | 官方 Python SDK | `harness_client/`（client/models/cli/errors），`dist/` 下的 wheel 与 sdist 按约定入库 |
| `miniprogram/` | 微信小程序 | 4 个 Tab + 5 个二级页，`utils/api.js` 统一带 `Authorization: Bearer` 会话令牌 |
| `tests/` | 测试 | `conftest.py` 夹具把资产目录与 `.env`、`auth.json` 全隔离到临时目录 |
| `docs/` | 人读参考 | `API.md`（逐端点）、`INTEGRATION.md`、`LLM.md`、`openapi.json`（生成物）、`images/`（README 截图） |
| `Dockerfile` / `docker-compose.yml` / `docs/DEPLOY.md` | 部署 | 容器非 root（UID 1000）、`/api/health` 健康检查、四个数据卷 |
| `.github/workflows/ci.yml` | CI | Python 3.11/3.12 矩阵,ruff + pytest + verify + check_release;`probe.yml` 每天只读探线上健康 |

## 架构与数据流

（原独立总览文档里的分层图与三条数据流并入本节。）

五个板块 + 三份资产：

```
┌─────────────────────────────────────────────────────────────┐
│  客户端：webapp/static（PWA 看板）· miniprogram（小程序）· scripts（CLI） │
├─────────────────────────────────────────────────────────────┤
│  HTTP API 层：webapp/app.py（FastAPI）+ auth.py（鉴权）+ settings.py（配置）│
├──────────────────────────────┬──────────────────────────────┤
│  harness/（评测框架，领域无关）│  llm/（LLM 智能层，可选、可降级）           │
│  models / storage / runner    │  runtime / judge / workflows      │
│  judge / report / evolve      │  store / mocks                    │
├──────────────────────────────┴──────────────────────────────┤
│  被测对象：pipeline/versions.py（v0 → v1 → v2 → v3）+ pipeline/data/（6 情景）│
├─────────────────────────────────────────────────────────────┤
│  评测资产（全量落盘 JSON，git 友好）：cases/ · evalsets/ · reports/         │
└─────────────────────────────────────────────────────────────┘
```

分层的三条硬约束：

- `harness/` 不 import `pipeline/`、`llm/`、`webapp/`。评测框架只依赖自己的 models；
  被测管线靠「版本登记」注入，判分器靠 `BaseJudge` 接口注入。
- `llm/` 是增强层不是依赖层：任何 LLM 功能失败都有确定性降级路径，不配 Key 系统照常跑。
- 三端客户端只走 HTTP API，不直接 import 后端模块（小程序天然如此，SDK 也是）。

一次闭环的三段旅程：

```
沉淀 case（第 1–2 步）
  用户反馈 → 看板「Case 管理」表单 / 小程序提交 / POST /api/cases
          → （可选）AI 草稿 POST /api/llm/drafts → 人工确认才入库
          → cases/<标签>/rc-xxxx.json，同时追加进 evalsets 清单

跑评测（第 3 步）
  scripts/run_eval.py --version v2 / 看板「运行评测」/ POST /api/eval/run
  → runner 重放 evalset 全部 case → pipeline/versions.py 出分析结果
  → judge 按 case.checks 逐条判分 → reports/report_<v>_<ts>.json 归档

自进化（第 4–6 步）
  python -m harness.evolve / 看板「运行完整自进化循环」/ POST /api/evolve/run
  → 测基线 v0 → 逐版本验证：提升且无回归才合入，收益 <5% 即停，最多 2 轮
  → reports/evolution_<ts>.json + report_evolution_<ts>.md 归档
  → 看板「版本对比」GET /api/compare 看逐 case 差分
```

## 鉴权事实（照 `webapp/app.py` 的 `auth_middleware` 写，不要凭印象改）

`AUTH_MODE=open` 时全部放行（仅内网演示）。否则对 `/api/*` 依次判定:

0. **初始口令门禁在最前**:`_AUTH_STORE` 的 `default_credentials` 为 true 时,
   除 `/api/health` 与 `/api/auth/*` 外的全部 `/api/*` 一律 `403`(先于凭据裁决,
   令牌与已登录会话同样被挡)。部署者必须先改掉初始口令(看板「改密」或
   `POST /api/auth/password`),或在启动环境设 `ADMIN_PASSWORD` 后重启 ——
   语义见 `webapp/auth.py`:环境变量提供即视为已设置(false);
   随机生成只打印一次(true,门禁开启);存量默认口令部署重启时提供环境变量即自动轮换;
1. **豁免在前**:非 `/api/` 路径、`/api/auth/*`、`/api/health`、`/api/settings` 直接放行 ——
   `/api/settings` 刻意不被通用 401 挡掉,由端点自己 `_settings_actor()` 做更严的裁决
   (但它仍受第 0 条门禁约束);
2. **凭据按序裁决,任一通过即放行**:
   1. `X-API-Token: <AUTH_TOKEN>` —— 机器令牌(SDK / 脚本 / CI),用 `hmac.compare_digest` 比较;
      短于 16 字符的取值在启动时直接拒绝(`__main__` 段);
   3. `Authorization: Bearer <会话令牌>` —— 小程序等带不了 Cookie 的客户端;
   4. `harness_session` Cookie —— 网页看板(HttpOnly、`SameSite=lax`、7 天)。
   后两者是**同一枚** HMAC 签名令牌(载荷 `用户名.过期时间`),签发与校验只在 `webapp/auth.py`;
3. 三条都不通过 → `401 {"detail":"未登录或会话已过期"}`。

`/api/settings` 只认两种身份:已鉴权会话(Bearer 或 Cookie)**或本机直连**。
它**故意不认机器令牌** —— 那枚 `AUTH_TOKEN` 与小程序等客户端共用,认它就等于把
「改服务器配置(含换令牌、看密钥)」交给任何令牌持有者。
「本机直连」= TCP 对端是回环地址且请求不带 `Forwarded`/`X-Forwarded-For`/`X-Real-IP`
(反代之后对端恒为 `127.0.0.1`,所以经代理的请求一律要求会话)。
未开 `SETTINGS_ENABLED=1` 时恒为 `403`。
未处理异常由 `on_unhandled` 兜底:客户端只收到通用 500 文案,异常细节只进服务端日志。

## 关键约定（违反会出问题的才写）

1. **架构分层不许反向依赖**：`harness/` 不 import `pipeline/`、`llm/`、`webapp/`；
   被测管线靠 `PIPELINES` 注册表注入，判分器靠 `BaseJudge` 子类注入。
   破坏它就没有「框架与领域解耦可迁移」这条卖点，`CompositeJudge` 的懒加载降级也会失效。
2. **LLM 只有增强、必须可降级**：`llm/runtime.py` 未配 `LLM_BASE_URL`+`LLM_API_KEY` 时返回
   `MockLLMRuntime`；`CompositeJudge` 里 LLM judge 导入失败即退回纯规则判分；
   `llm/judge.py` 任何异常都记「未通过 + 原因」而不抛出。
   **只有全程离线 Mock 下结果确定，才叫确定性**：任何要求联网才能过的测试或校验都不许进 CI。
3. **评测资产用 `tests/fixtures/` 的冻结快照，不用真实 `cases/`**：`conftest.seed_asset_dirs()`
   把 `tests/fixtures/cases|evalsets` 拷进 `tmp_path` 再 monkeypatch `storage` 的三个目录。
   夹具比真实库多一条 `rc-0014`（用于断言「沉淀后编号递增」），所以 17 个 fixture 文件 ≠ 18 条生产 case，
   别把它们当成同一份数据、也别让测试去读 `cases/`。
4. **OpenAPI / SDK / 文档不许互相漂移**：端点改动后同一次提交里
   `python scripts/export_openapi.py`（重写 `docs/openapi.json`）→ 改 `docs/API.md` →
   改 `sdk/harness_client/client.py` 与 `webapp/static/help.html` → 跑 `python -m pytest tests/test_sdk.py` 之外再跑全量。
   `docs/API.md` 与 `static/help.html` 是同构内容的两份载体，改一份必须改另一份。
5. **产物文件名带版本前缀**：`report_v2_20260920T213232.json`。`storage.save_report()` 用
   `timestamp` 去掉 `-` 与 `:`（于是有 `T` 没有分隔符），前缀 `report_<version>_` 是
   `list_reports()` / `verify.py` / 看板对比认得的唯一筛选条件（glob `report_*.json`），
   去掉前缀会让归档混在一起、`/api/compare` 拿不到配对。
6. **报告类产物不手改、`reports/` 只由运行生成**；`drafts/`、`llm_cache/`、`llm_runs.jsonl`
   是运行期产物且已在 `.gitignore`（前导斜杠只匹配仓库根，否则会连带吞掉 `miniprogram/pages/drafts/`）。
7. **路径与标签一律过白名单**：外部传入的数据集名 / 评测集名 / 报告 ID / 进化 ID 走
   `storage._safe_name()`，失败标签走 `storage.safe_label()`（用作目录名）。
   新增「按名字拼路径」的接口必须复用它们，否则等于开一个 `../` 穿越口（有测试断言）。
8. **写盘都是「临时文件 + `os.replace`」**，复合操作在进程锁内：
   `_CASE_LOCK`（沉淀 + 加入评测集，避免并发生成重复 `case_id`）、`_EVOLVE_LOCK`
   （非阻塞获取，冲突直接 `409`）、`storage._LOCK`、`settings_mod._WRITE_LOCK`。
   多进程部署时这些锁不跨进程，别指望它们保证一致性。
9. **删除 case 必须同步评测集清单**：`storage.delete_case()` 在同一把锁里从所有
   `evalsets/*.json` 移除该 id；`load_evalset_cases()` 遇悬空引用直接 `KeyError`（API 转 400），
   别让清单能指向不存在的用例。
10. **迭代纪律不许放宽**：单轮上限 `EVOLVE_MAX_ROUNDS`（默认 2）、
    收益 <5% 且无新通过即停、回归一票否决、未验证版本显式进 `pending_versions`。
    放宽上限等于放弃「每轮只改一类问题」的纪律。

## 常见任务 → 改哪里

（原独立总览文档里的位置安排表并入此处；改完之后跑什么见下一节。）

| 我想… | 去这里 | 备注 |
| --- | --- | --- |
| 改进分析算法 / 出新版本 | `pipeline/versions.py` | 新增函数 + 在版本注册表登记一行，看板与 CLI 立即可见 |
| 加数据集 / 改工况参数 | `pipeline/data/*.json` | 容量、流量、车速都是数据，管线零改动 |
| 加判分检查类型 | `harness/judge.py` + `harness/models.py` | 新 `type` 要在两个文件同步，并补 `tests/test_judge.py` |
| 加 API 端点 | `webapp/app.py` | 之后 `python scripts/export_openapi.py` 重导，并同步 `docs/API.md` 与 `static/help.html` |
| 改看板页面 / 加前端功能 | `webapp/static/index.html` | 3199 行的单文件应用，无构建步骤 |
| 换 Logo / PWA 图标 | `webapp/static/assets/icon.svg` → `python scripts/generate_pwa_icons.py` | 全套图标从这张 SVG 母版栅格化 |
| 加 LLM 能力（新工作流） | `llm/workflows.py` | 强制 JSON Schema + 必须有降级路径，设计原则见 `docs/LLM.md` |
| 接入别的 LLM 供应商 | 只改环境变量，无需动代码 | 任意 OpenAI 兼容端点，见 `.env.example` |
| 沉淀首批种子 case / 重置资产 | `python scripts/seed_cases.py` | 雨天场景另用 `seed_scenario_cases.py` |
| 备份评测资产 | `python scripts/backup.py` | 打包 `cases/`、`evalsets/`、`reports/` |
| 部署 / 更新公网 | 见 [DEPLOY.md](docs/DEPLOY.md) | Docker 路线一条命令，小程序发布清单也在里面 |

## 改动后的验证

| 你动了 | 必须跑 |
| --- | --- |
| `pipeline/versions.py`（含新增 v3 与 CHANGELOG） | `python scripts/verify.py` + `python -m pytest tests/test_versions.py tests/test_evolve.py -q` |
| `pipeline/data/*.json` | `python scripts/verify.py`（第 [5] 组是数值抽查，改了数据要同步期望值） |
| `cases/`、`evalsets/`、`tests/fixtures/` | `python -m pytest tests/test_storage.py -q` + `python scripts/verify.py` |
| `harness/judge.py`、`harness/models.py` | `python -m pytest tests/test_judge.py tests/test_models.py -q` |
| `harness/evolve.py`、`harness/report.py` | `python -m pytest tests/test_evolve.py tests/test_report.py -q` + `python -m harness.evolve` |
| `webapp/auth.py`、鉴权中间件、初始口令门禁 | `python -m pytest tests/test_webapp.py tests/test_auth.py tests/test_settings_api.py -q`,再手动开一次服务过一遍看板(含「改密前 403 → 改密后放行」) |
| 版本号 / `docs/openapi.json` | `python scripts/check_release.py`(版本同步 + 漂移断言) |
| `webapp/settings.py` 的键元数据 | `python -m pytest tests/test_settings_api.py -q` + 更新 `.env.example` 与看板「设置」页说明 |
| 任何端点/请求体字段 | `python scripts/export_openapi.py` 重导 + 同步 `docs/API.md`、`webapp/static/help.html`、`sdk/`（见关键约定 4） |
| `sdk/harness_client/*` | `python -m pip install ./sdk` 后 `python -m pytest tests/test_sdk.py -q` |
| `webapp/static/**`（前端与 PWA） | `python -m pytest tests/test_pwa.py -q`（校验 manifest/SW/图标）+ 浏览器手测；改图标则 `python scripts/generate_pwa_icons.py` |
| `llm/*` | `python -m pytest tests/test_llm.py -q`（全程离线 Mock） |
| 任何代码 | `ruff check .` + `python -m pytest` + `python scripts/verify.py` + `python scripts/check_release.py`(CI 就这四条) |

## 已知坑

- **裸 `pytest` 与 `python -m pytest` 的 `sys.path` 不同**：`python -m pytest` 会把当前目录放进
  `sys.path`，裸 `pytest` 不会。这一行 `pythonpath = ["."]`（`pyproject.toml` 的
  `[tool.pytest.ini_options]`）是修这个问题的：缺了它，`tests/` 全部模块在收集期
  `ModuleNotFoundError: No module named 'harness'`，退出码 2，CI 里表现为「装完依赖仍然一条测试都没跑起来」。
  别再删掉或改成靠 `conftest.py` 里 `sys.path.insert` 单点兜底 —— `conftest.py` 自己也需要先被导入。
- **`tests/test_sdk.py` 曾单独跑失败,已修(1.6.0)**:`server_url` 夹具现在在导入
  `webapp.app` 前后把 `AUTH_FILE` 与模块级 `_AUTH_STORE` 换到临时文件再还原;
  别把这个隔离拆掉,否则单跑又会读到本机真实 `webapp/auth.json` 而 401。
- **本机 `webapp/auth.json` 的 `default_credentials` 已随 1.6.0 的轮换通道翻转为 false**
  (本地 `.env` 提供了 `ADMIN_PASSWORD` 并重启过一次);`/api/health` 会原样回显这个布尔,
  它为 true 表示「初始口令未改、业务接口处于 403 门禁状态」,线上是否收口以探针为准。
- **Windows 控制台/管道编码**：脚本自身有 `sys.stdout.reconfigure(encoding="utf-8")`，
  但没走这条的进程（例如你新写的脚本、或 `webapp/app.py` 的 banner）在 GBK 控制台里经管道会被
  重新解码成乱码。捕获输出前 `set PYTHONIOENCODING=utf-8`。
- **`python -m harness.evolve`、`scripts/run_eval.py`、`POST /api/eval/run` 都会往 `reports/` 写文件**，
  `POST /api/evolve/run` 还会长驻 `evolution_*.json` + `.md`。在干净工作区里试跑之后，
  要么一起提交（归档即历史），要么把新增文件删干净再提交，别留下半套不一致的归档。
- **`/api/settings` 默认关闭**：看板「设置」页会得到
  `403 运行时配置接口未启用:...`；不要为了让页面能用而把 `SETTINGS_ENABLED` 写进仓库里的任何文件。
- **`ruff` 的 `per-file-ignores`**：`webapp/app.py`、`scripts/*.py`、`tests/conftest.py` 允许 `E402`
  （它们先把仓库根插入 `sys.path` 再 import 项目包，是刻意的运行模式）。别为了「干净」去调顺序，
  那会让裸脚本运行方式失效。
- 2026-10-05 已清理：根目录 `batch_demo_ids.txt`（批量删除演示遗留）与 `cases/未分类/`、
  `cases/批量演示/` 两个空目录。`storage.safe_label()` 对空标签仍兜底返回 `未分类`，
  真有空标签沉淀时目录会自动重建，无需手工预建。

## 不要做的事

- 不要放宽 `MIN_IMPROVEMENT`（5%）、`EVOLVE_MAX_ROUNDS`（2）或把回归一票否决改成警告 ——
  这三条是这个仓库存在的理由。
- 不要给文档、产物、日志加时间戳之外的可变值去制造 diff；不要把 `reports/`、`drafts/`、
  `llm_cache/`、`llm_runs.jsonl` 当源码修（它们是运行产物，`verify.py` 只读不写）。
- 不要在文档里写公网 IP、真实令牌值、`AUTH_TOKEN`/口令的实际取值；示例一律
  `<你的服务地址>`、`<AUTH_TOKEN>`、`<你的口令>`。`webapp/auth.json`、`.env`、
  `miniprogram/config.js`、`启动后端.bat` 已 gitignore，但不要把它们的内容摘进文档。
- 不要新增第二个会话格式或第二套判分入口：会话签发只在 `webapp/auth.py`，
  凭据裁决只在 `webapp/app.py` 的中间件；检查类型路由只在 `CompositeJudge._route`。
- 不要为了「测起来方便」让测试读真实 `cases/`、`evalsets/`、`.env`、`webapp/auth.json` ——
  用 `hermetic_storage` / `make_client` / `_hermetic_dotenv` 夹具。
- 不要把机器令牌加进 `/api/settings` 的准入条件，也不要在这给 SDK 开口子。
- 不要只改 `docs/API.md` 或只改 `webapp/static/help.html` 其中一份，也不要手改 `docs/openapi.json`。

## 延伸阅读

上手与故障排查 [docs/getting-started.md](docs/getting-started.md) · 架构决策的理由
[ARCHITECTURE.md](docs/ARCHITECTURE.md) · 逐端点参考 [docs/API.md](docs/API.md) · 程序化接入 [docs/INTEGRATION.md](docs/INTEGRATION.md) ·
LLM 设计 [docs/LLM.md](docs/LLM.md) · 部署 [DEPLOY.md](docs/DEPLOY.md) ·
各目录说明 `harness/README.md`、`pipeline/README.md`、`llm/README.md`、`webapp/README.md`、
`scripts/README.md`、`cases/README.md`、`evalsets/README.md`、`sdk/README.md`、
`miniprogram/README.md`、`tests/README.md`。
