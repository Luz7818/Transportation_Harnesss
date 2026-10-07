"""组装私有化部署交付包:dist/TransportationHarness-deploy-<版本>.zip。

  python packaging/build_deploy.py

包内容(在线构建形态,目标机需 Docker + 基础镜像网络):
  源码树 + Dockerfile/docker-compose.yml/.dockerignore + .env.example
  + docs/DEPLOY.md + scripts/(probe_live/backup 零依赖) + 部署说明.md
本机装有 Docker 时额外执行 docker build → docker save,zip 内含镜像 tar,
目标机 `docker load` 后可免网络部署;无 Docker 自动跳过并提示。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE_NAME = "deploy"

# 源码树打包清单:docker build 的 context 所需 + 数据资产 + 目标机要用的脚本/文档
_COPY_FILES = (
    "Dockerfile", "docker-compose.yml", ".dockerignore",
    "pyproject.toml", "README.md", ".env.example",
)
_COPY_TREES = ("harness", "llm", "pipeline", "webapp", "cases", "evalsets", "reports", "scripts")
# 交付物里绝不允许出现的本机凭据/运行态文件(双保险:忽略规则 + 装包前扫描)
_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "auth.json")
_FORBIDDEN = {".env", "auth.json"}


def _run(cmd: list[str]) -> None:
    print(f"[deploy] {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    image = f"transportation-harness:{version}"
    stage = ROOT / "dist" / STAGE_NAME
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    print(f"[deploy] 版本 {version} → {stage}")

    for name in _COPY_FILES:
        shutil.copy2(ROOT / name, stage / name)
    for name in _COPY_TREES:
        shutil.copytree(ROOT / name, stage / name, ignore=_IGNORE)
    (stage / "docs").mkdir()
    shutil.copy2(ROOT / "docs" / "DEPLOY.md", stage / "docs" / "DEPLOY.md")
    shutil.copy2(ROOT / "packaging" / "部署说明.md", stage / "部署说明.md")

    leaked = [p.relative_to(stage) for p in stage.rglob("*")
              if p.name in _FORBIDDEN or p.name.endswith(".log")]
    if leaked:
        for p in leaked:
            p.unlink()
        sys.exit(f"[deploy] 终止:打包清单混入了凭据/运行态文件 {leaked}(已清除,请核查 _COPY_TREES)")

    with_image = shutil.which("docker") is not None
    if with_image:
        _run(["docker", "build", "-t", image, str(ROOT)])
        tar = stage / f"transportation-harness-{version}.tar"
        _run(["docker", "save", "-o", str(tar), image])
    else:
        print("[deploy] 本机未装 Docker:跳过镜像构建,产出在线构建包"
              "(目标机 docker compose up -d --build;离线 tar 需在有 Docker 的机器重跑本脚本)")

    zip_base = ROOT / "dist" / f"TransportationHarness-deploy-{version}"
    # 注意不能 Path.with_suffix(".zip"):版本号 "2.1.0" 的 ".0" 会被当成后缀替换掉
    zip_path = zip_base.with_name(zip_base.name + ".zip")
    shutil.make_archive(str(zip_base), "zip", root_dir=stage)
    with zipfile.ZipFile(zip_path) as zf:
        print(f"[deploy] 完成:{zip_path.name} "
              f"({zip_path.stat().st_size / 1e6:.1f} MB, {len(zf.namelist())} 个文件,"
              f"镜像 {'含' if with_image else '不含'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
