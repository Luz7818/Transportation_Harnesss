"""SDK 返回的强类型模型:与后端 REST 响应字段一一对应,均提供 :meth:`from_dict` 工厂。

仅对"评测结果"与"版本对比"这两类核心负载建模(字段稳定、消费价值最高),
其余端点保持返回原生 dict,避免模型层与后端演进强耦合。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    """单条判分结果。"""

    type: str
    target: str
    expected: Any
    actual: Any
    passed: bool
    detail: str

    @staticmethod
    def from_dict(d: dict) -> CheckResult:
        return CheckResult(
            type=d.get("type", ""), target=d.get("target", ""),
            expected=d.get("expected"), actual=d.get("actual"),
            passed=bool(d.get("passed")), detail=d.get("detail", ""),
        )


@dataclass
class CaseResult:
    """单条 replaycase 的重放结果。"""

    case_id: str
    title: str
    label: str
    version: str
    passed: bool
    score: float
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0

    @staticmethod
    def from_dict(d: dict) -> CaseResult:
        return CaseResult(
            case_id=d.get("case_id", ""), title=d.get("title", ""), label=d.get("label", ""),
            version=d.get("version", ""), passed=bool(d.get("passed")), score=float(d.get("score", 0.0)),
            checks=[CheckResult.from_dict(c) for c in d.get("checks", [])],
            error=d.get("error"), duration_ms=float(d.get("duration_ms", 0.0)),
        )


@dataclass
class EvalResult:
    """一次评测运行的结果(POST /api/eval/run 的响应)。

    accuracy = passed_count / total;results 为逐 case 明细;
    report_id 为服务端归档的报告 ID,可直接传给 get_report / compare。
    """

    version: str
    evalset_id: str
    timestamp: str
    total: int
    passed_count: int
    accuracy: float
    label_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    results: list[CaseResult] = field(default_factory=list)
    duration_ms: float = 0.0
    report_id: str | None = None
    version_name: str | None = None
    changes: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> EvalResult:
        return EvalResult(
            version=d.get("version", ""), evalset_id=d.get("evalset_id", ""),
            timestamp=d.get("timestamp", ""), total=int(d.get("total", 0)),
            passed_count=int(d.get("passed_count", 0)), accuracy=float(d.get("accuracy", 0.0)),
            label_stats=d.get("label_stats", {}),
            results=[CaseResult.from_dict(r) for r in d.get("results", [])],
            duration_ms=float(d.get("duration_ms", 0.0)), report_id=d.get("report_id"),
            version_name=d.get("version_name"), changes=list(d.get("changes", [])),
        )

    def failed_cases(self) -> list[CaseResult]:
        """未通过的 case 明细(快速定位回归)。"""
        return [r for r in self.results if not r.passed]


@dataclass
class CompareRow:
    """版本对比中单条 case 的 A/B 结果。"""

    case_id: str
    title: str
    label: str
    a_passed: bool | None
    b_passed: bool | None
    a_score: float | None
    b_score: float | None
    check_diffs: list[dict] = field(default_factory=list)


@dataclass
class CompareResult:
    """两份评测报告的逐 case 差分(GET /api/compare 的响应)。

    newly_passed 为 B 新通过的 case 列表;regressed 为 B 相对 A 回归的 case 列表
    ——回归非空即应阻止合入。
    """

    a_report_id: str
    a_version: str
    a_accuracy: float
    b_report_id: str
    b_version: str
    b_accuracy: float
    newly_passed: list[str] = field(default_factory=list)
    regressed: list[str] = field(default_factory=list)
    rows: list[CompareRow] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> CompareResult:
        return CompareResult(
            a_report_id=d["a"].get("report_id", ""), a_version=d["a"].get("version", ""),
            a_accuracy=float(d["a"].get("accuracy", 0.0)),
            b_report_id=d["b"].get("report_id", ""), b_version=d["b"].get("version", ""),
            b_accuracy=float(d["b"].get("accuracy", 0.0)),
            newly_passed=list(d.get("newly_passed", [])),
            regressed=list(d.get("regressed", [])),
            rows=[CompareRow(
                case_id=r.get("case_id", ""), title=r.get("title", ""), label=r.get("label", ""),
                a_passed=r.get("a_passed"), b_passed=r.get("b_passed"),
                a_score=r.get("a_score"), b_score=r.get("b_score"),
                check_diffs=list(r.get("check_diffs", [])),
            ) for r in d.get("rows", [])],
        )
