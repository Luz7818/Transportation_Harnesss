"""离线确定性 Mock:按用途从提示词输入本身推导输出(不随机、不联网)。

Mock 的职责边界:只保证「工作流编排可离线演示与测试」,
不追求与真实模型等价的语义质量 —— 配置 LLM_API_KEY 后即被真实端点替换。
"""

from __future__ import annotations

import json
import re

_LEVEL_WORDS = ("严重拥堵", "拥堵", "缓行", "基本畅通", "畅通")
_LABEL_RULES = (("崩溃", "健壮性"), ("误判", "阈值错误"), ("建议", "结论缺失"),
                ("加权", "指标计算错误"), ("精度", "精度问题"), ("雨天", "雨天场景"))
_ROOT_CAUSE = {
    "阈值错误": "分级阈值或等级判定与业务口径不一致,需核对 V/C 分级边界",
    "指标计算错误": "指标公式或聚合方式有误(车道数/加权/精度),需对照口径逐项核对",
    "健壮性": "对缺失字段、空输入等异常数据缺乏防御,聚合前未做有效性过滤",
    "结论缺失": "结论文本未覆盖关键信息或缺少可执行的处置建议",
    "精度问题": "指标保留位数/取整方式不统一,导致对比与回归误报",
    "边界处理": "边界条件(临界 V/C、极低速)未单独处理,临界场景判定漂移",
    "回归保护": "此前已修复的行为出现回退,需检查本轮改动是否触碰旧逻辑",
    "雨天场景": "场景化参数(通行能力折减/车速普降)未参与判定,恶劣天气下灵敏度不足",
}
_SUGGESTIONS = {
    "阈值错误": "以 V/C 五级标准复核 _classify 阈值边界;为临界区间补一条边界用例",
    "指标计算错误": "核对 saturation/delay_index 公式与全局指数聚合方式,补公式级单测",
    "健壮性": "对 volume 缺失与空数据集补降级分支(标记缺失、输出空结果),补 no_crash 用例",
    "结论缺失": "为拥堵路段强制生成处置建议,并在结论中回显关键计数",
    "精度问题": "统一指标保留 2 位小数,禁止取整;对 round 行为补单测",
    "边界处理": "引入边界升级规则(V/C 逼近上限且车速显著下降),补边界用例",
    "回归保护": "回退本轮改动,并在 CHANGELOG 标注影响面",
    "雨天场景": "让容量折减系数参与 V/C 计算,并校验雨天评测集得分",
}


def _section(user: str, name: str) -> str:
    m = re.search(rf"\[{re.escape(name)}\]\n(.*?)(?:\n\[-{re.escape(name)}\]|\Z)", user, re.S)
    return m.group(1).strip() if m else ""


def _pick_level(text: str) -> str:
    for lv in _LEVEL_WORDS:  # 长词优先,避免「拥堵」抢先命中「严重拥堵」
        if lv in text:
            return lv
    return "拥堵"


def _pick_label(text: str) -> str:
    for word, label in _LABEL_RULES:
        if word in text:
            return label
    return "未分类"


def _parse_judgments(user: str) -> list[dict]:
    rows = []
    for line in _section(user, "v2 当前判定").splitlines():
        m = re.match(r"(\S+)\s+(.+?):\s*(\S+),\s*饱和度\s*([\d.]+|-)", line.strip())
        if m:
            rows.append({"segment_id": m.group(1), "name": m.group(2),
                         "level": m.group(3), "sat": m.group(4)})
    return rows


def render(purpose: str, user: str) -> dict:
    if purpose == "draft":
        return _draft(user)
    if purpose == "judge":
        return _judge(user)
    if purpose == "diagnose-analyze":
        return _diagnose_analyze(user)
    if purpose == "diagnose-review":
        return _diagnose_review(user)
    return {"note": f"mock 未实现用途 {purpose}"}


def _draft(user: str) -> dict:
    complaint = _section(user, "用户反馈原文")
    judgments = _parse_judgments(user)
    target = next((r for r in judgments if r["level"] in complaint), None)
    if target is None:
        target = next((r for r in judgments if r["level"] in ("拥堵", "严重拥堵")),
                      judgments[0] if judgments else None)
    sat = None
    m = re.search(r"V/C\s*[=:]?\s*([0-9.]+)", complaint)
    if m:
        sat = float(m.group(1))
    elif target and target["sat"] not in ("-", ""):
        sat = float(target["sat"])
    return {
        "title": complaint[:48] or "未命名坏例",
        "label": _pick_label(complaint),
        "expected_level": _pick_level(complaint) if any(lv in complaint for lv in _LEVEL_WORDS)
                          else (target["level"] if target else "拥堵"),
        "expected_saturation": sat,
        "rationale": "离线 Mock:基于反馈关键词与 v2 当前判定推导;配置 LLM_API_KEY 后由大模型生成更准确的草稿。",
    }


def _judge(user: str) -> dict:
    text = _section(user, "评分对象")
    score = 0.5
    if "拥堵" in text or "严重拥堵" in text:
        score += 0.2
    if len(text) > 40:
        score += 0.2
    if "建议" in text:
        score += 0.1
    score = round(min(score, 1.0), 2)
    return {"score": score,
            "rationale": f"离线 Mock 评分:确定性启发式(关键词覆盖/篇幅/建议完备),得分 {score}。"}


def _diagnose_analyze(user: str) -> dict:
    try:
        failures = json.loads(_section(user, "失败清单") or "[]")
    except json.JSONDecodeError:
        failures = []
    items, seen = [], set()
    for row in failures:
        label = row.get("label", "未分类")
        if label in seen:
            continue
        seen.add(label)
        items.append({
            "label": label,
            "root_cause": _ROOT_CAUSE.get(label, "失败原因待人工确认"),
            "suggestions": [_SUGGESTIONS.get(label, "结合具体 case 逐条分析后再定迭代方向")],
            "affected_cases": [row.get("case_id", "")],
        })
    for item in items:  # 同标签的其余 case 一并归入
        item["affected_cases"] = [r.get("case_id", "") for r in failures
                                  if r.get("label") == item["label"]]
    return {"items": items}


def _diagnose_review(user: str) -> dict:
    try:
        data = json.loads(_section(user, "分析结果") or "{}")
    except json.JSONDecodeError:
        data = {}
    items = data.get("items", [])
    return {"items": items,
            "reviewer_notes": "离线 Mock 评审:根因与建议按失败标签一一对应,无重复项;"
                              "配置 LLM_API_KEY 后由评审角色复核因果链与建议可行性。"}
