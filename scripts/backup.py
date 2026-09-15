"""评测资产一键备份:cases/ evalsets/ reports/ pipeline/data 打包为带时间戳的 zip。

用法:
    python scripts/backup.py                 # 备份到 backups/
    python scripts/backup.py --out /path/dir # 指定输出目录

定时备份(服务器上 crontab):
    0 3 * * * cd /opt/Transportation_Harnesss && python3 scripts/backup.py
"""

import argparse
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import storage

ASSET_DIRS = ("cases", "evalsets", "reports", Path("pipeline") / "data")


def create_backup(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"harness_backup_{ts}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in ASSET_DIRS:
            src = storage.PROJECT_ROOT / rel
            if not src.exists():
                continue
            for f in sorted(src.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    zf.write(f, Path(rel) / f.relative_to(src))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="评测资产备份(cases/evalsets/reports/数据集)")
    parser.add_argument("--out", default=str(storage.PROJECT_ROOT / "backups"),
                        help="输出目录(默认项目根下 backups/)")
    args = parser.parse_args()
    path = create_backup(Path(args.out))
    size_kb = path.stat().st_size / 1024
    print(f"备份完成:{path}({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
