"""make_server:exe GUI 启动器用的 Server 工厂——参数校验必须先于返回。

GUI 本身(pywebview 窗口)无法在 CI 自动化,由构建后的人工冒烟覆盖(见 packaging/README.md);
这里守住的是 GUI 与无头模式共用的部署参数门禁。

注意:webapp.app 必须在测试函数内导入 —— 模块级导入会在 collection 阶段(早于 conftest
夹具接管 auth_mod.AUTH_FILE)执行 _AUTH_STORE = load_store(),读到仓库真实 webapp/auth.json,
污染后续所有登录类用例(与 test_sdk.py server_url 夹具的补丁-再导入约定同理)。
"""

from __future__ import annotations

import pytest


def test_make_server_rejects_short_token(monkeypatch):
    """AUTH_TOKEN 不满 16 字符时拒绝启动(GUI 与无头同一道门)。"""
    import webapp.app as app_mod

    monkeypatch.setattr(app_mod, "AUTH_TOKEN", "short-token")
    with pytest.raises(SystemExit):
        app_mod.make_server()


def test_make_server_returns_configured_handle():
    """正常配置下返回绑定 HOST/PORT 的 Server 句柄(关窗停机靠它)。"""
    import webapp.app as app_mod

    server = app_mod.make_server()
    assert (server.config.host, server.config.port) == (app_mod.HOST, app_mod.PORT)
