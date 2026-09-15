"""harness.judge:各规则类型的判分语义与路由。"""

from harness.judge import CompositeJudge, HeuristicJudge, RuleJudge, case_score
from harness.models import CheckResult, CheckSpec, ReplayCase

OUTPUT = {
    "segments": [
        {"segment_id": "S-01", "classification": "畅通", "saturation": 0.42},
        {"segment_id": "S-02", "classification": "拥堵", "saturation": 0.91},
    ],
    "congested_segments": ["S-02"],
    "global_congestion_index": 0.85,
    "recommendations": [{"segment_id": "S-02", "text": "优化信号配时"}],
    "summary": "共分析 2 个路段,存在拥堵路段 1 个。",
}


def classify(seg, level):
    return CheckSpec(type="classify", segment=seg, expected=level)


class TestRuleJudge:
    def test_classify_pass_and_fail(self):
        judge = RuleJudge()
        assert judge.judge_one(classify("S-02", "拥堵"), OUTPUT, None).passed
        assert not judge.judge_one(classify("S-02", "严重拥堵"), OUTPUT, None).passed

    def test_classify_unknown_segment_fails(self):
        r = RuleJudge().judge_one(classify("S-99", "拥堵"), OUTPUT, None)
        assert not r.passed and "不存在" in r.detail

    def test_metric_within_tolerance(self):
        spec = CheckSpec(type="metric", segment="S-02", field="saturation",
                         expected=0.9, tol=0.02)
        assert RuleJudge().judge_one(spec, OUTPUT, None).passed

    def test_metric_global_field(self):
        spec = CheckSpec(type="metric", field="global_congestion_index", expected=0.8, tol=0.3)
        assert RuleJudge().judge_one(spec, OUTPUT, None).passed

    def test_metric_missing_value_fails(self):
        spec = CheckSpec(type="metric", segment="S-01", field="nonexistent", expected=1.0)
        r = RuleJudge().judge_one(spec, OUTPUT, None)
        assert not r.passed and "缺失" in r.detail

    def test_no_crash(self):
        ok = CheckSpec(type="no_crash")
        assert RuleJudge().judge_one(ok, OUTPUT, None).passed
        assert not RuleJudge().judge_one(ok, None, "ZeroDivisionError").passed

    def test_crash_output_fails_other_checks(self):
        spec = CheckSpec(type="metric", segment="S-02", field="saturation", expected=0.9)
        r = RuleJudge().judge_one(spec, None, "ZeroDivisionError: x")
        assert not r.passed and "崩溃" in r.detail

    def test_recommendations_coverage(self):
        spec = CheckSpec(type="recommendations")
        assert RuleJudge().judge_one(spec, OUTPUT, None).passed
        broken = {**OUTPUT, "recommendations": []}
        r = RuleJudge().judge_one(spec, broken, None)
        assert not r.passed and "S-02" in r.detail

    def test_congested_empty(self):
        spec = CheckSpec(type="congested_empty")
        assert RuleJudge().judge_one(spec, {"congested_segments": []}, None).passed
        assert not RuleJudge().judge_one(spec, OUTPUT, None).passed

    def test_unknown_type_fails(self):
        r = RuleJudge().judge_one(CheckSpec(type="time_travel"), OUTPUT, None)
        assert not r.passed


class TestHeuristicJudge:
    def test_keyword_coverage(self):
        spec = CheckSpec(type="conclusion_keyword", keywords=("拥堵", "路段"))
        assert HeuristicJudge().judge_one(spec, OUTPUT, None).passed
        spec2 = CheckSpec(type="conclusion_keyword", keywords=("拥堵", "事故"))
        r = HeuristicJudge().judge_one(spec2, OUTPUT, None)
        assert not r.passed and "事故" in r.detail


class TestCompositeJudge:
    def test_routes_by_type(self):
        judge = CompositeJudge()
        assert judge.judge_one(classify("S-02", "拥堵"), OUTPUT, None).passed
        assert judge.judge_one(
            CheckSpec(type="conclusion_keyword", keywords=("拥堵",)), OUTPUT, None).passed

    def test_unsupported_type_fails_gracefully(self):
        judge = CompositeJudge(judges=[])  # 没有任何 judge
        r = judge.judge_one(classify("S-01", "畅通"), OUTPUT, None)
        assert not r.passed


def test_case_score():
    case = ReplayCase(case_id="c", title="t", label="l", dataset_name="d")
    results = [CheckResult("classify", "S-01", "畅通", "畅通", True, "ok"),
               CheckResult("metric", "S-01.sat", 0.4, 0.41, False, "off")]
    passed, score = case_score(case, results)
    assert passed is False and score == 0.5
    assert case_score(case, []) == (False, 0.0)
