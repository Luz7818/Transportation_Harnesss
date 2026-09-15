"""判分器(judge):把 replaycase 里的判分规则应用到管线输出上。

- RuleJudge       : 结构化规则校验(分级、指标、健壮性、建议完备性),确定性。
- HeuristicJudge  : LLM-as-judge 的离线确定性替身,对结论文本做关键词覆盖检查;
                    接入真实大模型时,实现 BaseJudge 接口并替换 CompositeJudge 的成员即可。
- CompositeJudge  : 按规则类型路由到对应的 judge,汇总 CheckResult 列表。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from numbers import Number

from harness.models import CheckResult, CheckSpec, ReplayCase

CONGESTED_LEVELS = ("拥堵", "严重拥堵")
MISSING_LEVEL = "数据缺失"


class BaseJudge(ABC):
    supported_types: set[str] = set()

    @abstractmethod
    def judge_one(self, spec: CheckSpec, output: dict | None, error: str | None) -> CheckResult:
        ...


class RuleJudge(BaseJudge):
    """结构化规则校验:适用于可精确判定的检查。"""

    supported_types = {"classify", "metric", "no_crash", "recommendations", "congested_empty"}

    def judge_one(self, spec: CheckSpec, output: dict | None, error: str | None) -> CheckResult:
        if spec.type == "no_crash":
            passed = error is None and output is not None
            return CheckResult(spec.type, "-", "无异常", error or "正常返回", passed,
                               "管线崩溃" if not passed else "管线正常返回")
        if output is None:
            return CheckResult(spec.type, spec.segment or spec.field or "-", spec.expected, None, False,
                               f"管线崩溃,无法判分:{error}")
        if spec.type == "classify":
            return self._judge_classify(spec, output)
        if spec.type == "metric":
            return self._judge_metric(spec, output)
        if spec.type == "recommendations":
            return self._judge_recommendations(spec, output)
        if spec.type == "congested_empty":
            n = len(output.get("congested_segments") or [])
            return CheckResult(spec.type, "congested_segments", 0, n, n == 0, f"拥堵路段数 = {n},期望 0")
        return CheckResult(spec.type, "-", None, None, False, f"未知规则类型 {spec.type}")

    @staticmethod
    def _find(output: dict, segment_id: str) -> dict | None:
        for row in output.get("segments", []):
            if row.get("segment_id") == segment_id:
                return row
        return None

    def _judge_classify(self, spec: CheckSpec, output: dict) -> CheckResult:
        row = self._find(output, spec.segment)
        if row is None:
            return CheckResult(spec.type, spec.segment, spec.expected, None, False,
                               f"输出中不存在路段 {spec.segment}")
        actual = row.get("classification")
        passed = actual == spec.expected
        return CheckResult(spec.type, spec.segment, spec.expected, actual, passed,
                           f"期望「{spec.expected}」,实际「{actual}」")

    def _judge_metric(self, spec: CheckSpec, output: dict) -> CheckResult:
        target = output if spec.segment is None else self._find(output, spec.segment)
        if spec.segment is not None and target is None:
            return CheckResult(spec.type, f"{spec.segment}.{spec.field}", spec.expected, None, False,
                               f"输出中不存在路段 {spec.segment}")
        actual = target.get(spec.field) if isinstance(target, dict) else None
        if not isinstance(actual, Number):
            return CheckResult(spec.type, f"{spec.segment or '全局'}.{spec.field}", spec.expected, actual, False,
                               "指标缺失或非数值")
        passed = abs(float(actual) - float(spec.expected)) <= spec.tol
        return CheckResult(spec.type, f"{spec.segment or '全局'}.{spec.field}", spec.expected, actual, passed,
                           f"期望 {spec.expected}±{spec.tol},实际 {actual}")

    def _judge_recommendations(self, spec: CheckSpec, output: dict) -> CheckResult:
        congested = [r for r in output.get("segments", []) if r.get("classification") in CONGESTED_LEVELS]
        rec_ids = {r.get("segment_id") for r in output.get("recommendations") or []}
        missing = [r["segment_id"] for r in congested if r.get("segment_id") not in rec_ids]
        passed = not missing
        detail = ("每个拥堵/严重拥堵路段均有处置建议" if passed
                  else f"缺少处置建议: {', '.join(missing)}")
        return CheckResult(spec.type, "recommendations", "全覆盖", f"缺 {len(missing)} 条", passed, detail)


class HeuristicJudge(BaseJudge):
    """LLM-as-judge 的离线确定性替身:对结论文本做关键词覆盖检查。

    真实场景中此处应调用大模型按评分细则给结论打分;
    为了让整个闭环离线可复现,这里用确定性的文本启发式代替。
    """

    supported_types = {"conclusion_keyword"}

    def judge_one(self, spec: CheckSpec, output: dict | None, error: str | None) -> CheckResult:
        if output is None:
            return CheckResult(spec.type, "summary", list(spec.keywords), None, False,
                               f"管线崩溃,无法判分:{error}")
        summary = output.get("summary", "") or ""
        missing = [k for k in spec.keywords if k not in summary]
        passed = not missing
        return CheckResult(spec.type, "summary", list(spec.keywords), summary, passed,
                           "结论覆盖全部关键词" if passed else f"结论缺少关键词: {missing}")


class CompositeJudge(BaseJudge):
    """按规则类型路由到对应 judge。

    默认成员 = 规则 + 启发式 + LLM(LLM-as-Judge,处理 conclusion_quality);
    LLM 层不可用(缺依赖/初始化失败)时优雅降级为纯规则判分 —— 评测闭环
    永不因 LLM 故障而中断。LLM 只服务文本质量类检查,确定性规则不受影响。
    """

    def __init__(self, judges: list[BaseJudge] | None = None):
        # 仅当未显式传入时才使用默认 judge;显式传 [] 表示"无 judge"(用于测试路由缺失场景)
        if judges is None:
            judges = [RuleJudge(), HeuristicJudge()]
            try:  # 懒加载:llm 层可选,harness 不对其产生硬依赖
                from llm.judge import LLMJudge
                from llm.runtime import get_runtime
                judges.append(LLMJudge(get_runtime()))
            except Exception:
                pass
        self.judges: list[BaseJudge] = judges
        self._route = {}
        for j in self.judges:
            for t in j.supported_types:
                self._route[t] = j

    def judge_one(self, spec: CheckSpec, output: dict | None, error: str | None) -> CheckResult:
        judge = self._route.get(spec.type)
        if judge is None:
            return CheckResult(spec.type, spec.segment or "-", None, None, False,
                               f"没有任何 judge 支持规则类型 {spec.type}")
        return judge.judge_one(spec, output, error)


def case_score(case: ReplayCase, check_results: list[CheckResult]) -> tuple[bool, float]:
    """单条 case 的得分:passed_check/total_check;全部通过才算通过。"""
    if not check_results:
        return False, 0.0
    passed = sum(1 for c in check_results if c.passed)
    return all(c.passed for c in check_results), round(passed / len(check_results), 3)
