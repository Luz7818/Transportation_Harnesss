"""沉淀首批 replaycase(模拟"收集反馈 → 建 replaycase 库 → 组评测集")。

运行一次即可:python scripts/seed_cases.py
幂等:重复运行会覆盖同名 case 文件。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import storage
from harness.models import CheckSpec, ReplayCase

CASES = [
    ReplayCase(
        case_id="rc-0001", title="学府路(V/C 0.91)被按车速误判为「严重拥堵」",
        label="阈值错误", dataset_name="base", source="线上点踩",
        created_at="2026-08-31T00:39:00",
        notes="用户反馈:该路段饱和度已超 0.9,按 V/C 标准应为「拥堵」;基线只看车速直接判成严重拥堵。",
        checks=[
            CheckSpec(type="classify", segment="S-02", expected="拥堵"),
            CheckSpec(type="metric", segment="S-02", field="saturation", expected=0.91, tol=0.01),
        ],
    ),
    ReplayCase(
        case_id="rc-0002", title="解放西路(V/C 0.71)应为「缓行」,基线判成「拥堵」",
        label="阈值错误", dataset_name="base", source="线上点踩",
        created_at="2026-08-31T00:39:00",
        notes="车速 29 km/h 触发了基线的「拥堵」阈值,但通行能力尚有富余。",
        checks=[CheckSpec(type="classify", segment="S-06", expected="缓行")],
    ),
    ReplayCase(
        case_id="rc-0003", title="泉山南路(V/C 1.03)应为「严重拥堵」并出现在结论中",
        label="阈值错误", dataset_name="base", source="人工标注",
        created_at="2026-08-31T00:40:00",
        notes="过饱和路段必须被识别为最高等级,且结论文字必须点明。",
        checks=[
            CheckSpec(type="classify", segment="S-10", expected="严重拥堵"),
            CheckSpec(type="conclusion_keyword", keywords=("严重拥堵",)),
        ],
    ),
    ReplayCase(
        case_id="rc-0004", title="长江路饱和度按车道数折算后应为 0.85(基线漏乘车道数)",
        label="指标计算错误", dataset_name="base", source="人工标注",
        created_at="2026-08-31T00:42:00",
        notes="基线用 volume/capacity_per_lane,得到 5.11;正确应为 volume/(capacity_per_lane×lane_count)。",
        checks=[CheckSpec(type="metric", segment="S-03", field="saturation", expected=0.85, tol=0.01)],
    ),
    ReplayCase(
        case_id="rc-0005", title="学府路延误指数应为 0.64(基线公式方向写反,输出 -0.64)",
        label="指标计算错误", dataset_name="base", source="线上点踩",
        created_at="2026-08-31T00:42:00",
        notes="delay_index = max(0, (free_flow_speed - speed) / free_flow_speed)。",
        checks=[CheckSpec(type="metric", segment="S-02", field="delay_index", expected=0.64, tol=0.02)],
    ),
    ReplayCase(
        case_id="rc-0006", title="云谷隧道流量传感器故障(volume 缺失)导致整个分析崩溃",
        label="健壮性", dataset_name="missing_volume", source="线上反馈",
        created_at="2026-08-31T00:43:00",
        notes="单点数据缺失不允许让整份分析报告失败;缺失路段应标记为「数据缺失」。",
        checks=[
            CheckSpec(type="no_crash"),
            CheckSpec(type="classify", segment="S-09", expected="数据缺失"),
        ],
    ),
    ReplayCase(
        case_id="rc-0007", title="拥堵路段没有任何处置建议,报告不可执行",
        label="结论缺失", dataset_name="base", source="线上点踩",
        created_at="2026-08-31T00:43:00",
        notes="每个拥堵/严重拥堵路段都应给出可执行的处置建议(信号配时/分流等)。",
        checks=[CheckSpec(type="recommendations")],
    ),
    ReplayCase(
        case_id="rc-0008", title="文昌桥饱和度应保留 2 位小数(1.01),基线取整成整数",
        label="精度问题", dataset_name="base", source="人工标注",
        created_at="2026-08-31T00:44:00",
        notes="饱和度取整后 0.85 变 1、1.01 变 1,级别判断与展示全乱。",
        checks=[CheckSpec(type="metric", segment="S-05", field="saturation", expected=1.01, tol=0.005)],
    ),
    ReplayCase(
        case_id="rc-0009", title="云龙大道 V/C 0.78 且车速比 0.28,应升级为「拥堵」",
        label="边界处理", dataset_name="base", source="人工标注",
        created_at="2026-08-31T00:45:00",
        notes="饱和度逼近上限且车速已显著下降的边界路段,实际体验已是拥堵,应升级等级。",
        checks=[CheckSpec(type="classify", segment="S-11", expected="拥堵")],
    ),
    ReplayCase(
        case_id="rc-0010", title="全局拥堵指数应按流量加权 ≈ 0.7944,简单平均会低估主干道压力",
        label="指标计算错误", dataset_name="base", source="人工标注",
        created_at="2026-08-31T00:46:00",
        notes="全局指数 = Σ(volume×min(V/C,1.2)) / Σ(volume),流量大的路段权重大。",
        checks=[CheckSpec(type="metric", field="global_congestion_index", expected=0.7944, tol=0.005)],
    ),
    ReplayCase(
        case_id="rc-0011", title="城东大道(V/C 0.42)应为「基本畅通」,基线只看车速判成「畅通」",
        label="阈值错误", dataset_name="base", source="线上抽检",
        created_at="2026-08-31T00:47:00",
        notes="中低饱和度区段需要区分「畅通/基本畅通」两档。",
        checks=[CheckSpec(type="classify", segment="S-01", expected="基本畅通")],
    ),
    ReplayCase(
        case_id="rc-0012", title="上游数据管道故障返回空数据集时,分析应优雅降级而非崩溃",
        label="健壮性", dataset_name="empty", source="线上反馈",
        created_at="2026-08-31T00:48:00",
        notes="空输入应返回空结果集(无拥堵路段、全局指数为空),不得抛 ZeroDivisionError。",
        checks=[
            CheckSpec(type="no_crash"),
            CheckSpec(type="congested_empty"),
        ],
    ),
    ReplayCase(
        case_id="rc-0013", title="环北路(V/C 0.24)为「畅通」——回归保护用例",
        label="回归保护", dataset_name="base", source="人工标注",
        created_at="2026-08-31T00:49:00",
        notes="基线本来就判对的场景,任何版本都不允许改坏。",
        checks=[CheckSpec(type="classify", segment="S-04", expected="畅通")],
    ),
]

EVALSET = {
    "evalset_id": "evalset_v1",
    "description": "由 8 月底线上反馈沉淀的 13 条 replaycase 组成",
    "created_at": "2026-08-31",
    "case_ids": [c.case_id for c in CASES],
}


def main() -> None:
    for case in CASES:
        path = storage.save_case(case)
        print(f"沉淀 {case.case_id} [{case.label}] -> {path.relative_to(storage.PROJECT_ROOT)}")
    import json
    manifest_path = storage.EVALSETS_DIR / f"{EVALSET['evalset_id']}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(EVALSET, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"生成评测集清单 -> {manifest_path.relative_to(storage.PROJECT_ROOT)}(共 {len(CASES)} 条)")


if __name__ == "__main__":
    main()
