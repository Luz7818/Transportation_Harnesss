# llm/ —— LLM 智能层（可选装配）

> 用途：说明本目录管哪一段、每个文件干什么、离线降级发生在哪一行。

LLM 只接在闭环的两个薄弱环节上：**把模糊反馈起草成结构化用例**、
**给规则判不了的结论文本打分**，外加**把失败清单归因成根因与迭代建议**。
其余一切（数值、等级、崩溃与否）仍由 `harness/judge.py` 的确定性规则判定。

本目录是**可选**的：`harness/` 不硬依赖它，任何 LLM 故障都有降级路径。
未配置 `LLM_BASE_URL` + `LLM_API_KEY` 时整个进程走离线确定性 Mock ——
评测、看板、测试、CI 全部照常，且结果可复现。

## 文件清单

| 文件 | 干什么 | 备注 |
| --- | --- | --- |
| `runtime.py` | 模型访问层：`load_config()` 读环境变量、`LLMRuntime.complete_json()`（stdlib `urllib` 直发 OpenAI 兼容 `/chat/completions`，强制 `response_format=json_object`，超时 30 s、瞬时错误重试 1 次、缓存与审计）、`MockLLMRuntime`、进程级单例 `get_runtime()` / `reset_runtime()` / `status()` | `LLM_BASE_URL` 或 `LLM_API_KEY` 缺任何一个就返回 `None` 配置 → 用 Mock；`LLM_EXTRA_BODY` 必须是 JSON 对象，非法立即抛 `LLMError`（失败可见） |
| `judge.py` | `LLMJudge`：`conclusion_quality` 检查按细则（覆盖性 40% / 可执行性 40% / 简洁性 20%）打 0~1 分，`>= spec.min_score`（默认 0.7）才算通过 | 任何异常都返回「未通过 + 原因写进明细」，绝不抛出炸掉整轮评测；分数与理由随 `CheckResult` 进报告，可复核 |
| `workflows.py` | 两条工作流的编排与治理：`draft_replaycase()`（反馈原文 + 数据集事实 + v2 实际判定 → 起草 → 校验 → 存 `drafts/`）、`diagnose_failures()`（分析者 → 评审者 → `case_id` 防幻觉过滤） | 三段系统提示词（`DRAFT_SYSTEM`/`ANALYZE_SYSTEM`/`REVIEW_SYSTEM`）在这里；草稿的期望等级不在六档枚举内直接 `ValueError`（非法输出不落盘）；`complaint` 长度须在 5~500 字符 |
| `store.py` | 三样持久化：响应缓存 `llm_cache/<sha>.json`、审计日志 `llm_runs.jsonl`（追加写）、草稿 `drafts/draft-NNNN.json` | 缓存键 = `sha256(模型\|用途\|system\|user)` 前 32 位 → 同输入同输出；草稿 ID 取当前最大序号 +1；三个位置都是运行期产物且已 gitignore |
| `mocks.py` | 离线确定性输出：按 `purpose`（`draft`/`judge`/`diagnose-analyze`/`diagnose-review`）从提示词文本里推导字段（关键词、`V/C=0.95` 这类数值、失败标签→根因/建议映射表） | 职责边界：保证**编排可演示可测试**，不追求与真实模型等价的语义质量 |
| `__init__.py` | 包 docstring，指向 `docs/LLM.md` | — |

## 一次调用的路径

```
workflows / harness.CompositeJudge
   → runtime.get_runtime()            # 进程级单例,首次调用才读配置
   → complete_json(purpose, system, user)
        真实端点: 缓存命中? → 返回 ; 否则 POST → 解析(容忍 ```json 围栏) → 写缓存 + 写审计
        Mock:     mocks.render(purpose, user) → 只写审计(estimated_prompt_tokens = len(user)//2)
   → 调用方做 Schema 校验(等级枚举 / 数值范围 / 长度截断 / case_id 求交)
```

`GET /api/llm/status` 就是这个链路的健康视图：`kind`（`mock` 或 `openai-compatible`）、
`model`、`configured`、四个环境变量名、`cache_count`、最近 5 条审计。

## 三条人工确认边界（Human-in-the-loop）

1. LLM **永不直接写评测资产**：草稿状态是 `pending`，只有 `POST /api/llm/drafts/{id}/confirm`
   才落进 `cases/`，且内部复用与手工沉淀完全相同的校验函数（人工编辑也绕不过）。
2. 诊断结果只是建议：不自动建用例、不改管线、不动评测集。
3. 失败必须可见：judge 故障记「未通过 + 原因」，工作流故障回 `502`，不做静默吞掉。

## 和谁打交道

- **上游**：`webapp/app.py` 的 6 个 `/api/llm/*` 端点、`harness/judge.py` 的 `CompositeJudge`（懒加载 `LLMJudge`）、`miniprogram/pages/drafts`。
- **下游**：`drafts/`、`llm_cache/`、`llm_runs.jsonl`；确认后的用例归 `cases/` 与 `evalsets/`。
- **改完要跑**：`python -m pytest tests/test_llm.py -q`（27 例，全程离线 Mock）
  → 涉及端点再跑 `python -m pytest tests/test_webapp.py -q` 与 `python scripts/export_openapi.py`。

## 别动

- 不要让 `harness/` 依赖 `llm/`：`CompositeJudge` 用 `try/except` 懒加载就是为了「删掉 `llm/` 评测闭环仍然成立」。
- 不要引入 OpenAI SDK 或任何新依赖：`urllib` 直发 HTTP 是刻意的，换供应商只改环境变量。
- 不要让 LLM 步骤联网才能过：任何需要外网的测试或校验都不属于这里（也进不了 CI）。
- 不要放宽 `max_chars`（默认 6000 截断）或去掉缓存：前者是单次成本上限，后者是「同输入同输出」的唯一保证。
- 不要把真实模型密钥写进文档、示例或提交物；`.env` 与 `llm_runs.jsonl` 里的内容都不入库。
- 不要指望 Mock 的 `expected_level`/`label` 判得准：它按关键词与 v2 判定推导，
  价值在链路，起草质量要靠真实模型 + 人工确认，`rationale` 字段里已写明这一点。
