"""harness.models:数据结构序列化/反序列化的往返一致性。"""

from harness.models import CaseResult, CheckSpec, ReplayCase


def test_check_spec_roundtrip():
    spec = CheckSpec(type="metric", segment="S-02", field="saturation",
                     expected=0.91, tol=0.02, keywords=("拥堵",))
    assert CheckSpec.from_dict(spec.to_dict()) == spec


def test_replay_case_roundtrip_preserves_checks():
    case = ReplayCase(
        case_id="rc-9999", title="t", label="阈值错误", dataset_name="base",
        checks=[CheckSpec(type="classify", segment="S-01", expected="畅通"),
                CheckSpec(type="conclusion_keyword", keywords=("拥堵",))],
        source="线上点踩", notes="n",
    )
    restored = ReplayCase.from_dict(case.to_dict())
    assert restored == case
    assert restored.checks[1].keywords == ("拥堵",)


def test_replay_case_tolerates_unknown_fields():
    """前向兼容:老代码读取含新字段的 case 文件不应崩溃。"""
    restored = ReplayCase.from_dict({
        "case_id": "rc-0001", "title": "t", "label": "l", "dataset_name": "base",
        "future_field": "whatever",
    })
    assert restored.case_id == "rc-0001"
    assert restored.checks == []


def test_case_result_to_dict_nested():
    result = CaseResult(case_id="rc-0001", title="t", label="l", version="v2",
                        passed=True, score=1.0)
    assert result.to_dict()["checks"] == []
