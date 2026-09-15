"""交通分析管线的各版本实现与版本登记。

v0 为"线上最初的基线版本"——正是它产生了一批 badcase(阈值错误/指标算错/崩溃/无建议等);
v1、v2 为依据评测报告做的两轮迭代,遵循 code-optimization 技能的"最多 2 轮"上限:
  - 第 1 轮(v1):算法/公式层面的修正(影响最大);
  - 第 2 轮(v2):边界处理与聚合方式的精修。
每轮【优化内容】记录在 CHANGELOG,供报告与看板使用。

分级标准(基于饱和度 V/C,城市道路常用口径):
  畅通 [0,0.4) | 基本畅通 [0.4,0.6) | 缓行 [0.6,0.8) | 拥堵 [0.8,1.0) | 严重拥堵 [1.0,+∞)

统一输出结构:
{
  "version": "v1",
  "segments": [{segment_id, name, classification, saturation, delay_index, speed_ratio, status, volume}],
  "congested_segments": [segment_id, ...],   # 按饱和度降序
  "global_congestion_index": float | None,   # 全局拥堵指数(越大越堵)
  "recommendations": [{segment_id, text}],
  "summary": str
}
"""

from collections import Counter

CONGESTED_LEVELS = ("拥堵", "严重拥堵")
MISSING_LEVEL = "数据缺失"

# 全局指数按流量加权时,对过饱和路段的 V/C 做 1.2 封顶,避免单点极端值支配整体
SATURATION_CAP = 1.2

# v2 边界升级规则:V/C 处于 [0.75, 0.8) 且速度比 < 0.35 时升级为「拥堵」
ESCALATION_BAND = (0.75, 0.8)
ESCALATION_SPEED_RATIO = 0.35


def _classify_by_saturation(sat: float) -> str:
    if sat < 0.4:
        return "畅通"
    if sat < 0.6:
        return "基本畅通"
    if sat < 0.8:
        return "缓行"
    if sat < 1.0:
        return "拥堵"
    return "严重拥堵"


def _advice(level: str, name: str) -> str:
    if level == "严重拥堵":
        return f"{name}:建议立即启动分流预案并优化信号配时,安排现场疏导。"
    return f"{name}:建议优化信号配时,视情况引导车流绕行。"


def _summary_counts(valid_rows: list[dict]) -> Counter:
    return Counter(r["classification"] for r in valid_rows)


def analyze_v0(segments: list[dict]) -> dict:
    """基线版本(线上最初实现,已知缺陷):

    - 仅凭车速粗分四档、不看流量与通行能力 → 高饱和路段被误判;
    - 饱和度漏乘车道数且取整;
    - 延误指数公式方向写反;
    - volume 缺失直接抛异常;
    - 没有任何处置建议。
    """
    rows = []
    for seg in segments:
        speed = seg["speed"]
        if speed < 20:
            level = "严重拥堵"
        elif speed < 30:
            level = "拥堵"
        elif speed < 40:
            level = "缓行"
        else:
            level = "畅通"
        saturation = round(seg["volume"] / seg["capacity_per_lane"])  # 漏乘 lane_count,且取整
        delay = round((speed - seg["free_flow_speed"]) / seg["free_flow_speed"], 2)  # 方向写反
        rows.append({
            "segment_id": seg["segment_id"], "name": seg["name"], "classification": level,
            "saturation": saturation, "delay_index": delay,
            "speed_ratio": round(speed / seg["free_flow_speed"], 2), "status": "ok",
        })
    congested = [r["segment_id"] for r in rows if r["classification"] in CONGESTED_LEVELS]
    global_index = round(sum(r["saturation"] for r in rows) / len(rows), 4)  # 空数据集 → ZeroDivisionError
    cnt = Counter(r["classification"] for r in rows)
    summary = (f"共分析 {len(rows)} 个路段(按车速判定):畅通 {cnt.get('畅通', 0)} 个、"
               f"缓行 {cnt.get('缓行', 0)} 个、拥堵 {cnt.get('拥堵', 0)} 个、"
               f"严重拥堵 {cnt.get('严重拥堵', 0)} 个。")
    return {
        "version": "v0", "segments": rows, "congested_segments": congested,
        "global_congestion_index": global_index, "recommendations": [], "summary": summary,
    }


def analyze_v1(segments: list[dict]) -> dict:
    """v1(第 1 轮:算法修正)——修复基线的公式与分级错误:

    - 拥堵分级改为以饱和度 V/C 为主(五级),车速只作参考;
    - 饱和度 = volume / (capacity_per_lane × lane_count),保留 2 位小数;
    - 延误指数 = max(0, (free_flow_speed - speed) / free_flow_speed);
    - volume 缺失的路段标记「数据缺失」并从聚合中剔除,不再崩溃;
    - 为拥堵/严重拥堵路段生成处置建议。
    """
    rows, missing = [], []
    for seg in segments:
        if seg.get("volume") is None:
            missing.append(seg["segment_id"])
            rows.append({
                "segment_id": seg["segment_id"], "name": seg["name"],
                "classification": MISSING_LEVEL, "saturation": None, "delay_index": None,
                "speed_ratio": None, "status": "数据缺失(volume 缺失)", "volume": None,
            })
            continue
        capacity = seg["capacity_per_lane"] * seg["lane_count"]
        sat_raw = seg["volume"] / capacity
        speed, ffs = seg["speed"], seg["free_flow_speed"]
        rows.append({
            "segment_id": seg["segment_id"], "name": seg["name"],
            "classification": _classify_by_saturation(sat_raw),
            "saturation": round(sat_raw, 2),
            "delay_index": round(max(0.0, (ffs - speed) / ffs), 2),
            "speed_ratio": round(speed / ffs, 2), "status": "ok", "volume": seg["volume"],
        })

    valid = [r for r in rows if r["status"] == "ok"]
    congested = [r["segment_id"] for r in rows if r["classification"] in CONGESTED_LEVELS]
    global_index = round(sum(r["saturation"] for r in valid) / len(valid), 4) if valid else None
    recommendations = [
        {"segment_id": r["segment_id"], "text": _advice(r["classification"], r["name"])}
        for r in rows if r["classification"] in CONGESTED_LEVELS
    ]
    cnt = _summary_counts(valid)
    summary = (f"共分析 {len(segments)} 个路段(有效 {len(valid)} 个,数据缺失 {len(missing)} 个):"
               f"按饱和度 V/C 五级划分,畅通 {cnt.get('畅通', 0)}、基本畅通 {cnt.get('基本畅通', 0)}、"
               f"缓行 {cnt.get('缓行', 0)}、拥堵 {cnt.get('拥堵', 0)}、严重拥堵 {cnt.get('严重拥堵', 0)};"
               f"全局拥堵指数 {'无' if global_index is None else global_index}。")
    return {
        "version": "v1", "segments": rows, "congested_segments": congested,
        "global_congestion_index": global_index, "recommendations": recommendations,
        "summary": summary,
    }


def analyze_v2(segments: list[dict]) -> dict:
    """v2(第 2 轮:边界与聚合优化)——在 v1 基础上精修:

    - 边界升级:V/C ∈ [0.75, 0.8) 且速度比 < 0.35 → 升级为「拥堵」(贴近真实通行体验);
    - 全局拥堵指数改为按流量加权,并对单点 V/C 做 1.2 封顶;
    - 空数据集/零有效路段输出空结果集,全局指数为 null,不报错;
    - 拥堵路段按饱和度降序排列;单次遍历完成统计,减少重复计算。
    """
    rows, missing = [], []
    sat_raw_by_id: dict[str, float] = {}  # 保留未取整的 V/C,供边界升级/加权/排序使用
    for seg in segments:
        if seg.get("volume") is None:
            missing.append(seg["segment_id"])
            rows.append({
                "segment_id": seg["segment_id"], "name": seg["name"],
                "classification": MISSING_LEVEL, "saturation": None, "delay_index": None,
                "speed_ratio": None, "status": "数据缺失(volume 缺失)", "volume": None,
            })
            continue
        capacity = seg["capacity_per_lane"] * seg["lane_count"]
        sat_raw = seg["volume"] / capacity
        speed, ffs = seg["speed"], seg["free_flow_speed"]
        ratio_raw = speed / ffs
        level = _classify_by_saturation(sat_raw)
        if ESCALATION_BAND[0] <= sat_raw < ESCALATION_BAND[1] and ratio_raw < ESCALATION_SPEED_RATIO:
            level = "拥堵"  # 边界升级:饱和度逼近上限且车速已显著下降
        sat_raw_by_id[seg["segment_id"]] = sat_raw
        rows.append({
            "segment_id": seg["segment_id"], "name": seg["name"], "classification": level,
            "saturation": round(sat_raw, 2),
            "delay_index": round(max(0.0, (ffs - speed) / ffs), 2),
            "speed_ratio": round(ratio_raw, 2), "status": "ok", "volume": seg["volume"],
        })

    valid = [r for r in rows if r["status"] == "ok"]
    congested = [r["segment_id"] for r in sorted(
        (r for r in rows if r["classification"] in CONGESTED_LEVELS),
        key=lambda r: sat_raw_by_id[r["segment_id"]], reverse=True)]
    total_volume = sum(r["volume"] for r in valid)
    global_index = (round(sum(r["volume"] * min(sat_raw_by_id[r["segment_id"]], SATURATION_CAP)
                              for r in valid) / total_volume, 4)
                    if valid else None)
    recommendations = [
        {"segment_id": r["segment_id"], "text": _advice(r["classification"], r["name"])}
        for r in rows if r["classification"] in CONGESTED_LEVELS
    ]
    cnt = _summary_counts(valid)
    summary = (f"共分析 {len(segments)} 个路段(有效 {len(valid)} 个,数据缺失 {len(missing)} 个):"
               f"按饱和度 V/C 五级划分,畅通 {cnt.get('畅通', 0)}、基本畅通 {cnt.get('基本畅通', 0)}、"
               f"缓行 {cnt.get('缓行', 0)}、拥堵 {cnt.get('拥堵', 0)}、严重拥堵 {cnt.get('严重拥堵', 0)};"
               f"全局拥堵指数(流量加权){'无' if global_index is None else global_index}。")
    return {
        "version": "v2", "segments": rows, "congested_segments": congested,
        "global_congestion_index": global_index, "recommendations": recommendations,
        "summary": summary,
    }


PIPELINES = {
    "v0": analyze_v0,
    "v1": analyze_v1,
    "v2": analyze_v2,
}

CHANGELOG = {
    "v0": {"name": "基线(线上最初版本)", "changes": []},
    "v1": {"name": "算法修正", "changes": [
        "拥堵分级改为以饱和度 V/C 为主(0.4/0.6/0.8/1.0 五级),车速只作参考",
        "修正饱和度公式:saturation = volume / (capacity_per_lane × lane_count)",
        "修正延误指数公式:delay_index = max(0, (free_flow_speed - speed) / free_flow_speed)",
        "volume 缺失的路段标记「数据缺失」并从聚合中剔除,不再崩溃",
        "为拥堵/严重拥堵路段生成处置建议;指标统一保留 2 位小数",
    ]},
    "v2": {"name": "边界与聚合优化", "changes": [
        "边界升级规则:V/C ∈ [0.75, 0.8) 且速度比 < 0.35 时升级为「拥堵」",
        "全局拥堵指数改为按流量加权(单点 V/C 以 1.2 封顶)",
        "空数据集/零有效路段输出空结果集,全局指数为 null,不报错",
        "拥堵路段按饱和度降序排列;单次遍历完成统计",
    ]},
}
