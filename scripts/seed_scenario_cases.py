"""沉淀"雨天早高峰"场景评测集:检验管线在恶劣天气情景下的稳健性。

期望值全部按 v2 公式人工核算:
  S-02: 2950/(1445×2)=1.0208 → 严重拥堵,饱和度 1.02
  S-06: 3350/(1445×3)=0.7728 → 缓行;全局指数(流量加权)= Σ vol×min(V/C,1.2)/Σ vol = 0.8927
  S-10: 3350/(1445×2)=1.1592 → 严重拥堵,饱和度 1.16

运行:python scripts/seed_scenario_cases.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import storage
from harness.models import CheckSpec, ReplayCase

CASES = [
    ReplayCase(
        case_id="rsc-001", title="雨天学府路(V/C 1.02)应升级为「严重拥堵」",
        label="雨天场景", dataset_name="rain_peak", source="场景标定",
        created_at="2026-09-05T09:00:00",
        notes="降雨使通行能力下降 15%,同等级流量下 V/C 突破 1.0;恶劣天气预警必须覆盖该路段。",
        checks=[
            CheckSpec(type="classify", segment="S-02", expected="严重拥堵"),
            CheckSpec(type="metric", segment="S-02", field="saturation", expected=1.02, tol=0.01),
        ],
    ),
    ReplayCase(
        case_id="rsc-002", title="雨天解放西路保持「缓行」,全局拥堵指数 0.8927",
        label="雨天场景", dataset_name="rain_peak", source="场景标定",
        created_at="2026-09-05T09:00:00",
        notes="饱和度 0.7728 落在缓行区间,且车速比 0.5 未触发边界升级;全局指数应较基准情景(0.7944)明显抬升。",
        checks=[
            CheckSpec(type="classify", segment="S-06", expected="缓行"),
            CheckSpec(type="metric", field="global_congestion_index", expected=0.8927, tol=0.005),
        ],
    ),
    ReplayCase(
        case_id="rsc-003", title="雨天泉山南路(V/C 1.16)应为「严重拥堵」且指标保留两位小数",
        label="雨天场景", dataset_name="rain_peak", source="场景标定",
        created_at="2026-09-05T09:00:00",
        notes="过饱和路段的精度回归:1.1592 → 展示 1.16。",
        checks=[
            CheckSpec(type="classify", segment="S-10", expected="严重拥堵"),
            CheckSpec(type="metric", segment="S-10", field="saturation", expected=1.16, tol=0.01),
        ],
    ),
]

EVALSET = {
    "evalset_id": "evalset_scenario_rain",
    "description": "雨天早高峰场景评测集:检验恶劣天气下的分级与指标稳健性(3 条)",
    "created_at": "2026-09-05",
    "case_ids": [c.case_id for c in CASES],
}


def main() -> None:
    for case in CASES:
        path = storage.save_case(case)
        print(f"沉淀 {case.case_id} [{case.label}] -> {path.relative_to(storage.PROJECT_ROOT)}")
    manifest_path = storage.EVALSETS_DIR / f"{EVALSET['evalset_id']}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(EVALSET, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"生成评测集清单 -> {manifest_path.relative_to(storage.PROJECT_ROOT)}(共 {len(CASES)} 条)")


if __name__ == "__main__":
    main()
