"""端到端校验:重放三个版本的评测,用"不变量"而非硬编码得分断言,评测集增长后依然可用。

校验的不变量(与 reports/report_evolution_*.md 的结果一致):
  [种子不变量] 仅对 evalset_v1 的 13 条种子 case(rc-0001~0013)生效:
    - v0 仅 rc-0013 通过(回归保护用例);v1 恰好剩 rc-0009/rc-0010 未通过;v2 全部通过;
  [单调性]      任意评测集上:通过集 v0 ⊆ v1 ⊆ v2(改动只许修好、不许改坏);
  [数值抽查]    v2 在 base/missing_volume/empty 数据集上的关键行为与数值;
  [资产归档]    reports/ 已有各版本 JSON 报告与自进化 Markdown 报告。
  新沉淀、尚未被 v2 覆盖的 case 不判失败,输出 WARN 并提示作为下一轮迭代 backlog。

运行:
  python scripts/verify.py                       # 校验 evalset_v1(默认)
  python scripts/verify.py --evalset evalset_scenario_rain
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from harness import storage
from harness.runner import ReplayRunner
from pipeline.versions import PIPELINES

SEED_CASE_IDS = {f"rc-{i:04d}" for i in range(1, 14)}   # 首批评测集的 13 条种子 case
SEED_V0_PASSED = {"rc-0013"}                             # 唯一在基线上就该通过的回归保护用例
SEED_V1_FAILED = {"rc-0009", "rc-0010"}                  # v1(算法修正)后仍需 v2 边界优化才能通过
EXPECT_V2_GLOBAL_INDEX = 0.7944                          # v2 流量加权全局拥堵指数(base 数据集)
TOL = 0.005


def main() -> None:
    parser = argparse.ArgumentParser(description="端到端不变量校验")
    parser.add_argument("--evalset", default="evalset_v1", help="评测集名称(默认 evalset_v1)")
    args = parser.parse_args()

    evalset = storage.load_evalset(args.evalset)
    cases = storage.load_evalset_cases(args.evalset)
    runner = ReplayRunner()

    failures: list[str] = []
    warnings: list[str] = []

    def check(name: str, cond: bool, detail: str = "", warn_only: bool = False) -> None:
        mark = "PASS" if cond else ("WARN" if warn_only else "FAIL")
        print(f"  {mark}  {name}" + (f"({detail})" if detail else ""))
        if not cond:
            (warnings if warn_only else failures).append(name)

    er = {v: runner.run_evalset(v, PIPELINES[v], evalset, cases)
          for v in ("v0", "v1", "v2")}
    passed_ids = {v: {r.case_id for r in res.results if r.passed} for v, res in er.items()}

    print(f"[1] 得分轨迹(evalset={args.evalset},共 {len(cases)} 条 case)")
    for v in ("v0", "v1", "v2"):
        check(f"{v} 得分 {er[v].passed_count}/{er[v].total}", True)  # 展示行,恒真
    check("得分单调不减 v0 ≤ v1 ≤ v2",
          er["v0"].accuracy <= er["v1"].accuracy <= er["v2"].accuracy,
          f"{er['v0'].accuracy} → {er['v1'].accuracy} → {er['v2'].accuracy}")

    print("[2] 单调性(通过集只许扩大,不许缩小 = 无回归)")
    check("v1 通过集 ⊇ v0 通过集", passed_ids["v0"] <= passed_ids["v1"],
          f"丢失 {sorted(passed_ids['v0'] - passed_ids['v1'])}" if passed_ids["v0"] - passed_ids["v1"] else "")
    check("v2 通过集 ⊇ v1 通过集", passed_ids["v1"] <= passed_ids["v2"],
          f"丢失 {sorted(passed_ids['v1'] - passed_ids['v2'])}" if passed_ids["v1"] - passed_ids["v2"] else "")

    if args.evalset == "evalset_v1":
        print("[3] 种子不变量(13 条种子 case 的行为冻结)")
        seed_all = {c.case_id for c in cases} >= SEED_CASE_IDS
        check("评测集包含全部 13 条种子 case", seed_all)
        if seed_all:
            check("v0 通过集 = {rc-0013}", passed_ids["v0"] & SEED_CASE_IDS == SEED_V0_PASSED,
                  f"实际 {sorted(passed_ids['v0'] & SEED_CASE_IDS)}")
            check("v1 剩余失败 = {rc-0009, rc-0010}",
                  SEED_CASE_IDS - passed_ids["v1"] == SEED_V1_FAILED,
                  f"实际 {sorted(SEED_CASE_IDS - passed_ids['v1'])}")
            check("v2 通过全部种子 case", passed_ids["v2"] >= SEED_CASE_IDS)
    else:
        print("[3] 种子不变量(非 evalset_v1,跳过)")

    open_failures = sorted({r.case_id for r in er["v2"].results if not r.passed} - SEED_CASE_IDS)
    print("[4] 新沉淀 case(v2 尚未覆盖的不判失败,属于下一轮迭代 backlog)")
    if open_failures:
        print(f"  WARN  v2 未通过新沉淀 case:{open_failures}(沉淀新 case 后应迭代 v3 修复)")
        warnings.extend(open_failures)
    else:
        print("  PASS  无待修复的新沉淀 case")

    print("[5] v2 数值与健壮性抽查(与评测集无关)")
    out = PIPELINES["v2"](storage.load_dataset("base"))
    check("全局拥堵指数(流量加权)≈ 0.7944",
          abs(out["global_congestion_index"] - EXPECT_V2_GLOBAL_INDEX) <= TOL,
          f"实际 {out['global_congestion_index']}")
    check("拥堵路段按饱和度降序", out["congested_segments"] == ["S-10", "S-05", "S-02", "S-03", "S-11"],
          f"实际 {out['congested_segments']}")
    out_missing = PIPELINES["v2"](storage.load_dataset("missing_volume"))
    s9 = next(r for r in out_missing["segments"] if r["segment_id"] == "S-09")
    check("缺失流量路段标记为「数据缺失」", s9["classification"] == "数据缺失")
    out_empty = PIPELINES["v2"](storage.load_dataset("empty"))
    check("空数据集优雅降级(无拥堵路段,指数为空)",
          out_empty["congested_segments"] == [] and out_empty["global_congestion_index"] is None)

    print("[6] 报告归档")
    reports = storage.list_reports()
    versions_present = {r["version"] for r in reports}
    check("reports/ 已有 v0/v1/v2 的 JSON 报告", {"v0", "v1", "v2"} <= versions_present,
          f"现有版本 {sorted(versions_present)}")
    md_files = list(storage.REPORTS_DIR.glob("report_evolution_*.md"))
    check("存在自进化 Markdown 报告", bool(md_files))

    if failures:
        print(f"\n校验未通过:{failures}")
        sys.exit(1)
    print("\nVERIFY PASS:最小闭环与两轮自进化结果全部符合预期。"
          + (f"(警告 {len(warnings)} 条:{warnings})" if warnings else ""))


if __name__ == "__main__":
    main()
