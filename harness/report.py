"""报告生成:把多轮 EvalResult 汇总成 code-optimization 模板的 Markdown 报告 + 看板用 JSON。

模板结构:基线性能 → 【优化版本】v1 → 【优化版本】v2 → 最终总结(最多 2 轮迭代)。
这里的"性能"是评测得分(通过率),同时记录单轮评测耗时作为次要指标。
"""

from __future__ import annotations

from pathlib import Path

from harness.models import EvalResult


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _label_table(er: EvalResult) -> str:
    lines = ["| 失败标签 | 通过/总数 | 通过率 |", "| --- | --- | --- |"]
    for label, st in sorted(er.label_stats.items(), key=lambda kv: (-kv[1]["total"], kv[0])):
        lines.append(f"| {label} | {st['passed']}/{st['total']} | {_pct(st['passed'] / st['total'])} |")
    return "\n".join(lines)


def diff(prev: EvalResult, cur: EvalResult) -> tuple[list[str], list[str]]:
    """对比两轮评测:(新通过的 case, 回归的 case)。

    两轮之间评测集可能扩充过(新 badcase 沉淀),只对两轮共有的 case 判定
    新通过/回归,单侧独有的 case 不计入,避免 KeyError 与误报。
    """
    prev_map = {r.case_id: r for r in prev.results}
    newly = [r.case_id for r in cur.results
             if r.passed and prev_map.get(r.case_id) is not None and not prev_map[r.case_id].passed]
    regressed = [r.case_id for r in cur.results
                 if not r.passed and prev_map.get(r.case_id) is not None and prev_map[r.case_id].passed]
    return newly, regressed


def build_payload(er: EvalResult, changelog: dict) -> dict:
    """单个版本的评测结果 → JSON(供 webapp 看板/对比接口使用)。"""
    meta = changelog.get(er.version, {})
    payload = er.to_dict()
    payload["version_name"] = meta.get("name", "")
    payload["changes"] = meta.get("changes", [])
    return payload


def render_markdown(results: dict[str, EvalResult], changelog: dict, evalset_desc: str, out_path,
                    max_rounds: int = 2) -> Path:
    versions = list(results)
    baseline = results[versions[0]]

    lines: list[str] = []
    lines.append("# 交通分析自进化 Harness 评测报告")
    lines.append("")
    lines.append(f"- 评测集:{baseline.evalset_id}({baseline.total} 条 replaycase,{evalset_desc})")
    lines.append(f"- 生成时间:{baseline.timestamp}")
    strategy = " → ".join(f"{v}({changelog.get(v, {}).get('name', '')})" for v in versions[1:])
    lines.append(f"- 迭代策略:基线 {versions[0]} → {strategy or '无'},"
                 f"本轮迭代上限 {max_rounds}(收益 <5% 或全部通过即提前停止)")
    lines.append("")
    lines.append(f"## 基线性能({versions[0]})")
    lines.append(f"- 评测得分(通过率):{baseline.passed_count}/{baseline.total}({_pct(baseline.accuracy)})")
    lines.append(f"- 单轮评测耗时:{baseline.duration_ms} ms")
    lines.append(f"- 版本说明:{changelog.get(baseline.version, {}).get('name', '')}")
    lines.append("")
    lines.append(_label_table(baseline))
    lines.append("")

    for prev_v, cur_v in zip(versions, versions[1:], strict=False):
        prev, cur = results[prev_v], results[cur_v]
        newly, regressed = diff(prev, cur)
        meta = changelog.get(cur_v, {})
        lines.append("---")
        lines.append("")
        lines.append(f"## 【优化版本】{cur_v}({meta.get('name', '')})")
        lines.append("")
        lines.append("### 【优化内容】")
        for i, change in enumerate(meta.get("changes", []), 1):
            lines.append(f"{i}. {change}")
        lines.append("")
        lines.append("### 【优化后性能】")
        lines.append(f"- 得分:从 {prev.passed_count}/{prev.total}({_pct(prev.accuracy)})"
                     f" 到 {cur.passed_count}/{cur.total}({_pct(cur.accuracy)})"
                     f"(提升 {_pct(cur.accuracy - prev.accuracy)})")
        lines.append(f"- 单轮评测耗时:{cur.duration_ms} ms(基线 {prev.duration_ms} ms)")
        lines.append("")
        lines.append(_label_table(cur))
        lines.append("")
        lines.append("### 【与上一版本对比】")
        lines.append(f"- 新通过 {len(newly)} 条:{', '.join(newly) if newly else '无'}")
        lines.append(f"- 回归 {len(regressed)} 条:{', '.join(regressed) if regressed else '无'}")
        verdict = "PASS(无回归且得分提升)" if (not regressed and cur.accuracy >= prev.accuracy) else "FAIL"
        lines.append(f"- 验证结果:{verdict}")
        lines.append("")

    best = max(results.values(), key=lambda er: (er.accuracy, -versions.index(er.version)))
    worst_er = results[versions[-1]]
    remaining = [f"{r.case_id}({r.title})" for r in worst_er.results if not r.passed]
    first, last = results[versions[0]], results[versions[-1]]
    lines.append("---")
    lines.append("")
    lines.append(f"## 最终总结(本轮迭代 {len(versions) - 1} 轮,上限 {max_rounds})")
    lines.append(f"- 最佳版本:{best.version}({best.passed_count}/{best.total},{_pct(best.accuracy)})")
    lines.append(f"- 总体提升:{_pct(first.accuracy)} → {_pct(last.accuracy)}"
                 f"(绝对提升 {_pct(last.accuracy - first.accuracy)})")
    strategies = [c for v in versions[1:] for c in changelog.get(v, {}).get("changes", [])]
    lines.append("- 优化策略:" + ";".join(strategies))
    last_diff = diff(results[versions[-2]], results[versions[-1]])[1]
    lines.append(f"- 回归检查:{versions[-1]} 相对 {versions[-2]} "
                 f"{'无回归' if not last_diff else '存在回归,需回退'}")
    lines.append("- 剩余失败案例:" + (", ".join(remaining) if remaining else "无"))
    lines.append("")
    lines.append("> 评测集会随线上 badcase 持续扩充,harness 据此自进化;"
                 "单轮提升 <5% 或已通过全部案例时停止迭代(收益递减原则)。")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
