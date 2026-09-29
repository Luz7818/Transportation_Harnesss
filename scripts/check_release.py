"""发布一致性检查(进 CI):版本号四处同步 + OpenAPI 无漂移。

  python scripts/check_release.py

检查两件事,任何一件失败都以退出码 1 结束:
  1. 版本号一致 —— 根 pyproject.toml、sdk/pyproject.toml、sdk/harness_client/__init__.py、
     webapp/app.py 的 FastAPI(version=) 四处取值相同(靠人记同步曾反复失效,改为机器断言;
     __init__.py 直接读源码文件,不经 import —— 环境里可能装着旧版本的包);
  2. OpenAPI 无漂移 —— app 当前 schema 与仓库里 docs/openapi.json 逐键一致
     (端点改动后忘了重导,在这里当场暴露)。
零第三方依赖:只读文件与 import,不起服务、不联网。
"""

from __future__ import annotations

import ast
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _toml_version(path: Path) -> str:
    return tomllib.loads(path.read_text(encoding="utf-8"))["project"]["version"]


def _init_version(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Name) and target.id == "__version__"
                        and isinstance(node.value, ast.Constant)):
                    return str(node.value.value)
    raise ValueError(f"{path} 里找不到 __version__ 赋值")


def check_versions() -> tuple[bool, list[str]]:
    from webapp.app import app

    versions = {
        "pyproject.toml": _toml_version(ROOT / "pyproject.toml"),
        "sdk/pyproject.toml": _toml_version(ROOT / "sdk" / "pyproject.toml"),
        "sdk/harness_client/__init__.py": _init_version(
            ROOT / "sdk" / "harness_client" / "__init__.py"),
        "webapp/app.py (FastAPI version=)": app.version,
    }
    distinct = sorted(set(versions.values()))
    if len(distinct) != 1:
        detail = ", ".join(f"{k}={v}" for k, v in versions.items())
        return False, [f"版本号不一致:{detail}"]
    return True, [f"版本号一致:{distinct[0]} <- {len(versions)} 处"]


def check_openapi_drift() -> tuple[bool, list[str]]:
    from webapp.app import app

    live = json.dumps(app.openapi(), sort_keys=True, ensure_ascii=False)
    disk_path = ROOT / "docs" / "openapi.json"
    disk = json.dumps(json.loads(disk_path.read_text(encoding="utf-8")),
                      sort_keys=True, ensure_ascii=False)
    if live != disk:
        return False, ["OpenAPI 漂移:app 当前 schema 与 docs/openapi.json 不一致,"
                       "请运行 python scripts/export_openapi.py 重导"]
    n_paths = len(json.loads(live)["paths"])
    return True, [f"OpenAPI 无漂移:docs/openapi.json 与 app 当前 schema 逐键一致({n_paths} 路径)"]


def main() -> int:
    failures = 0
    for check in (check_versions, check_openapi_drift):
        ok, messages = check()
        for line in messages:
            print(("[OK]   " if ok else "[FAIL] ") + line)
        failures += 0 if ok else 1
    print("RELEASE CHECK PASS" if failures == 0 else "RELEASE CHECK FAIL")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
