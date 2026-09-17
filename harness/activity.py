"""跨资产活动流:把 case 沉淀、评测运行、自进化与 LLM 草稿统一成时间倒序的动态 feed。

这是看板「最近动态」的读模型:只聚合已有资产,不引入新的写入路径;
LLM 草稿由调用方注入(harness 不反向依赖 llm 层,保持框架可选装配)。
"""

from __future__ import annotations

import re


def _ts_key(ts: str | None) -> str:
    """不同格式的 timestamps 归一为可排序数字串:ISO 与 YYYYMMDD_HHMMSS 皆可比较。"""
    digits = re.sub(r"\D", "", str(ts or ""))
    return (digits + "00000000000000")[:14]


def _pct(x) -> str:
    try:
        return f"{float(x) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def collect(limit: int = 12, drafts: list[dict] | None = None) -> list[dict]:
    """聚合活动流(时间倒序)。drafts 由调用方注入(llm_store.list_drafts())。"""
    from harness import storage

    events: list[dict] = []

    for c in storage.load_cases():
        events.append({
            "ts": c.created_at, "kind": "case",
            "title": f"沉淀 replaycase {c.case_id}",
            "detail": f"{c.title} · 来源 {c.source}",
            "tag": c.label, "ref": c.case_id,
        })

    for r in storage.list_reports():
        events.append({
            "ts": r.get("timestamp"), "kind": "eval",
            "title": f"评测 {r.get('version')} → {_pct(r.get('accuracy'))}",
            "detail": f"{r.get('passed_count')}/{r.get('total')} 通过 · {r.get('evalset_id')}",
            "tag": r.get("version"), "ref": r.get("report_id"),
        })

    for e in storage.list_evolutions():
        best, base = e.get("best") or {}, e.get("baseline") or {}
        events.append({
            "ts": e.get("timestamp"), "kind": "evolve",
            "title": f"自进化:最佳 {best.get('version')} {_pct(best.get('accuracy'))}",
            "detail": f"基线 {base.get('version')} {_pct(base.get('accuracy'))} · "
                      f"{e.get('evalset_id')}(共 {e.get('total_cases')} 条)",
            "tag": e.get("evalset_id"), "ref": e.get("evolution_id"),
        })

    for d in drafts or []:
        status = d.get("status", "pending")
        detail = (f"{d.get('label')} / {d.get('expected_level')} · {d.get('llm', {}).get('model', '')}"
                  if status == "pending"
                  else f"已确认为 {d.get('confirmed_case_id')}")
        events.append({
            "ts": d.get("created_at"), "kind": "draft",
            "title": f"LLM 草稿 {d.get('draft_id')}({status})",
            "detail": detail, "tag": status, "ref": d.get("draft_id"),
        })

    events.sort(key=lambda e: _ts_key(e["ts"]), reverse=True)
    return events[:max(1, min(int(limit), 50))]
