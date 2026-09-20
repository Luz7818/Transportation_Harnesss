# LLM 集成设计:七个维度的落地映射

本文回答「一个评测型 harness 应该如何合理、克制、有价值地引入 LLM」。
核心立场先讲清楚:

> **LLM 接在闭环的薄弱环节上,而不是处处撒模型。**
> 确定性规则能做的事(数值、等级、崩溃与否)绝不交给模型;LLM 只做规则判不了的三件事:
> 把模糊反馈变成结构化用例(沉淀加速)、给结论文本按细则打分(LLM-as-Judge)、
> 把失败清单变成根因与迭代建议(诊断加速)。每一步都有 Schema 校验、人工确认与审计。

## 总览:七个维度 → 本仓库的落点

| 维度 | 本项目的落地 | 代码位置 |
| --- | --- | --- |
| **Runtime** | 统一模型访问层:OpenAI 兼容端点(OpenAI/DeepSeek/vLLM/Ollama)、强制 JSON 输出、超时重试、响应缓存、调用审计、**离线 Mock 降级** | `llm/runtime.py`、`llm/store.py` |
| **Context & Memory** | 每次调用的上下文由「反馈原文 + 数据集事实 + v2 当前判定」程序化组装,超长截断(token 预算);记忆分三层:响应缓存(情景)、case 库(长期语义)、人工确认记录(校准) | `llm/workflows.py` 的 prompt 组装、`llm_cache/`、`cases/`、`drafts/` |
| **Tool & Workflow** | 工作流优先于自由 Agent:两个确定性编排(草稿沉淀、失败诊断),LLM 是其中可校验的「步骤」;步骤可用的"工具"= 数据集查询、v2 试运行、case 校验落盘 —— 全部是 harness 已有能力 | `llm/workflows.py`、`harness/storage.py` |
| **Human-in-the-loop** | 草稿必须人工确认才成为 replaycase(且走与手工沉淀**完全相同**的校验/落盘路径);诊断结论仅供参考,不自动改任何资产;LLM 判分失败降级可见、可重跑 | `POST /api/llm/drafts/{id}/confirm`、`harness/judge.py` |
| **Multi-Agent 协作** | 失败诊断 = 分析者(按标签归因)+ 评审者(复核、去重、风险提示)的 generator-critic 流水线;**刻意不做自主 Agent 群** —— 评测系统要求可复现,编排必须确定 | `llm/workflows.py:diagnose_failures` |
| **Evaluation & Governance** | 模型输出全部过校验(等级枚举、case_id 防幻觉过滤、长度截断);一切调用进 `llm_runs.jsonl` 审计;响应缓存保证同输入同输出;LLM judge 的分数与理由随报告持久化可复核;成本可见(缓存命中/token 统计) | `llm/store.py`、`llm/judge.py`、`llm/workflows.py` |
| **工程化落地** | 零新增依赖(stdlib urllib);未配 Key 自动降级 Mock,CI 与课堂演示离线可跑;27 个专项测试;环境变量两枚即可接入(另有 LLM_EXTRA_BODY 可选透传模型专属参数);.env 零依赖自动加载;Docker 卷持久化草稿与缓存 | `tests/test_llm.py`、`Dockerfile`、`docker-compose.yml` |

## 1. Runtime:统一模型访问层

```
调用方(workflows / judge)
    │  complete_json(purpose, system, user)
    ▼
LLMRuntime(配置:LLM_BASE_URL/LLM_API_KEY/LLM_MODEL,环境变量)
    ├─ 缓存命中? → 直接返回(llm_cache/<sha>.json)
    ├─ POST {base_url}/chat/completions,response_format=json_object
    │    超时 30s,失败重试 1 次;解析容忍 ```json 围栏
    ├─ 写缓存 + 写审计(llm_runs.jsonl:用途/模型/耗时/token/缓存命中)
    ▼
未配置 Key → MockLLMRuntime:输出由输入确定性推导,零网络零成本
```

要点:

- **零 SDK 依赖**:stdlib `urllib` 直发 HTTP,任何 OpenAI 兼容端点通吃;
- **单例 + 可重置**:`get_runtime()` 进程级单例,测试可 `reset_runtime()`;
- **Mock 不是假装配**:它让工作流的**编排结构**(上下文组装 → 结构化输出 → 校验 →
  人工确认 → 落盘)在不配 Key 时完整可演示、可测试;配 Key 后仅替换一个方法,
  其余零改动。

## 2. Context & Memory:上下文组装与三层记忆

**上下文组装**(以坏例草稿为例)是一次调用的全部输入,由代码而非模型拼装:

```
[用户反馈原文] → 用户输入,原样保留(截断至预算内)
[数据集]       → storage.list 数据集元信息
[候选路段]     → 路段事实(volume/speed),让模型"有据可依"
[v2 当前判定]  → 用当前最佳版本实际跑一遍该数据集,把"现在判成什么样"给模型看
```

单次调用 `max_chars=6000` 截断,成本上限确定。

**三层记忆**:

| 层 | 载体 | 作用 |
| --- | --- | --- |
| 情景记忆 | `llm_cache/`(响应缓存,输入哈希寻址) | 同输入同输出:评测可复现、重复请求零成本 |
| 长期语义记忆 | `cases/`(replaycase 库) | 项目本身就是"这个系统犯过什么错"的结构化记忆,LLM 诊断时以它为事实来源 |
| 校准记忆 | `drafts/`(人工确认记录) | 哪些 AI 草稿被人接受/修改,是后续 few-shot 校准 judge 与起草提示词的第一手数据 |

## 3. Tool & Workflow:工作流优先,LLM 是"步骤"

两个编排好的工作流,LLM 只出现在可校验的步骤上:

**工作流 A:坏例沉淀助手**(闭环第 1-2 步加速)

```
反馈原文 + 数据集 + 路段 → [LLM: 起草] → Schema 校验
  (等级枚举/标题长度/饱和度范围,非法即 400,不落盘)
→ 草稿 pending(drafts/) → 人工编辑确认 → 复用手工沉淀的同一校验/落盘路径
→ 正式 replaycase + 加入评测集
```

**工作流 B:失败诊断**(闭环第 4 步加速)

```
重放评测(真实运行,非缓存) → 失败清单
→ [智能体 1 分析者: 按标签归因] → [智能体 2 评审者: 复核/去重/风险]
→ case_id 防幻觉过滤(只允许引用真实失败 id)→ 建议展示(仅供参考)
```

为什么不做自由 Agent(自己决定调什么工具、循环到满意为止):
评测系统的第一品质是**可复现**。自由 Agent 的路径不可预测,同一天两次运行给两个答案,
回归验证就失去了基准。工作流 + 受控 LLM 步骤是"有用"与"可复现"的平衡点;
若未来引入自主 Agent,也应作为**被测对象**接入本 harness 评测,而不是藏在评测器里。

## 4. Human-in-the-loop:三条硬边界

1. **写路径必经人工**:LLM 草稿确认接口内部复用 `CaseBody` 校验 + `_create_case_from_body`,
   与网页手工沉淀走同一条路 —— 人工确认也不能绕过校验(有测试断言);
2. **诊断仅供参考**:诊断结果不自动建 case、不改管线、不动评测集;
3. **失败可见不静默**:LLM judge 调用失败时该检查记为"未通过 + 原因写入明细",
   由人决定重跑;绝不允许 LLM 故障炸掉整轮评测(有测试断言)。

## 5. Multi-Agent 协作:generator-critic 流水线

诊断工作流实现了最小但完整的双角色协作:

- **分析者**:输入失败清单,按标签聚类归因,产出根因 + 建议;
- **评审者**:以分析者输出为输入,独立复核 —— 剔除不成立、合并重复、补充风险提示;
- **编排者**(纯代码):负责上下文组装、Schema 校验、case_id 幻觉过滤、结构化落盘。

角色 = 系统提示 + 独立上下文 + 固定输出 Schema;协作质量由
`affected_cases 只能引用真实失败 id` 这类**机械校验**兜底,而不是信任模型自觉。
这就是本项目对"多智能体"的立场:**协作价值来自视角分离,可靠性来自编排约束。**

## 6. Evaluation & Governance:模型本身也在治理之下

| 治理项 | 机制 |
| --- | --- |
| 输出合法性 | 等级枚举校验、数值范围钳制、长度截断;非法输出直接拒绝(400),不落盘 |
| 防幻觉 | 诊断结果中的 case_id 与真实失败集求交,引用不存在 id 的项被替换为真实失败集(有测试) |
| 可复现 | 响应缓存按「模型+用途+提示词」哈希寻址;Mock 模式输出纯确定性 |
| 可审计 | `llm_runs.jsonl` 追加写每次调用:时间/用途/模型/耗时/token/缓存命中;`/api/llm/status` 与常驻「智能助手」面板直接可查 |
| 可复核 | LLM judge 的分数与评分理由随 CheckResult 进入评测报告,人工可逐条申诉 |
| 成本可控 | 缓存命中零成本;超长输入截断;调用次数 = 工作流步数(固定),无 Agent 循环失控风险 |
| 可降级 | 无 Key → Mock;真实端点故障 → 重试 1 次 → 明确报错;judge 故障 → 检查降级为未通过且原因可见 |

## 7. 工程化落地

**接入真实模型(两枚环境变量)**:

```bash
LLM_BASE_URL=https://api.deepseek.com/v1   # 或 OpenAI/vLLM/Ollama 等任意兼容端点
LLM_API_KEY=sk-xxx                          # 无鉴权端点可填 EMPTY
LLM_MODEL=deepseek-chat
LLM_EXTRA_BODY={"enable_thinking": false}   # 可选:JSON 对象,原样并入请求体(如关闭 Qwen3 思考模式)
python webapp/app.py
```

`webapp/app.py` 启动时会自动加载仓库根目录的 `.env`(零依赖实现,已存在的环境变量优先于文件),
也可在 Docker/启动脚本里直接注入环境变量。

未配置时一切照常(Mock),常驻右侧的「智能助手」面板与 `/api/llm/status` 会明确标注当前模式。

**零新增依赖**:HTTP 用 stdlib `urllib`,无 openai SDK 锁定 —— 换供应商只改环境变量。

**测试**:`tests/test_llm.py` 覆盖 27 个用例 —— Runtime 配置/缓存/审计/JSON 解析容错、
LLMJudge 打分与故障降级、草稿工作流(编号递增/校验拒绝)、诊断工作流(分标签归因/
全通过短路/幻觉过滤)、API 全链路(草稿 → 确认 → 入库 → 重复确认 409 / 非法等级 400)。
全程离线 Mock,CI 无需密钥。

**部署**:`Dockerfile` 已纳入 `llm/`;`docker-compose.yml` 挂载 `drafts/` 与 `llm_cache/`
数据卷;三个目录均入 `.gitignore`(运行期产物不入库)。

**API 一览**(全部需登录/令牌,鉴权与既有接口一致):

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/llm/status` | Runtime 状态与最近调用审计 |
| POST | `/api/llm/drafts` | 反馈原文 → 坏例草稿(pending) |
| GET | `/api/llm/drafts` | 草稿列表 |
| POST | `/api/llm/drafts/{id}/confirm` | 人工确认 → 正式 replaycase(可带编辑覆盖) |
| DELETE | `/api/llm/drafts/{id}` | 丢弃草稿 |
| POST | `/api/llm/diagnose` | 失败诊断(双角色) |

## 已知边界与演进方向

- 判分细则与起草提示词是人工先验,尚未用 `drafts/` 的人工修正做自动 few-shot 校准(下一迭代);
- 诊断的建议质量依赖所配模型,当前验收手段是人工评审 + 回归重跑(恰是本 harness 的用法);
- 若引入自主 Agent(自动改管线并提交),必须以"被测对象"身份过同一套评测集 —— harness 不豁免自己。
