"""重放引擎(runner):批量把 replaycase 喂给指定版本的管线,并调用 judge 判分、汇总成 EvalResult。"""

from __future__ import annotations

import time
from datetime import datetime

from harness import storage
from harness.judge import CompositeJudge, case_score
from harness.models import CaseResult, EvalResult, ReplayCase


class ReplayRunner:
    def __init__(self, judge=None):
        self.judge = judge or CompositeJudge()

    def run_case(self, version_key: str, analyze, case: ReplayCase) -> CaseResult:
        t0 = time.perf_counter()
        output, error = None, None
        try:
            segments = storage.load_dataset(case.dataset_name)
            output = analyze(segments)
        except Exception as exc:  # 崩溃本身就是被测行为之一(健壮性类 badcase)
            error = f"{type(exc).__name__}: {exc}"
        check_results = [self.judge.judge_one(spec, output, error) for spec in case.checks]
        passed, score = case_score(case, check_results)
        return CaseResult(
            case_id=case.case_id, title=case.title, label=case.label, version=version_key,
            passed=passed, score=score, checks=check_results, error=error,
            duration_ms=round((time.perf_counter() - t0) * 1000, 2),
        )

    def run_evalset(self, version_key: str, analyze, evalset: dict, cases: list[ReplayCase]) -> EvalResult:
        t0 = time.perf_counter()
        results = [self.run_case(version_key, analyze, c) for c in cases]
        passed_count = sum(1 for r in results if r.passed)
        label_stats: dict[str, dict[str, int]] = {}
        for r in results:
            st = label_stats.setdefault(r.label, {"passed": 0, "total": 0})
            st["total"] += 1
            st["passed"] += int(r.passed)
        return EvalResult(
            version=version_key, evalset_id=evalset["evalset_id"],
            timestamp=datetime.now().isoformat(timespec="seconds"),
            total=len(results), passed_count=passed_count,
            accuracy=round(passed_count / len(results), 4) if results else 0.0,
            label_stats=label_stats, results=results,
            duration_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
