"""harness.evolve:自进化主流程的完整闭环(在临时目录归档,不污染真实报告)。"""

from harness import storage
from harness.evolve import run_evolution


def test_run_evolution_full_loop(hermetic_storage):
    summary = run_evolution("evalset_v1")

    # 轨迹:基线 → 2 轮迭代,逐轮提升且最终全通过
    assert summary["evalset_id"] == "evalset_v1"
    assert summary["total_cases"] == 13
    assert summary["baseline"]["version"] == "v0"
    assert summary["baseline"]["accuracy"] == round(1 / 13, 4)
    assert [r["version"] for r in summary["rounds"]] == ["v1", "v2"]
    assert all(not r["regressed"] for r in summary["rounds"])  # 全程无回归
    assert summary["best"]["version"] == "v2"
    assert summary["best"]["accuracy"] == 1.0
    assert "全部通过" in summary["stop_reason"]

    # 归档资产:每版本 JSON 报告 + Markdown 总报告 + 进化摘要
    reports = {r["version"] for r in storage.list_reports()}
    assert {"v0", "v1", "v2"} <= reports
    assert (storage.REPORTS_DIR / summary["md_report"]).exists()
    evolution = storage.load_evolution(summary["evolution_id"])
    assert evolution["best"]["accuracy"] == 1.0


def test_run_evolution_on_scenario_evalset(hermetic_storage):
    """同一管线可直接跑场景评测集 —— harness 与被测对象解耦。"""
    summary = run_evolution("evalset_scenario_rain")
    assert summary["total_cases"] == 3
    assert summary["best"]["accuracy"] == 1.0


def test_run_evolution_from_custom_baseline(hermetic_storage, monkeypatch):
    """登记 v3 后,以 v2 为基线增量验证 —— 迭代版本从注册表派生,不再硬编码。"""
    from pipeline.versions import CHANGELOG, PIPELINES, analyze_v2

    monkeypatch.setitem(PIPELINES, "v3", analyze_v2)  # v3 复用 v2 行为,应无回归
    monkeypatch.setitem(CHANGELOG, "v3", {"name": "第 3 轮迭代", "changes": ["占位改动"]})

    summary = run_evolution("evalset_v1", "v2")
    assert [r["version"] for r in summary["rounds"]] == ["v3"]
    assert summary["best"]["version"] == "v3"
    assert summary["pending_versions"] == []
    assert "评测集已全部通过" in summary["stop_reason"]


def test_round_cap_exposes_pending_versions(hermetic_storage, monkeypatch):
    """单轮上限裁剪不静默:未验证版本显式进入 pending_versions。"""
    from pipeline.versions import CHANGELOG, PIPELINES, analyze_v2

    monkeypatch.setitem(PIPELINES, "v3", analyze_v2)
    monkeypatch.setitem(CHANGELOG, "v3", {"name": "第 3 轮迭代", "changes": ["占位改动"]})
    monkeypatch.setenv("EVOLVE_MAX_ROUNDS", "2")

    summary = run_evolution("evalset_v1", "v0")  # v1/v2 占满 2 轮,v3 留待下轮
    assert [r["version"] for r in summary["rounds"]] == ["v1", "v2"]
    assert summary["pending_versions"] == ["v3"]
    assert "待验证" in summary["stop_reason"]


def test_unknown_baseline_rejected(hermetic_storage):
    import pytest

    with pytest.raises(ValueError):
        run_evolution("evalset_v1", "v9")


def test_tail_baseline_rejected(hermetic_storage):
    """基线传最末登记版本(其后无待验证版本)→ 明确 ValueError,不再 IndexError。
    v3 登记后最末版本随之前移(v2 → v3),用 PIPELINES 的实际末位,别写死。"""
    import pytest
    from pipeline.versions import PIPELINES

    tail = list(PIPELINES)[-1]
    with pytest.raises(ValueError) as excinfo:
        run_evolution("evalset_v1", tail)
    assert "没有待验证" in str(excinfo.value)


def test_forward_iteration_to_registered_v3(hermetic_storage):
    """前向迭代留痕:v3 已真实登记,以 v2 为基线增量验证 —— 无需任何 monkeypatch。"""
    summary = run_evolution("evalset_v1", "v2")
    assert [r["version"] for r in summary["rounds"]] == ["v3"]
    assert summary["baseline"]["version"] == "v2"
    assert summary["best"]["version"] == "v3"
    assert summary["best"]["accuracy"] == 1.0          # v3 通过夹具全部 13 条种子 case
    assert all(not r["regressed"] for r in summary["rounds"])
    assert summary["pending_versions"] == []
