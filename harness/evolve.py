"""自进化主流程:

    基线测量 → 逐版本迭代验证 → 「提升且无回归」检查 → 收益递减即停 → 归档报告

迭代版本不再硬编码:凡在 pipeline.versions.PIPELINES 中登记、且排在基线之后的版本,
都会按注册顺序被逐轮验证。单轮运行的迭代次数上限由 ``EVOLVE_MAX_ROUNDS`` 控制
(默认 2,沿用「每轮聚焦、收益递减」的纪律);因上限未验证的版本会以
``pending_versions`` 显式返回并用 ``--baseline <版本>`` 继续验证,绝不静默丢弃。

CLI 运行:python -m harness.evolve [--evalset 名称] [--baseline v2]
API 调用:POST /api/evolve/run {"evalset": "...", "baseline": "v2"}
"""

from __future__ import annotations

import os
import sys
from collections import OrderedDict
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pipeline.versions import CHANGELOG, PIPELINES

from harness import report, storage
from harness.models import EvalResult
from harness.runner import ReplayRunner

BASELINE_VERSION = "v0"          # 默认基线:完整回放 v0 → 全部已登记版本的历史轨迹
MIN_IMPROVEMENT = 0.05           # 收益 <5% 视为收益递减,提前停止


def _max_rounds() -> int:
    try:
        value = int(os.getenv("EVOLVE_MAX_ROUNDS", "2"))
    except ValueError:
        return 2
    return max(1, value)


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _failures_by_label(er: EvalResult) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in er.results:
        if not r.passed:
            out.setdefault(r.label, []).append(f"{r.case_id} {r.title}")
    return out


def _rel_to_project(path) -> str:
    """报告相对路径(供看板跳转);数据目录不在项目根下(挂载卷等)时退化为绝对路径。"""
    try:
        return str(path.relative_to(storage.PROJECT_ROOT))
    except ValueError:
        return str(path)


def _resolve_iterations(baseline_version: str) -> tuple[list[str], list[str]]:
    """按注册顺序取基线之后的版本,依单轮上限切成(本轮验证, 待下轮验证)。"""
    registered = list(PIPELINES)
    if baseline_version not in registered:
        raise ValueError(
            f"未知基线版本 {baseline_version!r}(可选:{', '.join(registered)})")
    pending_all = registered[registered.index(baseline_version) + 1:]
    cap = _max_rounds()
    return pending_all[:cap], pending_all[cap:]


def run_evolution(evalset_name: str = "evalset_v1",
                  baseline_version: str = BASELINE_VERSION) -> dict:
    """执行完整自进化循环并归档报告,返回结构化摘要(供 CLI 打印与 API 返回)。"""
    iteration_versions, pending_versions = _resolve_iterations(baseline_version)
    evalset = storage.load_evalset(evalset_name)
    cases = storage.load_evalset_cases(evalset_name)
    runner = ReplayRunner()

    results: OrderedDict[str, EvalResult] = OrderedDict()

    # ---- 基线测量 ----
    baseline = runner.run_evalset(baseline_version, PIPELINES[baseline_version], evalset, cases)
    results[baseline_version] = baseline

    # ---- 逐轮迭代(上限内)----
    rounds = []
    prev = baseline
    stop_reason = "已验证全部登记版本" if not iteration_versions else "已达本轮迭代上限"
    for round_idx, version in enumerate(iteration_versions, 1):
        er = runner.run_evalset(version, PIPELINES[version], evalset, cases)
        results[version] = er
        newly, regressed = report.diff(prev, er)
        improvement = er.accuracy - prev.accuracy
        info = {
            "round": round_idx, "version": version, "version_name": CHANGELOG[version]["name"],
            "changes": CHANGELOG[version]["changes"],
            "accuracy": er.accuracy, "passed_count": er.passed_count, "total": er.total,
            "improvement": improvement, "newly_passed": newly, "regressed": regressed,
            "remaining_failures": _failures_by_label(er),
        }
        rounds.append(info)
        prev = er
        if er.total and er.passed_count == er.total:
            stop_reason = "评测集已全部通过"
            break
        if er.total and improvement < MIN_IMPROVEMENT and not newly:
            stop_reason = "收益 <5% 且无新通过案例(收益递减)"
            break
    if pending_versions:  # 因单轮上限未验证的版本,显式提示,绝不静默丢弃
        note = f"({'/'.join(pending_versions)} 待验证)"
        stop_reason = stop_reason + note if "待验证" not in stop_reason else stop_reason

    # ---- 归档报告 ----
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = storage.REPORTS_DIR / f"report_evolution_{ts}.md"
    report.render_markdown(results, CHANGELOG, evalset.get("description", ""), md_path,
                           max_rounds=_max_rounds())
    for version, er in results.items():
        storage.save_report(version, report.build_payload(er, CHANGELOG))

    # 同分时取更新版本(迭代方向上的最新),而非回退旧版本
    best = max(results.values(), key=lambda er: (er.accuracy, list(results).index(er.version)))
    summary = {
        "evolution_id": f"evolution_{ts}",
        "evalset_id": evalset["evalset_id"],
        "total_cases": len(cases),
        "baseline": {
            "version": baseline.version, "accuracy": baseline.accuracy,
            "passed_count": baseline.passed_count, "total": baseline.total,
            "failures_by_label": _failures_by_label(baseline),
        },
        "rounds": rounds,
        "pending_versions": pending_versions,
        "stop_reason": stop_reason,
        "iterations_used": len(results) - 1,
        "best": {
            "version": best.version, "accuracy": best.accuracy,
            "passed_count": best.passed_count, "total": best.total,
        },
        "md_report": _rel_to_project(md_path),
        "timestamp": ts,
    }
    storage.save_evolution_summary(summary)  # 持久化本次运行,供看板进化时间线回放
    return summary


def _print_summary(summary: dict) -> None:
    print(f"=== 自进化循环启动:评测集 {summary['evalset_id']}({summary['total_cases']} 条 replaycase)===")
    b = summary["baseline"]
    print(f"\n--- 基线测量({b['version']})---")
    print(f"得分 {b['passed_count']}/{b['total']}({_pct(b['accuracy'])});失败案例如下:")
    for label, items in b["failures_by_label"].items():
        print(f"  [{label}]")
        for item in items:
            print(f"    - {item}")
    for r in summary["rounds"]:
        print(f"\n--- 第 {r['round']} 轮迭代({r['version']}:{r['version_name']})---")
        print("【优化内容】")
        for change in r["changes"]:
            print(f"  * {change}")
        print(f"得分 {r['passed_count']}/{r['total']}({_pct(r['accuracy'])}),"
              f"较上一轮 {_pct(r['improvement'])};新通过 {len(r['newly_passed'])} 条,"
              f"回归 {len(r['regressed'])} 条")
        if r["regressed"]:
            print(f"  !! 出现回归({', '.join(r['regressed'])}),按纪律应回退本轮改动")
        if r["remaining_failures"]:
            print("  仍未全部通过,剩余失败案例:")
            for label, items in r["remaining_failures"].items():
                print(f"    [{label}]")
                for item in items:
                    print(f"      - {item}")
    best = summary["best"]
    print("\n=== 总结 ===")
    print(f"停止原因:{summary['stop_reason']}"
          f"(本轮迭代 {summary['iterations_used']} 轮,上限 {_max_rounds()})")
    if summary["pending_versions"]:
        print(f"待验证版本:{', '.join(summary['pending_versions'])}"
              f" —— 用 --baseline <上一版本> 继续验证")
    print(f"最佳版本:{best['version']},得分 {best['passed_count']}/{best['total']}"
          f"({_pct(best['accuracy'])})(基线 {_pct(b['accuracy'])})"
          f" → 提升 {_pct(best['accuracy'] - b['accuracy'])}")
    print(f"Markdown 报告 -> {summary['md_report']}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="自进化循环:基线 → 逐版本迭代验证 → 回归检查")
    parser.add_argument("--evalset", default="evalset_v1", help="评测集名称(默认 evalset_v1)")
    parser.add_argument("--baseline", default=BASELINE_VERSION,
                        help="基线版本(默认 v0;增量验证新版本时用当前最佳,如 --baseline v2)")
    args = parser.parse_args()
    _print_summary(run_evolution(args.evalset, args.baseline))


if __name__ == "__main__":
    main()
