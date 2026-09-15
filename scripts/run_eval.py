"""单版本评测 CLI:python scripts/run_eval.py --version v0 [--evalset evalset_v1] [--md]

跑通"评测集 → 重放 → 判分 → 报告"的最小闭环;--md 额外输出 Markdown 报告。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from harness import report, storage
from harness.runner import ReplayRunner
from pipeline.versions import CHANGELOG, PIPELINES


def main() -> None:
    parser = argparse.ArgumentParser(description="运行单版本评测")
    parser.add_argument("--version", required=True, choices=sorted(PIPELINES))
    parser.add_argument("--evalset", default="evalset_v1")
    parser.add_argument("--md", action="store_true", help="同时输出 Markdown 报告")
    args = parser.parse_args()

    evalset = storage.load_evalset(args.evalset)
    cases = storage.load_evalset_cases(args.evalset)
    runner = ReplayRunner()
    er = runner.run_evalset(args.version, PIPELINES[args.version], evalset, cases)

    print(f"\n[{args.version}] 评测集 {er.evalset_id}:{er.passed_count}/{er.total}"
          f" 通过({_pct(er.accuracy)}),耗时 {er.duration_ms} ms")
    print(f"{'case':10} {'标签':8} {'结果':6} {'得分':6} 说明")
    for r in er.results:
        flag = "PASS" if r.passed else "FAIL"
        failed = "; ".join(c.detail for c in r.checks if not c.passed) or ("崩溃: " + r.error if r.error else "")
        print(f"{r.case_id:10} {r.label:8} {flag:6} {r.score:<6} {failed}")

    payload = report.build_payload(er, CHANGELOG)
    path = storage.save_report(args.version, payload)
    print(f"\nJSON 报告 -> {path.relative_to(storage.PROJECT_ROOT)}")

    if args.md:
        md_path = storage.REPORTS_DIR / f"report_{args.version}_{er.timestamp.replace(':', '').replace('-', '')}.md"
        report.render_markdown({args.version: er}, CHANGELOG, evalset["description"], md_path)
        print(f"Markdown 报告 -> {md_path.relative_to(storage.PROJECT_ROOT)}")


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


if __name__ == "__main__":
    main()
