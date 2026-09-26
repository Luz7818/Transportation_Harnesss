"""/api/settings:准入判定(公网默认拒绝)、密钥掩码、原子写 .env 与"重启才生效"边界。

全部用例都跑在 tests/conftest 的 _hermetic_dotenv 夹具上:.env 与备份落在临时目录,
绝不会写到仓库里现存的 .env;被改过的环境变量在用例结束后还原。
"""

import os

import pytest
from webapp import settings as settings_mod

SECRET_IN_FILE = "sk-should-never-echo-1234567890"


@pytest.fixture
def settings_on(monkeypatch):
    """打开总开关(等价于服务启动时设了 SETTINGS_ENABLED=1)。"""
    import webapp.app as app_mod

    monkeypatch.setattr(app_mod, "SETTINGS_ENABLED", True)
    return app_mod


@pytest.fixture
def seeded_env():
    """在临时目录放一份带注释与真实密钥的 .env(热键先由 client 夹具从环境里清掉)。"""
    settings_mod.ENV_FILE.write_text(
        "# 本机接入配置(不入库)\n"
        "LLM_BASE_URL=http://mock.test/v1\n"
        f"LLM_API_KEY={SECRET_IN_FILE}\n"
        "LLM_MODEL=mock-model\n",
        encoding="utf-8",
    )
    return settings_mod.ENV_FILE


def entry_of(snapshot: dict, key: str) -> dict:
    """从快照的两组里取出某个键的条目,并标注它属于哪一组。"""
    for group in ("hot_reloaded", "requires_restart"):
        for item in snapshot[group]:
            if item["key"] == key:
                return {**item, "_group": group}
    raise AssertionError(f"快照里没有 {key}")


class TestAccessControl:
    """默认关闭 + 只认"本机直连"或"已鉴权会话",X-API-Token 不算会话。"""

    def test_disabled_by_default_even_on_loopback(self, loopback_client):
        resp = loopback_client.get("/api/settings")
        assert resp.status_code == 403
        assert "SETTINGS_ENABLED" in resp.json()["detail"]

    def test_disabled_by_default_even_with_session(self, authed_client):
        assert authed_client.get("/api/settings").status_code == 403

    def test_public_request_without_session_is_403(self, settings_on, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        for hint in ("本机", "login", "Bearer"):       # detail 必须可操作:说清怎么才能用
            assert hint in detail

    def test_machine_token_is_not_a_session(self, settings_on, client, api_token):
        """小程序/脚本共用 X-API-Token,拿它就能改服务器配置等于泄露写入权。"""
        headers = {"X-API-Token": api_token}
        assert client.get("/api/cases", headers=headers).status_code == 200
        assert client.get("/api/settings", headers=headers).status_code == 403
        assert client.put("/api/settings", json={"values": {"LLM_MODEL": "x"}},
                          headers=headers).status_code == 403

    def test_cookie_session_allowed_from_remote(self, settings_on, authed_client):
        assert authed_client.get("/api/settings").status_code == 200

    def test_bearer_session_allowed_from_remote(self, settings_on, bearer_client):
        assert bearer_client.get("/api/settings").status_code == 200
        resp = bearer_client.put("/api/settings", json={"values": {"LLM_MODEL": "qwen-max"}})
        assert resp.status_code == 200

    def test_loopback_direct_allowed(self, settings_on, loopback_client):
        assert loopback_client.get("/api/settings").status_code == 200

    def test_via_reverse_proxy_is_not_loopback(self, settings_on, loopback_client):
        """反代之后对端地址恒为 127.0.0.1:带转发头的请求不能冒充本机。"""
        for header in ("X-Forwarded-For", "X-Real-IP", "Forwarded"):
            resp = loopback_client.get("/api/settings", headers={header: "127.0.0.1"})
            assert resp.status_code == 403, header

    def test_open_auth_mode_does_not_bypass_settings_gate(self, settings_on, make_client,
                                                          monkeypatch):
        """AUTH_MODE=open 只是免登录演示,不给 /api/settings 开后门。"""
        import webapp.app as app_mod

        monkeypatch.setattr(app_mod, "AUTH_MODE", "open")
        assert make_client().get("/api/settings").status_code == 403


class TestMasking:
    def test_mask_shape(self):
        assert settings_mod.mask_secret("") == ""
        # 用中性串:掩码形状与被掩码的值本身无关,不该拿任何真实凭据当夹具
        assert settings_mod.mask_secret("abcdefghij") == "ab***(10)"
        assert "cdefghij" not in settings_mod.mask_secret("abcdefghij")

    def test_secrets_never_returned_in_plaintext(self, settings_on, loopback_client, seeded_env):
        body = loopback_client.get("/api/settings").json()
        entry = entry_of(body, "LLM_API_KEY")
        assert entry["secret"] is True
        assert entry["set"] is True
        assert entry["value"] == f"{SECRET_IN_FILE[:2]}***({len(SECRET_IN_FILE)})"
        assert entry["source"] == "file"

    def test_full_response_free_of_plaintext_secrets(self, settings_on, loopback_client,
                                                     seeded_env):
        resp = loopback_client.get("/api/settings")
        assert SECRET_IN_FILE not in resp.text
        assert resp.json()["secrets_masked"] is True

    def test_non_secret_values_are_shown(self, settings_on, loopback_client, seeded_env):
        body = loopback_client.get("/api/settings").json()
        assert entry_of(body, "LLM_MODEL")["value"] == "mock-model"
        assert entry_of(body, "LLM_MODEL")["secret"] is False
        assert entry_of(body, "LLM_BASE_URL")["value"] == "http://mock.test/v1"

    def test_groups_separate_hot_from_restart_keys(self, settings_on, loopback_client):
        body = loopback_client.get("/api/settings").json()
        assert entry_of(body, "LLM_MODEL")["_group"] == "hot_reloaded"
        for key in ("AUTH_TOKEN", "ADMIN_PASSWORD", "CORS_ORIGINS", "SETTINGS_ENABLED"):
            assert entry_of(body, key)["_group"] == "requires_restart"
        assert "重启" in body["note"]                   # 响应里要说清改这些要重启

    def test_write_then_get_keeps_secret_masked(self, settings_on, loopback_client, api_token):
        token = "a-long-machine-token-value-1234"
        resp = loopback_client.put("/api/settings", json={"values": {"AUTH_TOKEN": token}})
        assert resp.status_code == 200
        assert token not in resp.text                             # PUT 的回显同样掩码
        snapshot = loopback_client.get("/api/settings").json()
        entry = entry_of(snapshot, "AUTH_TOKEN")
        # AUTH_TOKEN 是启动期才生效的键:接口回的是"当前生效值"(仍是旧令牌),
        # 新令牌只写进了 .env,重启后才生效 —— 所以既无法掩码骗过人,也无法在线换掉它
        assert entry["value"] == api_token[:2] + f"***({len(api_token)})"
        assert "AUTH_TOKEN" in snapshot["restart_pending_keys"]
        assert token in settings_mod.ENV_FILE.read_text(encoding="utf-8")


class TestWrite:
    def test_hot_key_written_and_applied(self, settings_on, loopback_client, seeded_env):
        resp = loopback_client.put("/api/settings", json={"values": {"LLM_MODEL": "deepseek-chat"}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["hot_reloaded"] == ["LLM_MODEL"] and body["requires_restart"] == []
        assert os.environ["LLM_MODEL"] == "deepseek-chat"          # 立刻生效
        text = seeded_env.read_text(encoding="utf-8")
        assert "LLM_MODEL=deepseek-chat" in text
        assert "# 本机接入配置(不入库)" in text                    # 注释原样保留
        assert "LLM_BASE_URL=http://mock.test/v1" in text          # 未碰的键不动

    def test_backup_written_before_replace(self, settings_on, loopback_client, seeded_env):
        loopback_client.put("/api/settings", json={"values": {"LLM_MODEL": "m2"}})
        backups = list(settings_mod.BACKUP_DIR.glob("env.*.bak"))
        assert len(backups) == 1
        assert SECRET_IN_FILE in backups[0].read_text(encoding="utf-8")
        assert "LLM_MODEL=m2" not in backups[0].read_text(encoding="utf-8")

    def test_no_temp_file_left_behind(self, settings_on, loopback_client, seeded_env):
        loopback_client.put("/api/settings", json={"values": {"LLM_MODEL": "m3"}})
        assert not list(seeded_env.parent.glob(".env.tmp*"))

    def test_empty_string_removes_the_key(self, settings_on, loopback_client, seeded_env):
        resp = loopback_client.put("/api/settings", json={"values": {"LLM_MODEL": ""}})
        assert resp.status_code == 200
        assert resp.json()["removed"] == ["LLM_MODEL"]
        assert "LLM_MODEL" not in seeded_env.read_text(encoding="utf-8")
        assert "LLM_MODEL" not in os.environ

    def test_new_key_appended_and_reported_as_restart_pending(self, settings_on,
                                                              loopback_client, seeded_env):
        resp = loopback_client.put("/api/settings",
                                   json={"values": {"CORS_ORIGINS": "https://harness.example.com"}})
        assert resp.status_code == 200
        assert resp.json()["requires_restart"] == ["CORS_ORIGINS"]
        assert "CORS_ORIGINS=https://harness.example.com" in seeded_env.read_text(encoding="utf-8")
        snap = loopback_client.get("/api/settings").json()
        assert "CORS_ORIGINS" in snap["restart_pending_keys"]      # 文件已改,进程还没读到

    def test_restart_only_key_cannot_hot_swap_the_live_token(self, settings_on,
                                                             loopback_client, client, api_token):
        """改 AUTH_TOKEN 只落盘:正在生效的机器令牌不变,新令牌签不出访问权。"""
        import webapp.app as app_mod

        fresh = "brand-new-machine-token-9999"
        assert client.get("/api/cases", headers={"X-API-Token": api_token}).status_code == 200
        resp = loopback_client.put("/api/settings", json={"values": {"AUTH_TOKEN": fresh}})
        assert resp.status_code == 200
        assert api_token == app_mod.AUTH_TOKEN                      # 进程内取值未被改写
        assert client.get("/api/cases", headers={"X-API-Token": fresh}).status_code == 401
        assert client.get("/api/cases", headers={"X-API-Token": api_token}).status_code == 200

    def test_settings_enabled_switch_itself_needs_restart(self, settings_on, loopback_client):
        resp = loopback_client.put("/api/settings", json={"values": {"SETTINGS_ENABLED": "0"}})
        assert resp.status_code == 200
        assert resp.json()["requires_restart"] == ["SETTINGS_ENABLED"]


class TestValidation:
    """非法值一律 400 且不写盘。"""

    def _reject(self, http, values, expect_fragment=""):
        before = settings_mod.ENV_FILE.read_text(encoding="utf-8") if settings_mod.ENV_FILE.exists() else None
        resp = http.put("/api/settings", json={"values": values})
        assert resp.status_code == 400, values
        if expect_fragment:
            assert expect_fragment in resp.json()["detail"]
        after = settings_mod.ENV_FILE.read_text(encoding="utf-8") if settings_mod.ENV_FILE.exists() else None
        assert after == before                                      # 校验失败不留半个字节
        return resp.json()["detail"]

    def test_rejects_newline_injection(self, settings_on, loopback_client, seeded_env):
        detail = self._reject(loopback_client, {"LLM_MODEL": "gpt\nAUTH_TOKEN=hacked"}, "换行")
        assert "hacked" not in seeded_env.read_text(encoding="utf-8")
        assert "AUTH_TOKEN" not in seeded_env.read_text(encoding="utf-8")
        assert detail

    def test_rejects_control_characters(self, settings_on, loopback_client, seeded_env):
        self._reject(loopback_client, {"LLM_MODEL": "gpt\x00x"}, "控制字符")

    def test_rejects_unknown_key(self, settings_on, loopback_client, seeded_env):
        self._reject(loopback_client, {"rm_rf": "x"}, "未知配置项")

    def test_rejects_non_string_value(self, settings_on, loopback_client, seeded_env):
        self._reject(loopback_client, {"PORT": 8765}, "字符串")

    def test_rejects_empty_values(self, settings_on, loopback_client, seeded_env):
        self._reject(loopback_client, {}, "values")

    def test_rejects_bad_port(self, settings_on, loopback_client, seeded_env):
        self._reject(loopback_client, {"PORT": "99999"}, "PORT")

    def test_rejects_bad_auth_mode(self, settings_on, loopback_client, seeded_env):
        self._reject(loopback_client, {"AUTH_MODE": "anonymous"}, "AUTH_MODE")

    def test_rejects_non_origin_cors(self, settings_on, loopback_client, seeded_env):
        self._reject(loopback_client, {"CORS_ORIGINS": "javascript:alert(1)"}, "CORS_ORIGINS")

    def test_rejects_bad_llm_extra_body(self, settings_on, loopback_client, seeded_env):
        self._reject(loopback_client, {"LLM_EXTRA_BODY": "[1,2]"}, "JSON 对象")
        self._reject(loopback_client, {"LLM_EXTRA_BODY": "not-json"}, "JSON")

    def test_rejects_weak_token_and_short_password(self, settings_on, loopback_client, seeded_env):
        self._reject(loopback_client, {"AUTH_TOKEN": "short"}, "AUTH_TOKEN")
        self._reject(loopback_client, {"ADMIN_PASSWORD": "123"}, "6~64")

    def test_strips_surrounding_whitespace(self, settings_on, loopback_client, seeded_env):
        assert loopback_client.put("/api/settings",
                                   json={"values": {"LLM_MODEL": "  deepseek-chat  "}}
                                   ).status_code == 200
        assert "LLM_MODEL=deepseek-chat\n" in seeded_env.read_text(encoding="utf-8")


class TestModuleUnit:
    def test_compose_merges_duplicate_keys(self, seeded_env):
        """同名重复行合并成一条,避免"改了但被后面那行覆盖"。"""
        settings_mod.ENV_FILE.write_text(
            "LLM_MODEL=first\nLLM_MODEL=second\n", encoding="utf-8")
        settings_mod.write_env_file({"LLM_MODEL": "final"})
        assert settings_mod.ENV_FILE.read_text(encoding="utf-8").splitlines() == ["LLM_MODEL=final"]

    def test_read_env_file_ignores_comments(self, seeded_env):
        values = settings_mod.read_env_file()
        assert values["LLM_MODEL"] == "mock-model"
        assert not any(k.startswith("#") for k in values)

    def test_clean_updates_rejects_unsupported_key(self):
        with pytest.raises(ValueError, match="未知配置项"):
            settings_mod.clean_updates({"nope": "1"})

    def test_every_spec_key_is_unique(self):
        keys = [spec.key for spec in settings_mod.SETTING_SPECS]
        assert len(keys) == len(set(keys))
