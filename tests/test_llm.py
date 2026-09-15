"""LLM 集成层:Runtime(Mock/缓存/审计)、LLMJudge、双工作流、API 全链路(全程离线 Mock)。"""

import pytest
from llm import runtime as llm_runtime
from llm import store as llm_store
from llm.judge import LLMJudge
from llm.runtime import LLMRuntime, MockLLMRuntime, get_runtime
from llm.workflows import diagnose_failures, draft_replaycase


@pytest.fixture(autouse=True)
def _isolated_llm(tmp_path, monkeypatch):
    """隔离 LLM 运行期产物,并强制 Mock 模式(清除可能存在的真实端点配置)。"""
    monkeypatch.setattr(llm_store, "DRAFTS_DIR", tmp_path / "drafts")
    monkeypatch.setattr(llm_store, "CACHE_DIR", tmp_path / "llm_cache")
    monkeypatch.setattr(llm_store, "JOURNAL_FILE", tmp_path / "llm_runs.jsonl")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    llm_runtime.reset_runtime()
    yield
    llm_runtime.reset_runtime()


class TestRuntime:
    def test_unconfigured_env_uses_mock(self):
        assert get_runtime().kind == "mock"
        assert get_runtime().model == "mock-deterministic"

    def test_configured_env_builds_real_runtime(self, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com/v1")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        llm_runtime.reset_runtime()
        rt = get_runtime()
        assert isinstance(rt, LLMRuntime)
        assert rt.model == "test-model"
        assert rt.config.base_url == "https://api.example.com/v1"

    def test_mock_output_is_deterministic(self):
        kwargs = {"purpose": "judge", "system": "s", "user": "[评分对象]\n结论:拥堵路段 3 个,建议分流" + "x" * 50}
        rt = MockLLMRuntime()
        assert rt.complete_json(**kwargs) == rt.complete_json(**kwargs)

    def test_cache_roundtrip(self):
        key = llm_store.cache_key("m", "p", "s", "u")
        assert llm_store.cache_get(key) is None
        llm_store.cache_put(key, {"score": 0.9})
        assert llm_store.cache_get(key) == {"score": 0.9}
        assert llm_store.cache_key("m", "p", "s", "u") == key          # 稳定
        assert llm_store.cache_key("m2", "p", "s", "u") != key         # 不同输入不同键

    def test_journal_records_calls(self):
        MockLLMRuntime().complete_json(purpose="judge", system="s", user="u")
        MockLLMRuntime().complete_json(purpose="draft", system="s", user="u")
        entries = llm_store.journal_tail(5)
        assert [e["purpose"] for e in entries] == ["judge", "draft"]
        assert all(e["model"] == "mock-deterministic" and not e["cache_hit"] for e in entries)

    def test_parse_json_content_tolerates_code_fence(self):
        assert llm_runtime._parse_json_content('```json\n{"a": 1}\n```') == {"a": 1}
        assert llm_runtime._parse_json_content('{"a": 2}') == {"a": 2}
        with pytest.raises(llm_runtime.LLMError):
            llm_runtime._parse_json_content("不是 JSON")


class TestLLMJudge:
    OUTPUT = {
        "summary": "共分析 10 个路段:拥堵 3 个、严重拥堵 1 个,全局拥堵指数 0.82,建议对主干道分流。",
        "recommendations": [{"segment_id": "S-02", "text": "学府路:建议优化信号配时并引导绕行。"}],
    }

    def test_scores_good_conclusion_above_threshold(self):
        from harness.models import CheckSpec

        spec = CheckSpec(type="conclusion_quality", min_score=0.8)
        result = LLMJudge(MockLLMRuntime()).judge_one(spec, self.OUTPUT, None)
        assert result.actual >= 0.8 and result.passed
        assert "Mock" in result.detail or "评分" in result.detail

    def test_strict_threshold_can_fail(self):
        from harness.models import CheckSpec

        spec = CheckSpec(type="conclusion_quality", min_score=0.95)
        result = LLMJudge(MockLLMRuntime()).judge_one(spec, {"summary": "短"}, None)
        assert not result.passed

    def test_crash_output_fails_without_llm_call(self):
        from harness.models import CheckSpec

        result = LLMJudge(MockLLMRuntime()).judge_one(
            CheckSpec(type="conclusion_quality"), None, "ZeroDivisionError")
        assert not result.passed and "崩溃" in result.detail

    def test_llm_failure_degrades_to_failed_visible(self, monkeypatch):
        """LLM 异常不允许炸掉评测:降级为未通过且原因可见(治理要求)。"""
        from harness.models import CheckSpec

        class Boom:
            model = "boom"

            def complete_json(self, **kw):
                raise llm_runtime.LLMError("断网了")

        result = LLMJudge(Boom()).judge_one(CheckSpec(type="conclusion_quality"), self.OUTPUT, None)
        assert not result.passed and "断网了" in result.detail

    def test_composite_judge_routes_conclusion_quality(self):
        """默认 CompositeJudge 挂载 LLMJudge,新增检查类型可路由(未配置时为 Mock)。"""
        from harness.judge import CompositeJudge
        from harness.models import CheckSpec

        judge = CompositeJudge()
        result = judge.judge_one(CheckSpec(type="conclusion_quality", min_score=0.3), self.OUTPUT, None)
        assert result.passed  # mock 对高质量文本给高分


class TestDraftWorkflow:
    def test_draft_creates_pending_record(self, hermetic_storage):
        draft = draft_replaycase("用户点踩:学府路 V/C 0.91 被误判为缓行,应为拥堵", "base", "S-02")
        assert draft["status"] == "pending"
        assert draft["draft_id"] == "draft-0001"
        assert draft["segment_id"] == "S-02"
        assert draft["expected_level"] == "拥堵"
        assert draft["llm"]["model"] == "mock-deterministic"
        assert llm_store.load_draft("draft-0001")["title"] == draft["title"]

    def test_draft_ids_increment(self, hermetic_storage):
        d1 = draft_replaycase("反馈一:城东大道判错了,应为畅通", "base", "S-01")
        d2 = draft_replaycase("反馈二:长江路建议缺失", "base", "S-03")
        assert (d1["draft_id"], d2["draft_id"]) == ("draft-0001", "draft-0002")

    def test_draft_validates_segment(self, hermetic_storage):
        with pytest.raises(ValueError):
            draft_replaycase("反馈内容足够长的一段文字", "base", "S-999")

    def test_draft_validates_complaint_length(self, hermetic_storage):
        with pytest.raises(ValueError):
            draft_replaycase("短", "base")

    def test_draft_rejects_unknown_dataset(self, hermetic_storage):
        with pytest.raises(FileNotFoundError):
            draft_replaycase("反馈内容足够长的一段文字", "no-such-dataset")


class TestDiagnoseWorkflow:
    def test_diagnose_groups_failures_by_label(self, hermetic_storage):
        out = diagnose_failures("v0", "evalset_v1")
        assert out["meta"]["failure_count"] == 12
        labels = {it["label"] for it in out["items"]}
        assert "阈值错误" in labels and "健壮性" in labels
        all_ids = {cid for it in out["items"] for cid in it["affected_cases"]}
        assert all_ids  # 每条建议都挂了真实 case
        assert out["reviewer_notes"]

    def test_diagnose_all_passed_yields_empty(self, hermetic_storage):
        out = diagnose_failures("v2", "evalset_v1")
        assert out["items"] == [] and "全部案例通过" in out["reviewer_notes"]

    def test_diagnose_rejects_unknown_version(self, hermetic_storage):
        with pytest.raises(ValueError):
            diagnose_failures("v9")

    def test_hallucinated_case_ids_filtered(self, monkeypatch, hermetic_storage):
        """治理:评审者引用不存在的 case_id 会被过滤,不落入结果。"""
        from llm import workflows

        class FakeRuntime(MockLLMRuntime):
            def complete_json(self, *, purpose, system, user, max_chars=6000):
                if purpose == "diagnose-review":
                    return {"items": [{"label": "阈值错误", "root_cause": "r",
                                       "suggestions": ["s"], "affected_cases": ["rc-9999"]}],
                            "reviewer_notes": "n"}
                return super().complete_json(purpose=purpose, system=system, user=user)

        monkeypatch.setattr(workflows, "get_runtime", lambda: FakeRuntime())
        out = workflows.diagnose_failures("v0", "evalset_v1")
        target = next(it for it in out["items"] if it["label"] == "阈值错误")
        assert "rc-9999" not in target["affected_cases"]  # 幻觉 id 被替换为真实失败集
        assert target["affected_cases"]


class TestLLMApi:
    def test_status(self, authed_client):
        body = authed_client.get("/api/llm/status").json()
        assert body["kind"] == "mock"
        assert body["configured"] is False
        assert "cache_count" in body

    def test_draft_confirm_flow(self, authed_client, hermetic_storage):
        draft = authed_client.post("/api/llm/drafts", json={
            "complaint": "用户点踩:学府路 V/C 0.91 被误判为缓行,应为拥堵",
            "dataset_name": "base", "segment_id": "S-02"}).json()
        assert draft["status"] == "pending"

        confirmed = authed_client.post(f"/api/llm/drafts/{draft['draft_id']}/confirm", json={
            "notes": "AI 起草,人工核对"}).json()
        assert confirmed["added_to_evalset"] is True
        case_id = confirmed["case"]["case_id"]
        assert confirmed["case"]["source"] == "LLM 草稿·人工确认"

        cases = {c["case_id"] for c in authed_client.get("/api/cases").json()}
        assert case_id in cases
        drafts = {d["draft_id"]: d for d in authed_client.get("/api/llm/drafts").json()}
        assert drafts[draft["draft_id"]]["status"] == "confirmed"
        assert drafts[draft["draft_id"]]["confirmed_case_id"] == case_id

    def test_confirm_twice_conflicts(self, authed_client, hermetic_storage):
        draft = authed_client.post("/api/llm/drafts", json={
            "complaint": "反馈:环北路结果与实际不符,应保持畅通级别", "dataset_name": "base"}).json()
        authed_client.post(f"/api/llm/drafts/{draft['draft_id']}/confirm", json={})
        resp = authed_client.post(f"/api/llm/drafts/{draft['draft_id']}/confirm", json={})
        assert resp.status_code == 409

    def test_confirm_with_invalid_level_rejected(self, authed_client, hermetic_storage):
        """治理:人工确认也不能绕过校验 —— 非法等级在统一校验路径被拒。"""
        draft = authed_client.post("/api/llm/drafts", json={
            "complaint": "反馈:解放西路分类有问题,应为缓行", "dataset_name": "base"}).json()
        resp = authed_client.post(f"/api/llm/drafts/{draft['draft_id']}/confirm",
                                  json={"expected_level": "飞行"})
        assert resp.status_code == 400

    def test_discard_draft(self, authed_client, hermetic_storage):
        draft = authed_client.post("/api/llm/drafts", json={
            "complaint": "反馈:文昌桥延误指数方向不对,应为正值", "dataset_name": "base"}).json()
        assert authed_client.delete(f"/api/llm/drafts/{draft['draft_id']}").status_code == 200
        assert authed_client.delete(f"/api/llm/drafts/{draft['draft_id']}").status_code == 404

    def test_diagnose_api(self, authed_client, hermetic_storage):
        body = authed_client.post("/api/llm/diagnose",
                                  json={"version": "v0", "evalset": "evalset_v1"}).json()
        assert body["items"] and body["meta"]["failure_count"] == 12
        assert authed_client.post("/api/llm/diagnose", json={"version": "v9"}).status_code == 400


def test_backup_script_packages_assets(tmp_path):
    """运维:备份脚本应把评测资产打成带时间戳的 zip。"""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from backup import create_backup

    path = create_backup(tmp_path / "backups")
    assert path.exists() and path.name.startswith("harness_backup_")
    import zipfile

    names = zipfile.ZipFile(path).namelist()
    assert any(n.startswith("cases/") for n in names)
    assert any(n.startswith("evalsets/") for n in names)
    assert any(n.startswith("reports/") for n in names)
