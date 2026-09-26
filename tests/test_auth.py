"""webapp.auth:口令哈希、旧哈希透明升级、登录限流、会话令牌。

夹具口令来自 tests/conftest 的 TEST_ADMIN_PASSWORD(仅测试,不对应任何真实部署)。
"""

import pytest
from webapp import auth as auth_mod


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_mod, "AUTH_FILE", tmp_path / "auth.json")
    return auth_mod.load_store()


def test_pbkdf2_hash_roundtrip(store, admin_credentials):
    _user, password = admin_credentials
    user = store["users"][0]
    assert user["password_hash"].startswith("pbkdf2_sha256$")
    assert password not in user["password_hash"]      # 哈希里不含明文
    assert auth_mod._verify_hash(user, password)
    assert not auth_mod._verify_hash(user, "wrong")


def test_password_never_stored_plaintext(store, admin_credentials):
    blob = auth_mod.AUTH_FILE.read_text(encoding="utf-8")
    assert admin_credentials[1] not in blob


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


def test_login_lockout_after_repeated_failures(store, admin_credentials):
    for _ in range(auth_mod.LOCKOUT_THRESHOLD):
        assert not auth_mod.verify_password(store, "admin", "bad-pass")
    assert auth_mod.login_locked("admin") > 0
    # 锁定期内即使口令正确也拒绝
    assert not auth_mod.verify_password(store, "admin", admin_credentials[1])


def test_successful_login_resets_failure_counter(store, admin_credentials):
    auth_mod.record_login_failure("admin")
    assert auth_mod.verify_password(store, "admin", admin_credentials[1])
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


def test_change_password(store, admin_credentials):
    old = admin_credentials[1]
    assert auth_mod.change_password(store, "admin", "wrong-old", "new-pass-1") is False
    assert auth_mod.change_password(store, "admin", old, "new-pass-1")
    assert auth_mod.verify_password(store, "admin", "new-pass-1")
    assert store["default_credentials"] is False  # 登录页不再提示初始口令


def test_change_password_rejects_short(store, admin_credentials):
    with pytest.raises(ValueError):
        auth_mod.change_password(store, "admin", admin_credentials[1], "12345")


def test_initial_store_has_no_public_default_password(tmp_path, monkeypatch, capsys):
    """auth.json 不存在且未给 ADMIN_PASSWORD → 随机强口令 + 只打印一次 + 不算默认口令。"""
    monkeypatch.setattr(auth_mod, "AUTH_FILE", tmp_path / "auth.json")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    store = auth_mod.load_store()

    assert store["default_credentials"] is False          # /api/health 不再自报"仍在用默认口令"
    assert auth_mod.DEFAULT_USER == "admin"
    user = store["users"][0]
    assert not auth_mod._verify_hash(user, "harness123")  # 曾经的公开默认值一律失效
    assert not auth_mod._verify_hash(user, "")            # ADMIN_PASSWORD 置空也不等于空口令
    printed = capsys.readouterr().out
    assert "请" in printed                                 # 提示立即改密
    # 打印出来的那枚口令确实能登录,且库里只存哈希
    token_password = printed.split("随机生成的初始口令为 ", 1)[1].split("(", 1)[0].strip()
    assert len(token_password) == auth_mod.INITIAL_PASSWORD_LENGTH
    assert auth_mod.verify_password(store, "admin", token_password)
    assert token_password not in auth_mod.AUTH_FILE.read_text(encoding="utf-8")


def test_generated_initial_password_is_random_and_strong():
    samples = {auth_mod.generate_initial_password() for _ in range(5)}
    assert len(samples) == 5                               # 每次不同
    for pwd in samples:
        assert len(pwd) == auth_mod.INITIAL_PASSWORD_LENGTH
        assert not set(pwd) & set("0O1lI")                 # 去掉易混字符,便于人工录入


def test_existing_store_untouched_by_default_password_change(tmp_path, monkeypatch):
    """现有部署(auth.json 已存在)行为不变:不重新生成口令、不改写文件。"""
    auth_file = tmp_path / "auth.json"
    monkeypatch.setattr(auth_mod, "AUTH_FILE", auth_file)
    first = auth_mod.load_store()
    before = auth_file.read_bytes()

    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    assert auth_mod.load_store() == first          # 已存在的账号库原样读回
    assert auth_file.read_bytes() == before        # 没有被覆写
