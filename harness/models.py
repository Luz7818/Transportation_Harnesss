"""核心数据结构:ReplayCase(沉淀的坏例)、CaseResult(单例重放结果)、EvalResult(整轮评测结果)。

一条 replaycase = 可重放的最小评测单元:
- dataset_name : 复现问题所需的数据集(对应 pipeline/data 下的文件名)
- checks       : 判分规则列表(交给 harness.judge 执行)
- label/source : 失败类别与反馈来源,用于"收集反馈建评测集"
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CheckSpec:
    """单条判分规则。type 决定语义,其余字段按类型取用。

    type 取值:
    - classify           : 某路段的拥堵等级应等于 expected
    - metric             : 某路段(或全局)指标应约等于 expected,容差 tol
    - no_crash           : 管线必须正常返回、不抛异常
    - recommendations    : 每个拥堵/严重拥堵路段都必须有处置建议
    - congested_empty    : 拥堵路段列表应为空(空数据集场景)
    - conclusion_keyword : 分析结论文本必须覆盖给定关键词(由启发式 judge 执行)
    - conclusion_quality : 结论文本质量按评分细则打分(LLM judge,阈值 min_score)
    """

    type: str
    segment: str | None = None
    field: str | None = None
    expected: Any = None
    tol: float = 0.01
    keywords: tuple[str, ...] = ()
    min_score: float = 0.7  # conclusion_quality(LLM judge)的通过阈值

    def to_dict(self) -> dict:
        d = asdict(self)
        d["keywords"] = list(self.keywords)
        return d

    @staticmethod
    def from_dict(d: dict) -> CheckSpec:
        known = set(CheckSpec.__dataclass_fields__)
        data = {k: v for k, v in d.items() if k in known}
        data["keywords"] = tuple(data.get("keywords", ()))
        return CheckSpec(**data)


@dataclass
class CheckResult:
    type: str
    target: str
    expected: Any
    actual: Any
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReplayCase:
    case_id: str
    title: str
    label: str
    dataset_name: str
    checks: list[CheckSpec] = field(default_factory=list)
    source: str = "人工标注"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["checks"] = [c.to_dict() for c in self.checks]
        return d

    @staticmethod
    def from_dict(d: dict) -> ReplayCase:
        known = set(ReplayCase.__dataclass_fields__)
        data = {k: v for k, v in d.items() if k in known}
        data["checks"] = [CheckSpec.from_dict(c) for c in data.get("checks", [])]
        return ReplayCase(**data)


@dataclass
class CaseResult:
    case_id: str
    title: str
    label: str
    version: str
    passed: bool
    score: float
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["checks"] = [c.to_dict() for c in self.checks]
        return d


@dataclass
class EvalResult:
    version: str
    evalset_id: str
    timestamp: str
    total: int
    passed_count: int
    accuracy: float
    label_stats: dict[str, dict[str, int]]
    results: list[CaseResult] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["results"] = [r.to_dict() for r in self.results]
        return d
