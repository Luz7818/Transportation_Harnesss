"""LLM 工作流:把 LLM 接进「沉淀 case」与「定位失败」两个薄弱环节。

编排原则(详见 docs/LLM.md 的 Tool & Workflow / Multi-Agent / Human-in-the-loop):
- 工作流优先:LLM 是确定性编排里的「步骤」,不是自由 Agent —— 每步输入输出都有
  Schema 校验,失败可降级、可重跑;
- LLM 永远不直接写评测资产:草稿必须经人工确认才成为 replaycase,
  诊断结论只是建议,不自动改动任何管线或用例;
- 输出可校验、可追溯:模型/用途/理由随草稿与诊断结果一起落盘。
"""

from __future__ import annotations

from datetime import datetime

from harness import storage
from harness.runner import ReplayRunner
from pipeline.versions import PIPELINES

from llm import store
from llm.runtime import get_runtime

VALID_LEVELS = ("畅通", "基本畅通", "缓行", "拥堵", "严重拥堵", "数据缺失")

DRAFT_SYSTEM = (
    "你是交通分析评测系统的坏例沉淀助手。根据用户对某路段分析结果的反馈,起草一条可重放的评测用例。\n"
    "只输出 JSON:{\"title\": 不超过40字的坏例标题, \"label\": 2~6字失败标签"
    "(如 阈值错误/指标计算错误/健壮性/结论缺失/边界处理/雨天场景),"
    " \"expected_level\": 「畅通/基本畅通/缓行/拥堵/严重拥堵/数据缺失」之一,"
    " \"expected_saturation\": 数字或 null, \"rationale\": 不超过60字的起草理由}"
)
ANALYZE_SYSTEM = (
    "你是交通分析管线的诊断专家(分析者角色)。输入是某版本在评测集上的失败案例清单。"
    "按失败标签归组,给出每组的根因分析与可执行的迭代建议。"
    "只输出 JSON:{\"items\": [{\"label\": 标签, \"root_cause\": 根因, "
    "\"suggestions\": [建议1, 建议2], \"affected_cases\": [case_id]}]}"
)
REVIEW_SYSTEM = (
    "你是评审者(第二智能体)。复核分析者的诊断:剔除不成立的结论、合并重复项、"
    "补充最大的一个风险提示。只输出 JSON:{\"items\": [与分析者相同的结构], "
    "\"reviewer_notes\": 不超过100字的复核意见}"
)


def draft_replaycase(complaint: str, dataset_name: str, segment_id: str | None = None) -> dict:
    """坏例沉淀助手:反馈原文 → 结构化 replaycase 草稿(pending,待人工确认)。"""
    complaint = str(complaint).strip()
    if not (5 <= len(complaint) <= 500):
        raise ValueError("反馈原文长度需在 5~500 字符之间")
    segments = storage.load_dataset(dataset_name)  # 非法名/不存在 → ValueError/FileNotFoundError
    by_id = {s["segment_id"]: s for s in segments}
    if segment_id is not None and segment_id not in by_id:
        raise ValueError(f"路段 {segment_id!r} 不在数据集中")

    out = PIPELINES["v2"](segments)  # 用当前最佳版本做参照判定
    judged = [f"{r['segment_id']} {r['name']}: {r['classification']}, "
              f"饱和度 {r['saturation'] if r['saturation'] is not None else '-'}"
              for r in out["segments"]]
    if segment_id is None:
        congested = out["congested_segments"]
        segment_id = congested[0] if congested else (segments[0]["segment_id"] if segments else None)

    seg_lines = "\n".join(f"{s['segment_id']} {s['name']} volume={s.get('volume')} "
                          f"speed={s.get('speed')}" for s in segments)
    user = (f"[用户反馈原文]\n{complaint}\n[-用户反馈原文]\n"
            f"[数据集]\n{dataset_name}\n[候选路段]\n{seg_lines}\n"
            f"[v2 当前判定]\n" + "\n".join(judged))

    runtime = get_runtime()
    data = runtime.complete_json(purpose="draft", system=DRAFT_SYSTEM, user=user)

    title = str(data.get("title", "")).strip()[:80]
    label = str(data.get("label", "")).strip()[:20] or "未分类"
    level = str(data.get("expected_level", "")).strip()
    if not title:
        raise ValueError("LLM 草稿缺少标题,请重试或手动沉淀")
    if level not in VALID_LEVELS:  # 治理:模型输出必须过校验,非法值不落盘
        raise ValueError(f"LLM 输出的期望等级非法:{level!r}(必须是 {'/'.join(VALID_LEVELS)})")
    sat = data.get("expected_saturation")
    if sat is not None:
        try:
            sat = round(float(sat), 4)
        except (TypeError, ValueError):
            sat = None
        if not 0 <= sat <= 3:
            sat = None

    draft = {
        "draft_id": store.next_draft_id(),
        "status": "pending",
        "complaint": complaint,
        "dataset_name": dataset_name,
        "segment_id": segment_id,
        "title": title,
        "label": label,
        "expected_level": level,
        "expected_saturation": sat,
        "rationale": str(data.get("rationale", ""))[:200],
        "llm": {"model": runtime.model, "kind": runtime.kind, "purpose": "draft"},
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "confirmed_case_id": None,
    }
    store.save_draft(draft)
    return draft


def diagnose_failures(version: str = "v2", evalset_name: str = "evalset_v1") -> dict:
    """失败诊断(双角色):分析者按标签归因 → 评审者复核收敛,输出迭代建议。"""
    if version not in PIPELINES:
        raise ValueError(f"未知版本 {version!r}")
    evalset = storage.load_evalset(evalset_name)
    cases = storage.load_evalset_cases(evalset_name)
    er = ReplayRunner().run_evalset(version, PIPELINES[version], evalset, cases)

    failures = []
    for r in er.results:
        if r.passed:
            continue
        detail = ";".join(c.detail for c in r.checks if not c.passed) or (r.error or "未通过")
        failures.append({"case_id": r.case_id, "label": r.label,
                         "title": r.title, "detail": detail[:200]})
    meta = {"version": version, "evalset_id": er.evalset_id, "accuracy": er.accuracy,
            "total": er.total, "passed": er.passed_count,
            "failure_count": len(failures), "model": get_runtime().model}
    if not failures:
        return {"items": [], "reviewer_notes": "全部案例通过,无需诊断。", "meta": meta}

    runtime = get_runtime()
    analyze_user = (f"[得分] {er.passed_count}/{er.total}\n"
                    f"[失败清单]\n" + json_dumps(failures))
    analyzed = runtime.complete_json(purpose="diagnose-analyze",
                                     system=ANALYZE_SYSTEM, user=analyze_user)
    review = runtime.complete_json(purpose="diagnose-review", system=REVIEW_SYSTEM,
                                   user="[分析结果]\n" + json_dumps(analyzed))

    real_ids = {f["case_id"] for f in failures}
    items = []
    for item in review.get("items", analyzed.get("items", [])):
        if not isinstance(item, dict) or not item.get("label"):
            continue
        # 治理:模型不得引用不存在的 case(幻觉过滤)
        affected = [cid for cid in item.get("affected_cases", []) if cid in real_ids]
        items.append({
            "label": str(item["label"])[:20],
            "root_cause": str(item.get("root_cause", ""))[:300],
            "suggestions": [str(s)[:200] for s in item.get("suggestions", [])][:5],
            "affected_cases": affected or sorted(
                f["case_id"] for f in failures if f["label"] == item["label"]),
        })
    return {"items": items, "reviewer_notes": str(review.get("reviewer_notes", ""))[:300],
            "meta": meta}


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
