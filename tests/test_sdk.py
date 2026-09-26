"""SDK 集成测试:线程内起真实 uvicorn(随机空闲端口),SDK 走网络直连。

不与开发端口冲突、不依赖外网,却覆盖"SDK → TCP → 中间件鉴权 → 端点 → 判分"
的完整真实链路;storage 夹具隔离,不污染真实评测资产。
"""

from __future__ import annotations

import socket
import threading
import time
import urllib.request

import pytest
from harness_client import (
    CompareResult,
    EvalResult,
    HarnessAPIError,
    HarnessAuthError,
    TransportationHarnessClient,
)
from harness_client import cli as sdk_cli


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def server_url():
    """模块级起一个真实 uvicorn 实例(随机端口,守护线程),供全部 SDK 用例共享。"""
    import uvicorn
    from webapp.app import app

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port,
                            log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(100):  # 轮询健康检查直至就绪
        try:
            urllib.request.urlopen(f"{base_url}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("测试服务器未能启动")
    yield base_url
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def api(server_url, hermetic_storage, api_token):
    """令牌通道的 SDK 客户端(机器客户端形态)。"""
    with TransportationHarnessClient(base_url=server_url, token=api_token) as client:
        yield client


@pytest.fixture
def login_api(server_url, hermetic_storage, admin_credentials):
    """登录通道的 SDK 客户端(交互脚本形态):用户名/密码自动换取会话 Cookie。"""
    username, password = admin_credentials
    with TransportationHarnessClient(
        base_url=server_url, username=username, password=password,
    ) as client:
        yield client


class TestAuthChannels:
    def test_token_channel_reaches_protected_endpoints(self, api):
        cases = api.list_cases()
        assert isinstance(cases, list) and len(cases) >= 13  # 库内全量(含场景快照)

    def test_missing_token_raises_auth_error(self, server_url, hermetic_storage):
        with TransportationHarnessClient(base_url=server_url) as client, \
                pytest.raises(HarnessAuthError):
            client.list_cases()

    def test_login_channel_me_and_cases(self, login_api, admin_credentials):
        me = login_api.me()
        assert me["username"] == admin_credentials[0]
        assert len(login_api.list_cases()) >= 13


class TestCoreFlows:
    def test_health(self, api):
        health = api.health()
        assert health["status"] == "ok"
        assert health["app_version"] == "1.5.0"
        assert health["versions"] == ["v0", "v1", "v2"]

    def test_analyze_pipeline_output(self, api):
        out = api.analyze(version="v2", dataset_name="base")
        assert abs(out["global_congestion_index"] - 0.7944) < 0.005
        assert out["congested_segments"][0] == "S-10"  # 按饱和度降序

    def test_run_eval_returns_typed_result(self, api):
        result = api.run_eval(version="v2")
        assert isinstance(result, EvalResult)
        assert (result.passed_count, result.total) == (13, 13)
        assert result.accuracy == 1.0
        assert result.report_id  # 服务端归档的报告 ID,可直接喂给 compare/get_report
        assert result.failed_cases() == []
        assert result.results[0].checks  # 逐 case 判分明细已建模

    def test_run_eval_unknown_version_raises_404(self, api):
        with pytest.raises(HarnessAPIError) as excinfo:
            api.run_eval(version="v9")
        assert excinfo.value.status == 404

    def test_evolve_summary(self, api):
        summary = api.evolve(timeout=60.0)
        assert summary["best"]["version"] == "v2"
        assert summary["iterations_used"] == 2
        assert summary["stop_reason"]
        assert summary["md_report"]

    def test_case_crud_roundtrip(self, api):
        created = api.create_case(
            title="SDK 回归用例", label="回归保护", dataset_name="base",
            segment="S-07", expected_level="畅通",
        )
        case_id = created["case"]["case_id"]
        assert created["added_to_evalset"] is True
        assert api.get_case(case_id)["title"] == "SDK 回归用例"
        assert api.delete_case(case_id)["deleted"] == case_id
        with pytest.raises(HarnessAPIError) as excinfo:
            api.get_case(case_id)
        assert excinfo.value.status == 404

    def test_compare_reports(self, api):
        v0 = api.run_eval(version="v0")
        v2 = api.run_eval(version="v2")
        comparison = api.compare(v0.report_id, v2.report_id)
        assert isinstance(comparison, CompareResult)
        assert len(comparison.newly_passed) == 12
        assert comparison.regressed == []  # 无回归才允许合入
        assert len(comparison.rows) == 13


class TestCli:
    def test_health_smoke(self, server_url, hermetic_storage, api_token, capsys):
        assert sdk_cli.main(["health", "--base-url", server_url, "--token", api_token]) == 0
        assert '"status": "ok"' in capsys.readouterr().out

    def test_eval_smoke(self, server_url, hermetic_storage, api_token, capsys):
        assert sdk_cli.main(["eval", "--version", "v2",
                             "--base-url", server_url, "--token", api_token]) == 0
        assert "13/13 通过" in capsys.readouterr().out

    def test_error_exit_code(self, server_url, hermetic_storage, capsys):
        assert sdk_cli.main(["versions", "--base-url", server_url]) == 1  # 无令牌 → 1
        assert "错误" in capsys.readouterr().err
