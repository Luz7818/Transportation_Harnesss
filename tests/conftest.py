"""pytest 共享夹具:把 storage 的数据目录隔离到临时目录,测试不污染真实评测资产。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"

# webapp.app 在 import 时读取环境变量,必须在其被导入前固定测试取值
os.environ.setdefault("AUTH_MODE", "login")
os.environ.setdefault("AUTH_TOKEN", "test-token-123")


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
    yield


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
def client(tmp_path, monkeypatch):
    """Web API 测试客户端:auth.json 指向临时文件,避免动到真实凭据。"""
    import webapp.auth as auth_mod

    monkeypatch.setattr(auth_mod, "AUTH_FILE", tmp_path / "auth.json")

    import webapp.app as app_mod
    from fastapi.testclient import TestClient

    with TestClient(app_mod.app) as tc:
        yield tc


@pytest.fixture
def authed_client(client):
    """已登录(会话 Cookie)的客户端。"""
    resp = client.post("/api/auth/login",
                       json={"username": "admin", "password": "harness123"})
    assert resp.status_code == 200, resp.text
    return client
