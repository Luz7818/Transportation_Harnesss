# Transportation Harness 架构与设计决策

> 用途：给评审者与后续维护者。架构总览、数据流、仓库地图、鉴权事实、设计决策的理由与扩展点
> 都在这里。操作步骤在 `docs/GET-START.md`；数字口径在根目录 `AGENTS.md` 的「当前状态」；
> 逐端点参考在 `docs/API.md`。
> 本文件由原设计决策文档与 AGENTS 的架构节合并重写（2026-10-05），取舍理由未删。

## 架构总览

FastAPI 单进程服务 + 文件型评测资产的交通分析自进化评测系统：线上 badcase 沉淀为可重放
replaycase → 版本化评测集 → 逐版本验证「提升且无回归」→ 归档报告；配 PWA 看板、微信小程序、
Python SDK、CLI 四个客户端，默认全程离线确定性（LLM 走 Mock）。

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
├───────────────────────────────────────────────────────── ───┤
│  评测资产（全量落盘 JSON，git 友好）：cases/ · evalsets/ · reports/         │
└─────────────────────────────────────────────────────────────┘
```

分层的三条硬约束：

- `harness/` 不 import `pipeline/`、`llm/`、`webapp/`。评测框架只依赖自己的 models；
  被测管线靠「版本登记」注入，判分器靠 `BaseJudge` 接口注入。
- `llm/` 是增强层不是依赖层：任何 LLM 功能失败都有确定性降级路径，不配 Key 系统照常跑。
- 三端客户端只走 HTTP API，不直接 import 后端模块（小程序天然如此，SDK 也是）。

## 数据流：一次闭环的三段旅程

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

## 仓库地图

| 路径 | 职责 | 关键点 |
| --- | --- | --- |
| `harness/` | 评测框架（领域无关） | `paths.py`（项目根定位,exe 模式读 `HARNESS_HOME`）/ `models.py` / `storage.py` / `runner.py` / `judge.py` / `report.py` / `evolve.py` / `activity.py` |
| `pipeline/` | 被测对象 | `versions.py` 一处登记 `PIPELINES`/`CHANGELOG`；`data/*.json` 6 个情景数据集（数据即场景，代码不含工况） |
| `llm/` | LLM 层（可选装配） | `runtime.py`、`judge.py`（`conclusion_quality`）、`workflows.py`、`store.py`、`mocks.py` |
| `webapp/` | HTTP 服务 + 前端 | `app.py` 全部端点与鉴权中间件、`auth.py`、`settings.py`、`static/index.html` 单文件看板（3354 行）、`static/help.html`、`sw.js` PWA |
| `cases/` | replaycase 库 | 按失败标签分目录，一 case 一 JSON |
| `evalsets/` | 评测集清单 | `case_ids` 顺序即重放顺序 |
| `reports/` | 归档产物 | `report_<v>_<时间>.json`、`evolution_*.json`、`report_evolution_*.md` |
| `scripts/` | 命令行工具箱 | seed / run_eval / verify / backup / export_openapi / generate_pwa_icons / check_release / probe_live |
| `sdk/` | 官方 Python SDK | `harness_client/`；`dist/` 下 wheel 按约定入库 |
| `miniprogram/` | 微信小程序 | 4 Tab + 5 二级页，统一 Bearer 会话令牌 |
| `tests/` | 测试 | `conftest.py` 把资产目录与 `.env`、`auth.json` 全隔离到临时目录 |
| `docs/` | 人读参考 | `API.md`、`INTEGRATION.md`、`LLM.md`、`DEPLOY.md`、`openapi.json`（生成物）、`images/` |
| `Dockerfile` / `docker-compose.yml` | 部署 | 非 root（UID 1000）、`/api/health` 健康检查、四个数据卷 |
| `.github/workflows/` | CI 与探针 | `ci.yml`（ruff + pytest + verify + check_release）；`probe.yml` 每天只读探线上健康 |

## 鉴权事实（照 `webapp/app.py` 的 `auth_middleware` 写，不要凭印象改）

`AUTH_MODE=open` 时全部放行（仅内网演示）。否则对 `/api/*` 依次判定:

0. **初始口令门禁在最前**:`_AUTH_STORE` 的 `default_credentials` 为 true 时,
   除 `/api/health` 与 `/api/auth/*` 外的全部 `/api/*` 一律 `403`(先于凭据裁决)。
   部署者必须先改掉初始口令,或在启动环境设 `ADMIN_PASSWORD` 后重启;
   存量默认口令部署重启时提供环境变量即自动轮换;
1. **豁免在前**:非 `/api/` 路径、`/api/auth/*`、`/api/health`、`/api/settings` 直接放行 ——
   `/api/settings` 刻意不被通用 401 挡掉,由端点自己做更严的裁决(仍受第 0 条约束);
2. **凭据按序裁决,任一通过即放行**:
   1. `X-API-Token: <AUTH_TOKEN>` —— 机器令牌,`hmac.compare_digest` 比较;短于 16 字符启动即拒;
   2. `Authorization: Bearer <会话令牌>` —— 小程序等带不了 Cookie 的客户端;
   3. `harness_session` Cookie —— 网页看板(HttpOnly、`SameSite=lax`、7 天)。
   后两者是**同一枚** HMAC 签名令牌,签发与校验只在 `webapp/auth.py`;
3. 三条都不通过 → `401 {"detail":"未登录或会话已过期"}`。

`/api/settings` 只认两种身份:已鉴权会话(Bearer 或 Cookie)**或本机直连**。
它**故意不认机器令牌** —— 认它等于把「改服务器配置(含换令牌、看密钥)」交给任何令牌持有者。
「本机直连」= TCP 对端是回环地址且请求不带 `Forwarded`/`X-Forwarded-For`/`X-Real-IP`
(反代之后对端恒为 `127.0.0.1`,所以经代理的请求一律要求会话)。
未开 `SETTINGS_ENABLED=1` 时恒为 `403`。
未处理异常由 `on_unhandled` 兜底:客户端只收到通用 500 文案,异常细节只进服务端日志。

## 设计决策：为什么这样设计

### 1. 分层:被测对象与评测框架严格解耦

解耦协议极简:被测对象只需要满足 `analyze(segments: list[dict]) -> dict`,harness 对其内部
实现零感知。换来两个能力:**多版本共存**（`PIPELINES` 注册表把版本名映射到函数,新增 v3 只是
注册表加一行）;**场景零成本**（雨天/事故/晚高峰全部建模在数据集参数里,同一份 v2 管线不做任何
修改即可被 `evalset_scenario_rain` 检验 —— 场景属于数据,不属于代码）。

### 2. replaycase:输入、期望与判分规则三位一体

一条 case 是「可重放的最小评测单元」:`dataset_name`（输入）+ `checks`（怎样算修好）+
`label`/`source`（聚类与溯源）。

**为什么判分规则(checks)存在 case 里而不是 judge 里**:判分标准是这个 badcase 的业务语义
的一部分 —— 同一个「拥堵判定」问题,有的 case 要求等级精确相等,有的只要求指标在容差内。
规则跟着 case 走,沉淀 case 的人(可能不是写 judge 的人)才能完整表达「什么是对的」。

**为什么按失败标签分目录**:失败标签是定位迭代方向的第一手聚类信息,物理分目录让 `ls` 和
git diff 都能直接回答「这轮修了哪类问题」。

### 3. 自进化纪律:把工程纪律写进代码

`harness/evolve.py` 把迭代纪律固化为可执行流程:基线可配、版本派生;单轮迭代上限（默认 2,
`EVOLVE_MAX_ROUNDS` 可调）防止无限递归,因上限未验证的版本显式进 `pending_versions` 绝不静默
丢弃;收益递减停止（<5% 且无新通过即停）;回归一票否决。运行产物全部归档,
`reports/evolution_*.json` 是这段优化过程的「黑匣子记录」,看板时间线可直接回放。

### 4. 判分器:规则优先,LLM 兜底,接口可插拔

```
BaseJudge(抽象)── RuleJudge        classify / metric / no_crash / recommendations / congested_empty
              └─ HeuristicJudge   conclusion_keyword(关键词覆盖,离线确定性)
CompositeJudge                       按 spec.type 路由,无主 judge 支持时该检查判失败
```

确定性规则能判的绝不交给模型;文本质量留给 LLM(`BaseJudge` 接口接入);判分器自身可测试
（`tests/test_judge.py` 对每条规则语义都有断言）。

### 5. 存储与并发:评测资产是核心资产

- **一切皆 JSON 文件**:git 可管、人工可读、拷贝目录即迁移,不引入数据库是有意为之;
- **原子写**:先写 `.tmp` 再 `os.replace`;
- **复合操作加锁**:「沉淀 case + 加入评测集」、自进化全库读写都在进程锁内串行化;
  自进化用非阻塞锁,重复触发直接 409;
- **路径安全**:外部标识符统一过 `_safe_name()` 白名单,从源头杜绝 `../` 穿越;
- **清单一致性**:删除 case 同步从所有评测集移除(同一把锁内),评测集永不悬空。

### 6. 安全设计(公网部署的前提)

| 威胁 | 对策 |
| --- | --- |
| 口令泄露 | PBKDF2-HMAC-SHA256,salt 随机 + 12 万次迭代;历史单轮哈希透明升级 |
| 口令暴力破解 | 连续失败 5 次锁定 10 分钟;不存在用户名也执行等时哈希 |
| 会话伪造 | HMAC-SHA256 签名令牌,HttpOnly + SameSite Cookie |
| API 令牌侧信道 | `hmac.compare_digest` 消除逐字节短路时间差 |
| 路径穿越 | 拼路径的外部标识符过白名单正则 |
| CORS | `allow_credentials` 与通配符 Origin 互斥 |
| 容器逃逸放大 | Dockerfile 非 root UID 运行 + HEALTHCHECK |
| 默认口令 | `auth.json` 入 .gitignore;health 暴露 `default_credentials` 状态 |

### 7. 前端与客户端策略

- **Web 端单文件无构建**:index.html 零外部依赖,克隆即用;状态管理用「每 Tab 独立渲染函数」
  约定隔离;
- **PWA 是纯前端增强**:只在安全上下文注册,http IP 访问时优雅降级;
- **小程序共用同一套 API**:一条中间件按序裁决三种凭据;
- **SDK 是 OpenAPI 的薄封装**:与 `docs/openapi.json` 由同一份 FastAPI 应用导出,除
  `/api/settings` 外方法与端点一一对应。

### 8. 测试策略:评测系统自己先要有测试

- 单元层:models 序列化往返 / storage 路径安全与清单一致性 / judge 全规则语义 /
  runner 崩溃捕获 / report 差分渲染 / 管线算法行为(含已知缺陷的负断言);
- 集成层:evolve 完整闭环在临时目录跑真数据,断言逐轮提升、无回归、归档齐全;
- 接口层:TestClient 走真实鉴权流程;
- 隔离:夹具把资产重定向到临时目录,测试永不污染真实评测资产;
- 端到端:`scripts/verify.py` 用**不变量**(种子行为冻结 + 通过集单调不减 + 数值抽查)
  而非硬编码得分。

### 9. LLM 智能层:接在薄弱环节上,而不是处处撒模型

| 能力 | 编排方式 | 治理硬边界 |
| --- | --- | --- |
| 坏例沉淀助手 | 反馈 + 数据集事实 + v2 试运行 → LLM 起草 → Schema 校验 → 人工确认 | 与手工沉淀走同一校验/落盘路径,人工确认也不能绕过 |
| 失败诊断 | generator-critic 双智能体,编排为确定性代码 | case_id 防幻觉过滤;结论仅供参考 |
| LLM-as-Judge | `conclusion_quality` 按评分细则打分 | 失败降级为"未通过+原因可见",评测永不因 LLM 中断 |

Runtime 统一负责配置/JSON 输出/重试/缓存/审计;未配置 Key 自动降级为确定性 Mock ——
**评测系统的第一品质是可复现**,自由 Agent 循环被刻意排除在评测器之外。详见 `docs/LLM.md`。

### 10. 扩展点

| 想扩展 | 动哪里 |
| --- | --- |
| 管线 v3 | `pipeline/versions.py` 实现 `analyze_v3` 并注册 |
| 新检查类型 | `CheckSpec.type` 加语义 → `BaseJudge` 子类注册到 `CompositeJudge` |
| 真实 LLM judge | 继承 `BaseJudge` 替换成员;runner/报告零改动 |
| 新数据源 | `storage.load_dataset` 支持 CSV/DB,或加 ingest 端点;管线零改动 |
| 新客户端 | 任何能发 HTTP 的端:REST + OpenAPI 已就绪 |
| 抽成通用框架 | `harness/` 对领域零依赖,注册表模式整体可迁移 |

## 常见任务 → 改哪里

| 我想… | 去这里 | 备注 |
| --- | --- | --- |
| 改进分析算法 / 出新版本 | `pipeline/versions.py` | 新增函数 + 注册表登记一行 |
| 加数据集 / 改工况参数 | `pipeline/data/*.json` | 容量、流量、车速都是数据,管线零改动 |
| 加判分检查类型 | `harness/judge.py` + `harness/models.py` | 两文件同步 + 补 `tests/test_judge.py` |
| 加 API 端点 | `webapp/app.py` | 之后 `export_openapi.py` 重导,同步 `docs/API.md` 与 `static/help.html` |
| 改看板页面 | `webapp/static/index.html` | 3199 行单文件应用,无构建步骤 |
| 换 Logo / PWA 图标 | `webapp/static/assets/icon.svg` → `generate_pwa_icons.py` | 全套图标从 SVG 母版栅格化 |
| 加 LLM 能力 | `llm/workflows.py` | 强制 JSON Schema + 必须有降级路径 |
| 接别的 LLM 供应商 | 只改环境变量 | 任意 OpenAI 兼容端点 |
| 沉淀种子 case / 重置资产 | `python scripts/seed_cases.py` | 雨天场景另用 `seed_scenario_cases.py` |
| 备份评测资产 | `python scripts/backup.py` | 打包 cases/evalsets/reports |
| 部署 / 更新公网 | 见 `docs/DEPLOY.md` | Docker 路线一条命令 |

## 文档体系：产品自文档化

| 文档 | 载体 | 读者 |
| --- | --- | --- |
| README | 仓库 | 首次接触项目的人 |
| docs/GET-START.md | 仓库 | 要真的用起来或改它的人 |
| AGENTS.md | 仓库 | AI 编码助手:规范入口与索引、状态表(带复核命令)、已知坑 |
| HISTORY.md / TODO.md | 仓库 | 版本演进 / 开发计划 |
| docs/ARCHITECTURE(本文) | 仓库 | 评审者与后续维护者:为什么这样设计 |
| docs/CODE-STYLE / TESTING / GIT | 仓库 | 约定 / 门禁 / 提交规范 |
| `<一级目录>/README.md` | 仓库 | 该目录负责什么、每个文件干什么 |
| docs/API.md | 仓库 | 集成方:全量接口参考 |
| docs/INTEGRATION.md | 仓库 | 外部系统:5 分钟接入 |
| docs/openapi.json | 仓库 | 机器:导入 Postman/Apifox |
| `/help` 文档中心 | 运行实例 | 看板使用者:核心概念/工作流/FAQ,无需登录 |
| `/docs` | FastAPI 自动生成 | 开发者:交互式调试 |

`/help` 与 `docs/API.md` 内容同构:前者面向使用产品的人,后者面向读代码库的人——
**使用者不必读源码就能用起来**。

## 已知架构问题

- 版本只有三个,且都是"事后重写"的样例;harness 只负责验证与守回归,不自动生成新版本。
- 建议文案的可执行性是真实短板:rc-0015 引入 `conclusion_quality` 后,真实模型判 0.70 恰在
  阈值,Mock 判 1.0 掩盖了它(对比见 `docs/LLM.md`)。
- 交通数据是合成快照(`captured_at` 2026-08-31),未接卡口/GPS 实时源。
- 单进程文件存储:并发靠进程内锁,多实例部署锁不跨进程(约束见 `docs/DEPLOY.md`)。
- 小程序正式发布有硬门槛:必须 HTTPS + 已备案域名,当前默认部署只适合开发与内网。
