"""harness.report:差分容错、报告 payload 与 Markdown 渲染。"""

from harness import report
from harness.models import CaseResult, EvalResult


def _er(version, case_status: dict[str, bool], evalset_id="evalset_v1") -> EvalResult:
    results = [CaseResult(case_id=cid, title=f"t-{cid}", label="阈值错误",
                          version=version, passed=p, score=1.0 if p else 0.0)
               for cid, p in case_status.items()]
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    return EvalResult(version=version, evalset_id=evalset_id, timestamp="2026-09-15T00:00:00",
                      total=total, passed_count=passed, accuracy=passed / total if total else 0.0,
                      label_stats={}, results=results)


def test_diff_basic_and_regression():
    prev = _er("v1", {"rc-0001": False, "rc-0002": True, "rc-0003": True})
    cur = _er("v2", {"rc-0001": True, "rc-0002": False, "rc-0003": True})
    newly, regressed = report.diff(prev, cur)
    assert newly == ["rc-0001"]
    assert regressed == ["rc-0002"]


def test_diff_tolerates_grown_evalset():
    """评测集扩充后对比旧报告:仅共有的 case 参与新通过/回归判定。"""
    prev = _er("v1", {"rc-0001": False})
    cur = _er("v2", {"rc-0001": True, "rc-0014": False})  # rc-0014 是新沉淀
    newly, regressed = report.diff(prev, cur)
    assert newly == ["rc-0001"]
    assert regressed == []  # 旧报告没有 rc-0014,不判回归


def test_build_payload_embeds_changelog():
    from pipeline.versions import CHANGELOG

    payload = report.build_payload(_er("v2", {"rc-0001": True}), CHANGELOG)
    assert payload["version_name"] == CHANGELOG["v2"]["name"]
    assert payload["changes"] == CHANGELOG["v2"]["changes"]


def test_render_markdown_contains_key_sections(tmp_path, hermetic_storage):
    from pipeline.versions import CHANGELOG

    results = {"v0": _er("v0", {"rc-0001": False}), "v1": _er("v1", {"rc-0001": True})}
    out = tmp_path / "r.md"
    report.render_markdown(results, CHANGELOG, "测试评测集", out)
    text = out.read_text(encoding="utf-8")
    for fragment in ("基线性能(v0)", "【优化版本】v1", "【优化内容】", "【与上一版本对比】",
                     "最终总结", "PASS(无回归且得分提升)", "rc-0001"):
        assert fragment in text, fragment


def test_render_markdown_flags_regression(tmp_path, hermetic_storage):
    from pipeline.versions import CHANGELOG

    results = {"v0": _er("v0", {"rc-0001": True}), "v1": _er("v1", {"rc-0001": False})}
    out = tmp_path / "r.md"
    report.render_markdown(results, CHANGELOG, "", out)
    assert "FAIL" in out.read_text(encoding="utf-8")
