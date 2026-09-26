# PROJECT OVERVIEW · 项目整体说明

> 拿到项目的第一份地图:项目是什么、分几个板块、每个板块在哪、互相怎么连接、
> 常见任务该改哪个文件。读完这一篇即可建立整体认知,细节再按文末「文档地图」深入。

---

## 1. 项目是什么(整体功能)

**Transportation Harness** 是一套「交通分析自进化评测系统」,把大模型时代的
**评测驱动迭代(Eval-Driven Iteration)** 工程方法论落地到交通分析领域:

```
线上 badcase ──沉淀──▶ 可重放 replaycase ──组成──▶ 版本化评测集
                                                      │
        ▲                                             ▼
        └──新的 badcase 继续回流 ◀── 评测 → 定位失败 → 迭代管线 → 回归验证
```

- **一句话**:badcase 不再流失,而是沉淀为可重放、可版本化、可自动判分的评测资产;
  用「评测 → 定位 → 迭代 → 回归验证」的闭环驱动分析管线持续进化。
- **实测效果**:管线得分从 **7.7%(v0)→ 84.6%(v1)→ 100%(v2)**,全程零回归,
  每一轮的逐 case 差分与得分曲线都归档在 `reports/` 可回溯。
- **领域无关**:核心评测框架 `harness/` 与「交通」完全解耦 —— 换成代码评审、
  医疗问答、客服话术,闭环同样成立。
- **双客户端 + 平台化**:Web 看板(PWA,可安装可离线)、微信小程序、CLI 三端共用
  同一套 HTTP API;提供 OpenAPI 3.1 规范与官方 Python SDK 供程序化接入。
- **LLM 智能层(可选)**:坏例沉淀助手、LLM-as-Judge、失败诊断双智能体;
  不配置 Key 自动降级为确定性 Mock,离线可复现、CI 免密钥。

---

## 2. 架构总览:五个板块 + 三份资产

```
┌─────────────────────────────────────────────────────────────┐
│  客户端:webapp/static(PWA 看板) · miniprogram(小程序) · scripts(CLI) │
├─────────────────────────────────────────────────────────────┤
│  HTTP API 层:webapp/app.py(FastAPI)+ auth.py(鉴权)+ settings.py(配置)  │
├──────────────────────────────┬──────────────────────────────┤
│  harness/(评测框架,领域无关) │  llm/(LLM 智能层,可选、可降级)        │
│  models / storage / runner    │  runtime / judge / workflows      │
│  judge / report / evolve      │  store / mocks                    │
├──────────────────────────────┴──────────────────────────────┤
│  被测对象:pipeline/versions.py(v0 → v1 → v2)+ pipeline/data/(6 情景)      │
├─────────────────────────────────────────────────────────────┤
│  评测资产(全量落盘 JSON,git 友好):cases/ · evalsets/ · reports/           │
└─────────────────────────────────────────────────────────────┘
```

**分层的关键约束**(改动时请遵守):

- `harness/` 不 import `pipeline/`、`llm/`、`webapp/` —— 评测框架只依赖自己的 models;
  被测管线通过「版本登记」注入,判分器通过 `BaseJudge` 接口注入。
- `llm/` 是增强层不是依赖层:任何 LLM 功能失败都有确定性降级路径,关掉 Key 系统照常跑。
- 三端客户端只走 HTTP API,不直接 import 后端模块(小程序天然如此,SDK 也是)。

---

## 3. 板块地图:每个目录是什么、在哪、干什么

| 位置 | 板块 | 职责 | 关键文件 |
| --- | --- | --- | --- |
| `harness/` | **评测框架(核心)** | 与领域无关的「case → 重放 → 判分 → 报告 → 自进化」引擎 | 见下表 ↓ |
| `pipeline/` | **被测对象** | 交通拥堵分析管线,三个版本的算法实现与 CHANGELOG | `versions.py`(一处登记,看板自动识别) |
| `pipeline/data/` | 情景数据集 | 6 种工况:常规早高峰 / 雨天 / 事故占道 / 晚高峰 / 缺失数据 / 空数据 | `base.json` 等,加数据集不改代码 |
| `llm/` | **LLM 智能层** | 七维克制集成:坏例沉淀助手、LLM-as-Judge、失败诊断 | 设计文档 `docs/LLM.md` |
| `webapp/` | **Web 服务端 + 前端** | FastAPI 后端(全部 API)+ 单文件 PWA 前端 | 见下表 ↓ |
| `sdk/` | **官方 Python SDK** | `pip install ./sdk`,导入名 `harness_client`,带 CLI | `pip install ./sdk` 后 `harness-client --help` |
| `miniprogram/` | **微信小程序客户端** | 4 Tab:评测看板 / 分析提交 / Case 库 / 版本对比,外业现场提交 badcase | `config.js`(API 地址与令牌) |
| `scripts/` | **CLI 工具箱** | 种子沉淀、评测、校验、备份、OpenAPI 导出、图标生成 | 逐个见 §6 |
| `tests/` | **测试** | 190 个 pytest 用例:单元 + 接口 + 闭环 + LLM + PWA + SDK | `pytest` 一键运行,夹具用临时目录隔离(含 .env) |
| `docs/` | **文档中心(仓库版)** | API 参考、接入指南、LLM 设计、OpenAPI 规范 | 与运行实例 `/help` 内容同构 |
| `cases/` | **评测资产:case 库** | 16 条 replaycase,按失败标签分目录(阈值错误/健壮性/精度问题…) | 一 case 一 JSON,可直接阅读 |
| `evalsets/` | **评测资产:评测集** | 版本化清单:evalset_v1(13 条)+ evalset_scenario_rain(雨天 3 条) | 纯 case_id 列表 |
| `reports/` | **评测资产:归档** | 每次评测/自进化自动归档:JSON 明细 + Markdown 总报告 | 最新 `report_evolution_*.md` 即进化全史 |
| `.github/workflows/ci.yml` | CI | ruff + pytest + 端到端校验,Python 3.11/3.12 矩阵 | push 自动跑 |
| `Dockerfile` / `docker-compose.yml` | 部署 | 非 root 容器 + 健康检查 + 数据卷(升级不丢资产) | `docker compose up -d --build` |

### harness/ 内部六个文件(评测框架核心)

| 文件 | 职责 |
| --- | --- |
| `models.py` | 数据结构:`ReplayCase`(输入+期望+判分规则)/ `CaseResult` / `EvalResult` |
| `storage.py` | `cases/`、`evalsets/`、`reports/` 读写:原子写入 + 加锁 + 路径安全校验 |
| `runner.py` | 重放引擎:批量重放 case → 调管线 → 交判分器 → 汇总 `EvalResult` |
| `judge.py` | 判分器:规则 judge(6 种检查类型)+ 启发式 judge + `BaseJudge` 可插拔接口 |
| `report.py` | Markdown / JSON 双格式报告渲染 |
| `evolve.py` | 自进化主流程:基线 → 逐登记版本验证「提升且无回归」→ 最多 2 轮 → 归档 |

### webapp/ 内部组成

| 文件 | 职责 |
| --- | --- |
| `app.py` | FastAPI 全部端点:鉴权 / 分析提交 / case 沉淀 / 评测 / 一键自进化 / 对比 / LLM / 运行时配置 |
| `auth.py` | 本地账号体系:PBKDF2 口令哈希 + HMAC 会话令牌(Cookie 或 Bearer)+ 登录失败限流 |
| `settings.py` | 运行时配置(.env)读写:键元数据、密钥掩码、值校验、原子写 + 写前备份 |
| `static/index.html` | 应用壳(单文件、零外部依赖):欢迎页 + 登录 + 三栏工作台 + 常驻 AI 面板 |
| `static/help.html` | 文档中心(`/help`):核心概念 / 工作流 / 全量 API 参考 / 错误码 |
| `static/sw.js` + `manifest.webmanifest` + `assets/` | PWA:壳预缓存、API network-first、图标四件套 |

---

## 4. 数据流:一次评测与一次自进化的完整旅程

**沉淀一条 case(闭环第 1–2 步)**

```
用户反馈 → 看板「Case 管理」表单 或 小程序提交 或 POST /api/cases
        → (可选)AI 草稿:POST /api/llm/drafts → 人工确认才入库
        → cases/<标签>/rc-xxxx.json + 同步追加进 evalsets 清单
```

**跑一次评测(闭环第 3 步)**

```
python scripts/run_eval.py --version v2   或  看板「运行评测」/ POST /api/eval/run
→ runner 重放 evalset 全部 case → pipeline/versions.py 出分析结果
→ judge 按 case.checks 逐条判分 → reports/report_<v>_<ts>.json 归档
```

**跑一次自进化(闭环第 4–6 步)**

```
python -m harness.evolve  或  看板「运行完整自进化循环」/ POST /api/evolve/run
→ 测基线 v0 → 逐版本验证:提升且无回归才合入,收益 <5% 即停,最多 2 轮
→ reports/evolution_<ts>.json + report_evolution_<ts>.md 归档
→ 看板「版本对比 /api/compare」看逐 case 差分
```

---

## 5. 位置安排:常见任务 → 改哪里

| 我想… | 去这里 | 备注 |
| --- | --- | --- |
| 改进分析算法 / 出新版本 | `pipeline/versions.py` | 新增函数 + 在版本注册表登记一行,看板/CLI 立即可见 |
| 加数据集 / 改工况参数 | `pipeline/data/*.json` | 容量/流量/车速都是数据,管线零改动 |
| 加判分检查类型 | `harness/judge.py` + `harness/models.py` | 新 type 在两个文件同步;补 `tests/test_judge.py` |
| 加 API 端点 | `webapp/app.py` | 之后跑 `python scripts/export_openapi.py` 重新导出规范,并同步 `docs/API.md` 与 `static/help.html` |
| 改前端页面 / 加看板功能 | `webapp/static/index.html` | 单文件应用;改图标另见下一行 |
| 换 Logo / PWA 图标 | `webapp/static/assets/icon.svg` → `python scripts/generate_pwa_icons.py` | 从 SVG 母版栅格化全套图标 |
| 加 LLM 能力(新工作流) | `llm/workflows.py` | 强制 JSON Schema + 降级路径;设计原则见 `docs/LLM.md` |
| 接入别的 LLM 供应商 | 环境变量即可,无需改代码 | 任意 OpenAI 兼容端点,见 `.env.example` |
| 加测试 | `tests/test_*.py` | 用 `hermetic_storage` 夹具,不污染真实评测资产 |
| 沉淀首批种子 case | `python scripts/seed_cases.py` | 重置种子与评测集;雨天场景另用 `seed_scenario_cases.py` |
| 校验端到端不变量 | `python scripts/verify.py` | 种子行为冻结 + 通过集单调不减,评测集增长后依然可用 |
| 备份评测资产 | `python scripts/backup.py` | 打包 cases/evalsets/reports |
| 部署 / 更新公网 | `DEPLOY.md` | Docker 路线一条命令,小程序发布清单在内 |

---

## 6. scripts/ 工具箱速查

| 命令 | 作用 |
| --- | --- |
| `python scripts/seed_cases.py` | 沉淀 13 条种子 replaycase + 生成 evalset_v1 |
| `python scripts/seed_scenario_cases.py` | 沉淀雨天场景评测集 evalset_scenario_rain |
| `python scripts/run_eval.py --version v1 --md` | 单版本评测,输出 Markdown 报告 |
| `python -m harness.evolve` | 一键自进化(v0 → v1 → v2 全流程) |
| `python scripts/verify.py` | 端到端不变量校验(预期 VERIFY PASS) |
| `python scripts/backup.py` | 评测资产一键打包备份 |
| `python scripts/export_openapi.py` | 导出 OpenAPI 3.1 规范 → `docs/openapi.json` |
| `python scripts/generate_pwa_icons.py` | SVG 母版 → PWA 图标全套(resvg) |

---

## 7. 新人上手路径

**10 分钟跑通(零配置,离线可用)**

```bash
pip install -r requirements.txt
python -m harness.evolve        # 看 7.7% → 84.6% → 100% 的进化全程
python webapp/app.py            # 启动看板 http://127.0.0.1:8765(账号 admin;初始口令随机生成、只在控制台打印一次)
```

**半天读懂(建立工程认知)**

1. 读本文档 §2–§4,打开看板把每个页面点一遍(对照 §3 板块地图);
2. 读 `ARCHITECTURE.md`(设计决策与扩展点)与 `docs/LLM.md`(七维设计);
3. 跑 `pytest`(190 例)与 `python scripts/verify.py`,感受回归防护;
4. 挑一条 `cases/阈值错误/rc-0001.json` 读一遍,对照 `docs/API.md` 理解 checks 结构。

**接入自己的系统(一天内)**

- 程序化调用:`docs/INTEGRATION.md`(5 分钟接入)→ `pip install ./sdk`;
- 迁移到其它领域:换掉 `pipeline/`,保留 `harness/` 闭环 —— 框架与领域解耦;
- 部署上线:`DEPLOY.md` 三条路线(Docker 最快)。

---

## 8. 术语表

| 术语 | 含义 |
| --- | --- |
| **replaycase** | 一条可重放的坏例:输入(dataset)+ 期望结论 + 判分规则(checks),存于 `cases/` |
| **评测集(evalset)** | case_id 的版本化清单,存于 `evalsets/`;评测集可以按场景切分(如雨天) |
| **check** | 最小判分单元:`classify`(分级)/ `metric`(指标近似)/ `no_crash`(健壮性)/ `recommendations` / `congested_empty` / `conclusion_keyword` |
| **judge** | 执行 checks 的判分器;规则版离线确定性,LLM 版按评分细则打分,可插拔 |
| **标签(label)** | 失败类别(阈值错误 / 健壮性 / 精度问题…),用于聚类定位与目录分组 |
| **自进化(evolve)** | 基线测量 → 逐版本验证「提升且无回归」的迭代纪律,收益 <5% 即停,最多 2 轮 |
| **回归** | 新版本把原本通过的 case 改坏了;一票否决,不允许合入 |
| **AI 草稿(draft)** | LLM 从反馈原文生成的 case 草稿,**人工确认后才入库**,与手工沉淀同一校验路径 |

---

## 9. 文档地图(接下来读什么)

| 文档 | 内容 | 什么时候读 |
| --- | --- | --- |
| `README.md` | 项目门面:亮点、截图、快速开始、API 一览 | 第一眼 |
| **本文档** | 全景地图、板块功能、位置安排 | 拿到项目时 |
| `ARCHITECTURE.md` | 架构分层、关键设计决策、扩展点 | 想改架构/深入某模块前 |
| `docs/API.md` | 28 个端点的完整参考(与 `/help`、`/docs` 同构) | 对接 API 时 |
| `docs/INTEGRATION.md` | 5 分钟接入指南(cURL → SDK → 原生 HTTP) | 程序化调用前 |
| `docs/LLM.md` | LLM 智能层七维设计与治理边界 | 想启用/扩展 LLM 功能时 |
| `DEPLOY.md` | 公网部署三条路线 + 小程序发布清单 | 上线前 |
| `miniprogram/README.md` | 小程序配置与真机调试 | 用小程序前 |
| `sdk/README.md` | SDK 安装与用法 | 用 Python SDK 前 |
| `reports/report_evolution_*.md`(最新) | 完整进化轨迹:逐轮优化内容、得分、差分 | 想看「怎么从 7.7% 到 100%」 |
