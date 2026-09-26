"""pytest 共享夹具:把 storage 的数据目录隔离到临时目录,测试不污染真实评测资产。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"

# 仅测试:以下凭据只存在于 pytest 进程内(临时 auth.json),不对应任何真实部署。
# 刻意用强赋值而非 setdefault —— 本机/CI 上残留的同名环境变量不该能改掉测试账号;
# 需要换值时设 TEST_ADMIN_USER / TEST_ADMIN_PASSWORD / TEST_API_TOKEN。
TEST_ADMIN_USER = os.getenv("TEST_ADMIN_USER", "admin")
TEST_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "test-only-harness-pw")
TEST_API_TOKEN = os.getenv("TEST_API_TOKEN", "test-only-api-token")
# webapp.app 在 import 时读取环境变量,必须在其被导入前固定测试取值
os.environ["AUTH_MODE"] = "login"
os.environ["AUTH_TOKEN"] = TEST_API_TOKEN
os.environ["ADMIN_USER"] = TEST_ADMIN_USER
os.environ["ADMIN_PASSWORD"] = TEST_ADMIN_PASSWORD


def seed_asset_dirs(tmp_path: Path) -> dict[str, Path]:
    """把冻结的种子快照(tests/fixtures)拷贝到临时目录;reports 留空待生成。

    用固定夹具而非真实 cases/,测试结果不随线上演示数据增长而漂移。
    """
    mapping = {}
    for name in ("cases", "evalsets"):
        target = tmp_path / name
        shutil.copytree(FIXTURE_ROOT / name, target)
        mapping[name] = target
    mapping["reports"] = tmp_path / "reports"
    mapping["reports"].mkdir()
    return mapping


@pytest.fixture(autouse=True)
def _reset_login_guard():
    """登录限流是进程内共享状态,逐用例清零,避免用例间相互锁定。"""
    from webapp import auth as auth_mod

    auth_mod._login_guard.clear()


@pytest.fixture(autouse=True)
def _hermetic_dotenv(tmp_path, monkeypatch):
    """.env 的读写与备份一律重定向到临时目录,用例结束后还原被改过的环境变量。

    autouse:/api/settings 会真写文件、真改 os.environ,不加这层保护
    任何一次接口测试都可能改到仓库里现存的 .env(里面是本机真实 LLM 配置)。
    """
    from webapp import settings as settings_mod

    monkeypatch.setattr(settings_mod, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(settings_mod, "BACKUP_DIR", tmp_path / "backups")
    saved = {key: os.environ.get(key) for key in settings_mod.SPECS_BY_KEY}
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def hermetic_storage(tmp_path, monkeypatch):
    """隔离 cases/evalsets/reports 三个目录;pipeline/data 保持真实(只读)。"""
    from harness import storage

    dirs = seed_asset_dirs(tmp_path)
    monkeypatch.setattr(storage, "CASES_DIR", dirs["cases"])
    monkeypatch.setattr(storage, "EVALSETS_DIR", dirs["evalsets"])
    monkeypatch.setattr(storage, "REPORTS_DIR", dirs["reports"])
    return dirs


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    """构造 API 测试客户端的工厂:`make_client(client_host=...)` 决定 TCP 对端地址。

    app 在 import 时会加载仓库根目录 .env(可能含本机真实 LLM 配置),
    这里统一清除并重置运行时,保证 API 级测试始终走离线确定性 Mock。
    """
    import webapp.auth as auth_mod

    monkeypatch.setattr(auth_mod, "AUTH_FILE", tmp_path / "auth.json")

    import webapp.app as app_mod
    for key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_EXTRA_BODY"):
        monkeypatch.delenv(key, raising=False)
    from llm import runtime as llm_runtime
    llm_runtime.reset_runtime()

    from fastapi.testclient import TestClient

    def _make(client_host: str = "testclient") -> TestClient:
        return TestClient(app_mod.app, client=(client_host, 50000))

    return _make


@pytest.fixture
def client(make_client):
    """Web API 测试客户端;默认对端地址不是回环,等价于"从另一台机器访问"。"""
    with make_client() as tc:
        yield tc


@pytest.fixture
def loopback_client(make_client):
    """对端地址为 127.0.0.1 的客户端:用于 /api/settings 的本机直连分支。"""
    with make_client("127.0.0.1") as tc:
        yield tc


@pytest.fixture
def authed_client(client):
    """已登录(会话 Cookie)的客户端。"""
    resp = client.post("/api/auth/login",
                       json={"username": TEST_ADMIN_USER, "password": TEST_ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return client


@pytest.fixture
def bearer_client(make_client):
    """只带 `Authorization: Bearer <会话令牌>`、不带任何 Cookie 的客户端(小程序形态)。"""
    with make_client() as tc:
        resp = tc.post("/api/auth/login",
                       json={"username": TEST_ADMIN_USER, "password": TEST_ADMIN_PASSWORD})
        assert resp.status_code == 200, resp.text
        token = resp.json()["token"]
        tc.cookies.clear()
        tc.headers["Authorization"] = f"Bearer {token}"
        yield tc


@pytest.fixture
def admin_credentials() -> tuple[str, str]:
    """夹具账号的用户名/口令(仅测试)。"""
    return TEST_ADMIN_USER, TEST_ADMIN_PASSWORD


@pytest.fixture
def api_token() -> str:
    """机器客户端令牌(仅测试),与服务端 AUTH_TOKEN 的取值一致。"""
    return TEST_API_TOKEN
