"""LLM Judge:按评分细则给结论文本打分(LLM-as-Judge)。

规则 judge(classify/metric/no_crash 等)能确定性判定的一律不用 LLM;
LLM 只负责规则判不了的「文本质量」:结论是否覆盖关键信息、建议是否可执行。
评分结果(分数+理由)随 CheckResult 持久化,可复核、可申诉(治理要求)。
"""

from __future__ import annotations

from harness.judge import BaseJudge
from harness.models import CheckResult, CheckSpec

JUDGE_SYSTEM = (
    "你是交通分析评测系统的判分员。按以下评分细则对【评分对象】打 0~1 分:\n"
    "1) 覆盖性(40%):是否点明拥堵/严重拥堵路段与数量、全局拥堵指数等关键信息;\n"
    "2) 可执行性(40%):处置建议是否具体可落地(而非空话);\n"
    "3) 简洁性(20%):表述是否精炼、无自相矛盾。\n"
    "只输出 JSON:{\"score\": 0到1的小数, \"rationale\": \"不超过60字的评分理由\"}"
)


class LLMJudge(BaseJudge):
    """conclusion_quality 检查类型:LLM 按细则打分,达到 min_score 视为通过。

    任何 LLM 异常都不允许炸掉评测 —— 降级为「未通过 + 原因写进明细」,
    由人工决定是否重跑(治理:LLM 失败可见,不静默吞掉)。
    """

    supported_types = {"conclusion_quality"}

    def __init__(self, runtime):
        self.runtime = runtime

    def judge_one(self, spec: CheckSpec, output: dict | None, error: str | None) -> CheckResult:
        if spec.type != "conclusion_quality":  # 防御:路由不应送来别的类型
            return CheckResult(spec.type, spec.segment or "-", None, None, False,
                               f"LLMJudge 不支持规则类型 {spec.type}")
        if output is None:
            return CheckResult(spec.type, "summary", spec.min_score, None, False,
                               f"管线崩溃,无法判分:{error}")
        recs = "\n".join(f"- {r.get('text', '')}" for r in output.get("recommendations") or [])
        user = (f"[评分对象]\n结论:{output.get('summary', '') or '(空)'}\n"
                f"处置建议:\n{recs or '(无)'}\n[-评分对象]")
        try:
            data = self.runtime.complete_json(purpose="judge", system=JUDGE_SYSTEM, user=user)
            score = max(0.0, min(1.0, float(data.get("score", 0.0))))
            rationale = str(data.get("rationale", ""))[:120]
        except Exception as exc:  # 降级:失败可见,不静默
            return CheckResult(spec.type, "summary", spec.min_score, None, False,
                               f"LLM 判分不可用({exc}),按未通过处理,可重跑")
        passed = score >= spec.min_score
        return CheckResult(spec.type, "summary", spec.min_score, score, passed,
                           f"LLM 评分 {score:.2f}(阈值 {spec.min_score}):{rationale}")
