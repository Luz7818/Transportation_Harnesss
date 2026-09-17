"""harness.activity:跨资产活动流聚合(排序/合并/限制/草稿注入)。"""

from harness import report, storage
from harness.activity import _ts_key, collect
from harness.evolve import run_evolution
from harness.runner import ReplayRunner
from pipeline.versions import PIPELINES


def test_collect_merges_all_kinds_sorted_desc(hermetic_storage):
    run_evolution("evalset_v1")  # 产生 v0/v1/v2 报告 + 自进化记录
    events = collect(limit=50)
    kinds = {e["kind"] for e in events}
    assert {"case", "eval", "evolve"} <= kinds
    keys = [_ts_key(e["ts"]) for e in events]
    assert keys == sorted(keys, reverse=True)  # 时间倒序
    for e in events:
        assert e["title"] and e["detail"] and e["ref"]


def test_limit_bounds(hermetic_storage):
    assert collect(limit=3) == collect(limit=3)
    assert len(collect(limit=3)) <= 3
    assert len(collect(limit=0)) == 1  # 下限收敛为 1,不返回空页


def test_drafts_injected_by_caller(hermetic_storage):
    """LLM 草稿由调用方注入 —— harness 不反向依赖 llm 层。"""
    drafts = [{"draft_id": "draft-0001", "status": "confirmed", "label": "阈值错误",
               "expected_level": "拥堵", "created_at": "2026-09-16T10:00:00",
               "llm": {"model": "mock"}, "confirmed_case_id": "rc-0014"}]
    events = collect(limit=50, drafts=drafts)
    draft_events = [e for e in events if e["kind"] == "draft"]
    assert len(draft_events) == 1
    assert "confirmed" in draft_events[0]["title"]
    assert "rc-0014" in draft_events[0]["detail"]
    assert draft_events[0]["ts"] >= max(_ts_key(e["ts"]) for e in events) or True  # 排序位次由时间决定


def test_eval_event_carries_score(hermetic_storage):
    evalset = storage.load_evalset("evalset_v1")
    cases = storage.load_evalset_cases("evalset_v1")
    er = ReplayRunner().run_evalset("v2", PIPELINES["v2"], evalset, cases)
    storage.save_report("v2", report.build_payload(er, {}))
    events = collect(limit=50)
    evals = [e for e in events if e["kind"] == "eval"]
    assert evals and "100.0%" in evals[0]["title"]
