"""harness.runner:重放引擎的崩溃捕获与统计汇总。"""

from harness import storage
from harness.runner import ReplayRunner


def _load_default_evalset():
    return storage.load_evalset("evalset_v1"), storage.load_evalset_cases("evalset_v1")


def test_run_case_captures_crash_as_error(hermetic_storage):
    """管线抛异常不应中断评测,而是作为被观测行为进入 CaseResult。"""
    runner = ReplayRunner()
    cases = storage.load_evalset_cases("evalset_v1")
    crash_case = next(c for c in cases if c.dataset_name == "empty")

    def boom(_segments):
        raise ZeroDivisionError("division by zero")

    result = runner.run_case("vX", boom, crash_case)
    assert result.passed is False
    assert "ZeroDivisionError" in result.error


def test_run_evalset_aggregates(hermetic_storage):
    from pipeline.versions import PIPELINES

    evalset, cases = _load_default_evalset()
    er = ReplayRunner().run_evalset("v2", PIPELINES["v2"], evalset, cases)
    assert er.total == 13
    assert er.passed_count == 13
    assert er.accuracy == 1.0
    assert er.label_stats["阈值错误"] == {"passed": 4, "total": 4}
    assert sum(st["total"] for st in er.label_stats.values()) == 13
    assert all(r.duration_ms >= 0 for r in er.results)
    assert er.timestamp  # ISO 时间戳已生成


def test_run_evalset_empty_cases_yields_zero_accuracy(hermetic_storage):
    evalset, cases = _load_default_evalset()
    er = ReplayRunner().run_evalset("v2", lambda s: {}, evalset, [])
    assert er.total == 0 and er.accuracy == 0.0
