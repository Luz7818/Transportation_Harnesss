"""HARNESS_HOME 路径契约:exe 封装模式唯一的环境变量约定(见 packaging/README.md)。

启动器在导入任何业务模块之前设 HARNESS_HOME,harness/paths.py 在被导入那一刻读取它;
源码模式(默认)下 PROJECT_ROOT 必须仍指向仓库根,四个数据目录与 auth.json 的
源码路径一个都不能变。
"""

from __future__ import annotations

import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_source_mode_root_and_derived_paths_unchanged():
    """不带 HARNESS_HOME:PROJECT_ROOT = 仓库根,各目录与历史行为逐一对齐。"""
    from harness import paths, storage
    from webapp import auth as auth_mod
    from webapp import settings as settings_mod

    root = paths.PROJECT_ROOT
    assert root == REPO_ROOT
    assert root == storage.PROJECT_ROOT
    assert root / "cases" == storage.CASES_DIR
    assert root / "evalsets" == storage.EVALSETS_DIR
    assert root / "pipeline" / "data" == storage.DATA_DIR
    assert root / "reports" == storage.REPORTS_DIR
    # conftest 的 autouse 夹具会把 settings.ENV_FILE/BACKUP_DIR 重定向到临时目录,
    # 这里重载模块本身,验证的是「settings 自己的推导」而非夹具改过的值
    importlib.reload(settings_mod)
    assert root / ".env" == settings_mod.ENV_FILE
    assert root / "backups" == settings_mod.BACKUP_DIR
    assert root / "webapp" / "auth.json" == auth_mod.AUTH_FILE


def test_harness_home_env_redirects_root(monkeypatch, tmp_path):
    """设 HARNESS_HOME 后重载 paths:PROJECT_ROOT 指向该目录(启动器的打包模式用法)。"""
    from harness import paths

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path))
    try:
        reloaded = importlib.reload(paths)
        assert tmp_path.resolve() == reloaded.PROJECT_ROOT
    finally:
        monkeypatch.delenv("HARNESS_HOME")
        importlib.reload(paths)   # 还原模块级单例,不让本用例影响其他用例
    assert paths.PROJECT_ROOT == REPO_ROOT
