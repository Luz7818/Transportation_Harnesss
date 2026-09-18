"""导出 OpenAPI 规范:python scripts/export_openapi.py [--out docs/openapi.json]

离线导出 FastAPI 自动生成的 OpenAPI 3.1 规范,产物可直接导入
Postman / Apifox / Swagger UI,或用于生成各语言客户端。
不启动服务器、不读任何业务数据。
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 确保导出的 schema 包含 X-API-Token 安全方案(app 模块导入时读取环境变量)
os.environ.setdefault("AUTH_MODE", "login")
os.environ.setdefault("AUTH_TOKEN", "export-placeholder")


def main() -> None:
    parser = argparse.ArgumentParser(description="导出 OpenAPI 规范到 JSON 文件")
    parser.add_argument("--out", default="docs/openapi.json", help="输出路径(默认 docs/openapi.json)")
    args = parser.parse_args()

    from webapp.app import app  # 环境变量就位后再导入

    schema = app.openapi()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    n_paths = len(schema.get("paths", {}))
    tags = sorted({t for ops in schema.get("paths", {}).values()
                   for op in ops.values() for t in op.get("tags", [])})
    print(f"OpenAPI {schema.get('openapi')} -> {out.relative_to(Path.cwd()) if out.is_relative_to(Path.cwd()) else out}")
    print(f"路径数:{n_paths};分组:{', '.join(tags)}")
    print("导入指引:Postman/Apifox -> Import -> 该 JSON 文件")


if __name__ == "__main__":
    main()
