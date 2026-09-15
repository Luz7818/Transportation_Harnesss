"""webapp.auth:口令哈希、旧哈希透明升级、登录限流、会话令牌。"""

import pytest
from webapp import auth as auth_mod


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_mod, "AUTH_FILE", tmp_path / "auth.json")
    return auth_mod.load_store()


def test_pbkdf2_hash_roundtrip(store):
    user = store["users"][0]
    assert user["password_hash"].startswith("pbkdf2_sha256$")
    assert "harness123" not in user["password_hash"]
    assert auth_mod._verify_hash(user, "harness123")
    assert not auth_mod._verify_hash(user, "wrong")


def test_password_never_stored_plaintext(store):
    blob = auth_mod.AUTH_FILE.read_text(encoding="utf-8")
    assert "harness123" not in blob


def test_legacy_sha256_hash_upgrades_on_verify(store, monkeypatch):
    """v1.2 的单轮 SHA-256 哈希应能登录,并透明升级为 PBKDF2。"""
    import hashlib
    import secrets

    salt = secrets.token_hex(8)
    user = {"username": "legacy", "salt": salt,
            "password_hash": hashlib.sha256(f"{salt}:old-pass".encode()).hexdigest()}
    store["users"].append(user)
    assert auth_mod.verify_password(store, "legacy", "old-pass")
    assert user["password_hash"].startswith("pbkdf2_sha256$")
    # 升级后旧口令依然可登录、新口令不可
    assert auth_mod.verify_password(store, "legacy", "old-pass")
    assert not auth_mod.verify_password(store, "legacy", "other")


def test_verify_password_rejects_unknown_user(store):
    assert not auth_mod.verify_password(store, "nobody", "whatever")


def test_login_lockout_after_repeated_failures(store):
    for _ in range(auth_mod.LOCKOUT_THRESHOLD):
        assert not auth_mod.verify_password(store, "admin", "bad-pass")
    assert auth_mod.login_locked("admin") > 0
    # 锁定期内即使口令正确也拒绝
    assert not auth_mod.verify_password(store, "admin", "harness123")


def test_successful_login_resets_failure_counter(store):
    auth_mod.record_login_failure("admin")
    assert auth_mod.verify_password(store, "admin", "harness123")
    assert auth_mod.login_locked("admin") == 0


def test_token_roundtrip(store):
    token = auth_mod.make_token(store, "admin")
    assert auth_mod.parse_token(store, token) == "admin"


def test_token_rejects_tamper_and_garbage(store):
    token = auth_mod.make_token(store, "admin")
    assert auth_mod.parse_token(store, token[:-2] + "xx") is None
    assert auth_mod.parse_token(store, "not-a-token") is None
    assert auth_mod.parse_token(store, "") is None


def test_token_expires(store, monkeypatch):
    monkeypatch.setattr(auth_mod, "SESSION_TTL", -1)  # 已过期
    token = auth_mod.make_token(store, "admin")
    assert auth_mod.parse_token(store, token) is None


def test_change_password(store):
    assert auth_mod.change_password(store, "admin", "wrong-old", "new-pass-1") is False
    assert auth_mod.change_password(store, "admin", "harness123", "new-pass-1")
    assert auth_mod.verify_password(store, "admin", "new-pass-1")
    assert store["default_credentials"] is False  # 登录页不再提示初始口令


def test_change_password_rejects_short(store):
    with pytest.raises(ValueError):
        auth_mod.change_password(store, "admin", "harness123", "12345")
