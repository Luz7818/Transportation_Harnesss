"""Web API:鉴权(三种凭据)、评测集选择、case 生命周期、评测与自进化端点。"""

import time


class TestAuthFlow:
    def test_health_open_without_login(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["case_count"] > 0
        assert body["evalset_count"] >= 2

    def test_protected_api_requires_login(self, client):
        assert client.get("/api/cases").status_code == 401
        assert client.get("/api/versions").status_code == 401

    def test_login_success_sets_cookie(self, client, admin_credentials):
        username, password = admin_credentials
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        assert resp.status_code == 200
        assert "harness_session" in resp.cookies
        assert client.get("/api/auth/me").json()["username"] == username

    def test_login_returns_bearer_token_and_expiry(self, client, admin_credentials):
        """契约:登录响应体除 ok/username 外还带 token(与 Cookie 同值)与 expires_at(unix 秒)。"""
        username, password = admin_credentials
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        body = resp.json()
        assert body["ok"] is True and body["username"] == username
        assert isinstance(body["token"], str) and body["token"]
        cookie = resp.headers["set-cookie"]
        assert body["token"] in cookie                     # 同一枚令牌,Cookie 与 body 二选一即可
        assert isinstance(body["expires_at"], int)
        assert body["expires_at"] > int(time.time())       # 有效期在未来

    def test_login_failure_body_is_detail_only(self, client, admin_credentials):
        resp = client.post("/api/auth/login",
                           json={"username": admin_credentials[0], "password": "nope"})
        assert resp.status_code == 401
        assert set(resp.json()) == {"detail"}              # 401 响应体保持 {detail: "..."}

    def test_login_wrong_password(self, client):
        assert client.post("/api/auth/login",
                           json={"username": "admin", "password": "nope"}).status_code == 401

    def test_logout_invalidates_session(self, authed_client):
        assert authed_client.post("/api/auth/logout", json={}).status_code == 200
        assert authed_client.get("/api/auth/me").status_code == 401

    def test_api_token_grants_access(self, client, api_token):
        resp = client.get("/api/cases", headers={"X-API-Token": api_token})
        assert resp.status_code == 200

    def test_bearer_token_grants_access_without_cookie(self, bearer_client):
        """小程序通道:无 Cookie,只靠 Authorization: Bearer <会话令牌>。"""
        assert bearer_client.get("/api/cases").status_code == 200
        assert bearer_client.get("/api/auth/me").json()["username"] == "admin"

    def test_bearer_header_must_be_a_valid_session_token(self, client, admin_credentials):
        username, password = admin_credentials
        token = client.post("/api/auth/login",
                            json={"username": username, "password": password}).json()["token"]
        client.cookies.clear()
        # 方案名不是 Bearer / 空令牌 / 签名被改 —— 三种都不认
        assert client.get("/api/cases",
                          headers={"Authorization": f"Basic {token}"}).status_code == 401
        assert client.get("/api/cases", headers={"Authorization": "Bearer "}).status_code == 401
        assert client.get("/api/cases",
                          headers={"Authorization": f"Bearer {token[:-2]}xx"}).status_code == 401
        assert client.get("/api/cases", headers={"Authorization": f"bearer {token}"}).status_code == 200

    def test_logout_keeps_bearer_token_valid_until_expiry(self, bearer_client):
        """登出只清 Cookie;HMAC 会话令牌是无状态的,到期前依旧有效(小程序契约需知)。"""
        assert bearer_client.post("/api/auth/logout", json={}).status_code == 200
        assert bearer_client.get("/api/cases").status_code == 200

    def test_expired_bearer_token_rejected(self, bearer_client, monkeypatch):
        from webapp import app as app_mod
        from webapp import auth as auth_mod

        with monkeypatch.context() as m:
            m.setattr(auth_mod, "SESSION_TTL", -1)         # 签出一枚已过期令牌
            expired = auth_mod.make_token(app_mod._AUTH_STORE, "admin")
        resp = bearer_client.get("/api/cases", headers={"Authorization": f"Bearer {expired}"})
        assert resp.status_code == 401


class TestEvalsets:
    def test_list_evalsets(self, authed_client):
        body = authed_client.get("/api/evalsets").json()
        ids = {e["evalset_id"] for e in body}
        assert {"evalset_v1", "evalset_scenario_rain"} <= ids
        for e in body:
            assert e["case_count"] > 0

    def test_eval_run_on_scenario_evalset(self, authed_client, hermetic_storage):
        resp = authed_client.post("/api/eval/run",
                                  json={"version": "v2", "evalset": "evalset_scenario_rain"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3 and body["accuracy"] == 1.0

    def test_eval_run_unknown_evalset_404(self, authed_client):
        resp = authed_client.post("/api/eval/run",
                                  json={"version": "v2", "evalset": "nope"})
        assert resp.status_code == 404

    def test_eval_run_unknown_version_404(self, authed_client):
        resp = authed_client.post("/api/eval/run", json={"version": "v9"})
        assert resp.status_code == 404

    def test_evolve_run_accepts_evalset_body(self, authed_client, hermetic_storage):
        resp = authed_client.post("/api/evolve/run", json={"evalset": "evalset_scenario_rain"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["evalset_id"] == "evalset_scenario_rain"
        assert body["best"]["accuracy"] == 1.0

    def test_evolve_run_without_body_defaults(self, authed_client, hermetic_storage):
        """旧客户端不传 body 时兼容:默认 evalset_v1。"""
        resp = authed_client.post("/api/evolve/run")
        assert resp.status_code == 200
        assert resp.json()["evalset_id"] == "evalset_v1"


class TestCaseLifecycle:
    def test_create_and_list_case(self, authed_client, hermetic_storage):
        resp = authed_client.post("/api/cases", json={
            "title": "单元测试沉淀的 case", "label": "测试标签", "dataset_name": "base",
            "segment": "S-01", "expected_level": "畅通",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["added_to_evalset"] is True
        assert body["case"]["case_id"].startswith("rc-")

        cases = {c["case_id"]: c for c in authed_client.get("/api/cases").json()}
        assert body["case"]["case_id"] in cases

    def test_create_case_validations(self, authed_client, hermetic_storage):
        base = {"title": "t", "label": "l", "dataset_name": "base",
                "segment": "S-01", "expected_level": "畅通"}
        assert authed_client.post("/api/cases",
                                  json={**base, "title": ""}).status_code == 400
        assert authed_client.post("/api/cases",
                                  json={**base, "segment": "S-99"}).status_code == 400
        assert authed_client.post("/api/cases",
                                  json={**base, "expected_level": "飞行"}).status_code == 400
        assert authed_client.post("/api/cases",
                                  json={**base, "dataset_name": "../../etc"}).status_code in (400, 404)

    def test_delete_case_syncs_evalsets(self, authed_client, hermetic_storage):
        created = authed_client.post("/api/cases", json={
            "title": "待删除", "label": "测试标签", "dataset_name": "base",
            "segment": "S-01", "expected_level": "畅通",
        }).json()["case"]["case_id"]
        assert authed_client.delete(f"/api/cases/{created}").status_code == 200
        assert authed_client.delete(f"/api/cases/{created}").status_code == 404
        manifest = authed_client.get("/api/evalsets").json()
        v1 = next(e for e in manifest if e["evalset_id"] == "evalset_v1")
        assert v1["case_count"] == 13  # 删除后清单同步收缩,不悬空


class TestDocs:
    def test_help_center_served(self, client):
        """文档中心是产品的一部分:/help 无需登录即可访问,内容完整。"""
        resp = client.get("/help")
        assert resp.status_code == 200
        for fragment in ("快速开始", "核心概念", "鉴权方式", "API · 认证与会话",
                         "错误码约定", "端到端完整示例", "常见问题"):
            assert fragment in resp.text

    def test_index_served(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Transportation Harness" in resp.text


class TestAnalyzeAndCompare:
    def test_analyze(self, authed_client):
        resp = authed_client.post("/api/analyze",
                                  json={"version": "v2", "dataset_name": "base"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["segments"]) > 0
        assert body["summary"]

    def test_analyze_empty_dataset_degrades(self, authed_client):
        resp = authed_client.post("/api/analyze",
                                  json={"version": "v2", "dataset_name": "empty"})
        assert resp.status_code == 200
        assert resp.json()["segments"] == []

    def test_compare_reports(self, authed_client, hermetic_storage):
        authed_client.post("/api/eval/run", json={"version": "v0"})
        authed_client.post("/api/eval/run", json={"version": "v2"})
        reports = authed_client.get("/api/reports").json()
        by_version = {r["version"]: r["report_id"] for r in reports}
        resp = authed_client.get(
            f"/api/compare?a={by_version['v0']}&b={by_version['v2']}")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["newly_passed"]) >= 12
        assert body["regressed"] == []

    def test_report_id_traversal_rejected(self, authed_client):
        resp = authed_client.get("/api/reports/..%2F..%2Fwebapp%2Fauth")
        assert resp.status_code in (400, 404)


class TestOpsApi:
    def test_case_detail_endpoint(self, authed_client, hermetic_storage):
        body = authed_client.get("/api/cases/rc-0001").json()
        assert body["case_id"] == "rc-0001"
        assert body["checks"]
        assert authed_client.get("/api/cases/rc-9999").status_code == 404

    def test_health_exposes_app_version(self, client):
        body = client.get("/api/health").json()
        assert body["app_version"]
        assert body["versions"] == ["v0", "v1", "v2"]

    def test_evolve_with_baseline_param(self, authed_client, hermetic_storage):
        """API 支持指定基线:以 v1 为基线增量验证 v2。"""
        resp = authed_client.post("/api/evolve/run",
                                  json={"evalset": "evalset_v1", "baseline": "v1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["baseline"]["version"] == "v1"
        assert [r["version"] for r in body["rounds"]] == ["v2"]

    def test_evolve_unknown_baseline_404(self, authed_client, hermetic_storage):
        resp = authed_client.post("/api/evolve/run", json={"baseline": "v9"})
        assert resp.status_code == 404


class TestBatchOpsAndDiff:
    def test_compare_includes_check_diffs(self, authed_client, hermetic_storage):
        """v0 → v2 对比应给出 checks 级差分:rc-0001 的判分明细从失败变通过。"""
        authed_client.post("/api/eval/run", json={"version": "v0"})
        authed_client.post("/api/eval/run", json={"version": "v2"})
        reports = authed_client.get("/api/reports").json()
        by_version = {r["version"]: r["report_id"] for r in reports}
        body = authed_client.get(
            f"/api/compare?a={by_version['v0']}&b={by_version['v2']}").json()
        row = next(r for r in body["rows"] if r["case_id"] == "rc-0001")
        assert row["check_diffs"], "变化的 case 应携带 checks 级差分"
        assert any(d["status"] == "fixed" for d in row["check_diffs"])
        fixed = next(d for d in row["check_diffs"] if d["status"] == "fixed")
        assert fixed["type"] in ("classify", "metric")
        assert fixed["b_detail"]  # 修复后的判分明细可展示

    def test_compare_same_pass_has_empty_diffs(self, authed_client, hermetic_storage):
        authed_client.post("/api/eval/run", json={"version": "v1"})
        authed_client.post("/api/eval/run", json={"version": "v2"})
        reports = authed_client.get("/api/reports").json()
        by_version = {r["version"]: r["report_id"] for r in reports}
        body = authed_client.get(
            f"/api/compare?a={by_version['v1']}&b={by_version['v2']}").json()
        passed_rows = [r for r in body["rows"]
                       if r["a_passed"] and r["b_passed"] and r["case_id"] in
                       {c["case_id"] for c in authed_client.get("/api/cases").json()
                        if c["case_id"] <= "rc-0008"}]
        assert all(not r["check_diffs"] for r in passed_rows[:3])

    def test_batch_delete(self, authed_client, hermetic_storage):
        """批量删除:存在的删除、不存在的进 missing;评测集清单同步收缩。"""
        ids = []
        for i in range(2):
            ids.append(authed_client.post("/api/cases", json={
                "title": f"批量{i}", "label": "批量测试", "dataset_name": "base",
                "segment": "S-01", "expected_level": "畅通",
            }).json()["case"]["case_id"])
        body = authed_client.post("/api/cases/batch-delete",
                                  json={"ids": ids + ["rc-9999"]}).json()
        assert sorted(body["deleted"]) == sorted(ids)
        assert body["missing"] == ["rc-9999"]
        remaining = {c["case_id"] for c in authed_client.get("/api/cases").json()}
        assert not set(ids) & remaining
