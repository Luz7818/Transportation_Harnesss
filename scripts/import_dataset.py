"""数据集摄取 CLI:把 CSV/JSON 样例写入 pipeline/data/<name>.json。

  python scripts/import_dataset.py <input.csv|.json> --name <数据集名> --source <来源> \
      [--captured-at "YYYY-MM-DD HH:MM"] [--description <描述>] \
      [--scenario-tag <标签> --scenario-insight <解读>]

「新数据源」扩展点(docs/ARCHITECTURE.md §10)的落地面:读入 → 校验 → 复用
harness.storage 的 _safe_name/_write_json 原子写。schema 取舍按现有合法资产
(pipeline/data/*.json):
  - segments 允许为空数组(同 empty.json);
  - 顶层 scenario 可选(同 missing_volume.json):JSON 自带时透传,CSV 用
    --scenario-tag/--scenario-insight 成对提供;
  - 有路段时 8 字段(segment_id/name/length_km/lane_count/capacity_per_lane/
    volume/speed/free_flow_speed)必填,数值须非负且有限,segment_id 唯一;
  - volume 可为 null/空单元格(同 missing_volume.json 的传感器缺测,管线按
    「数据缺失」降级,不视为非法)。
校验失败逐条报出具体字段并以退出码 2 结束;成功退出码 0,同名数据集幂等覆盖。
写入 source(必填)与 captured_at 溯源字段,经 list_datasets()/api/datasets 透出。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from harness import storage

# 有路段时的 8 个必填字段(顺序即写出顺序,与现有数据集一致)
SEGMENT_FIELDS = ("segment_id", "name", "length_km", "lane_count",
                  "capacity_per_lane", "volume", "speed", "free_flow_speed")
_NUMERIC_FIELDS = SEGMENT_FIELDS[2:]  # 后 6 个是数值字段;其中 volume 允许 null 表缺测
_INT_RE = re.compile(r"^[+-]?\d+$")
_EXIT_INVALID = 2  # 校验失败退出码(与 argparse 用法错误一致)


def _coerce_number(field: str, raw: str):
    """CSV 单元格 → int/float;解析不了就原样保留字符串,交给校验器报具体字段。"""
    try:
        value = int(raw) if _INT_RE.match(raw) else float(raw)
    except ValueError:
        return raw
    return value if math.isfinite(value) else raw


def _read_csv(path: Path) -> tuple[list[dict], dict, list[str]]:
    """CSV → (segments, meta, problems)。表头须恰含 8 字段;volume 空单元格 → None。"""
    problems: list[str] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        missing_cols = [c for c in SEGMENT_FIELDS if c not in headers]
        extra_cols = [c for c in headers if c not in SEGMENT_FIELDS]
        if missing_cols:
            problems.append(f"CSV 缺列: {', '.join(missing_cols)}")
        if extra_cols:
            problems.append(f"CSV 有未知列(只认 8 个路段字段): {', '.join(extra_cols)}")
        segments: list[dict] = []
        for row_no, row in enumerate(reader, start=2):  # 第 1 行是表头
            if all(not (row.get(c) or "").strip() for c in SEGMENT_FIELDS):
                continue  # 整行空白,跳过
            where = f"CSV 第 {row_no} 行: "
            seg: dict = {}
            for col in SEGMENT_FIELDS:
                raw = (row.get(col) or "").strip()
                if col not in _NUMERIC_FIELDS:
                    seg[col] = raw
                elif raw == "":
                    if col == "volume":
                        seg[col] = None  # 缺测的合法形态(同 missing_volume.json)
                    else:
                        problems.append(f"{where}字段 {col} 不能为空")
                else:
                    seg[col] = _coerce_number(col, raw)
            segments.append(seg)
    return segments, {}, problems


def _read_json(path: Path) -> tuple[list, dict, list[str]]:
    """JSON → (segments, meta, problems)。segments 必填(可为 []);meta 三键透传。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return [], {}, [f"JSON 顶层必须是对象,实际 {type(data).__name__}"]
    problems: list[str] = []
    for key in ("description", "captured_at"):
        if key in data and not isinstance(data[key], str):
            problems.append(f"JSON 顶层 {key} 必须是字符串,实际 {type(data[key]).__name__}")
    if "segments" not in data:
        problems.append("JSON 顶层缺 segments 键(可为空数组,同 pipeline/data/empty.json)")
    segments = data.get("segments")
    meta = {k: data[k] for k in ("description", "captured_at", "scenario") if k in data}
    return (segments if isinstance(segments, list) else []), meta, problems


def validate_segments(segments) -> list[str]:
    """路段 schema 校验:返回问题列表(空列表 = 通过),每条都指到具体字段。"""
    if not isinstance(segments, list):
        return [f"segments 必须是数组,实际 {type(segments).__name__}"]
    problems: list[str] = []
    first_seen: dict[str, int] = {}
    for idx, seg in enumerate(segments, start=1):
        where = f"segments[{idx}]: "
        if not isinstance(seg, dict):
            problems.append(f"{where}必须是对象,实际 {type(seg).__name__}")
            continue
        missing = [f for f in SEGMENT_FIELDS if f not in seg]
        if missing:
            problems.append(f"{where}缺字段: {', '.join(missing)}")
        for field in ("segment_id", "name"):
            value = seg.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{where}字段 {field} 必须是非空字符串,实际 {value!r}")
        for field in _NUMERIC_FIELDS:
            if field not in seg:
                continue  # 缺字段已单独报,不重复
            value = seg[field]
            if value is None:
                if field != "volume":
                    problems.append(f"{where}字段 {field} 不能为 null(只有 volume 允许缺测)")
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not math.isfinite(value):
                problems.append(f"{where}字段 {field} 必须是有限数值,实际 {value!r}")
            elif value < 0:
                problems.append(f"{where}字段 {field} = {value} 为负值")
        seg_id = seg.get("segment_id")
        if isinstance(seg_id, str) and seg_id.strip():
            if seg_id in first_seen:
                problems.append(f"{where}segment_id 重复: {seg_id}"
                                f"(首次出现于 segments[{first_seen[seg_id]}])")
            else:
                first_seen[seg_id] = idx
    return problems


def _merge_scenario(args: argparse.Namespace, file_scenario, problems: list[str]) -> dict | None:
    """CSV 的 --scenario-* 成对旗标优先;否则透传 JSON 内合法的 scenario;都没有则省略。"""
    tag, insight = args.scenario_tag, args.scenario_insight
    if (tag is None) != (insight is None):
        problems.append("--scenario-tag 与 --scenario-insight 必须成对提供")
        return None
    if tag is not None:
        return {"tag": tag, "insight": insight}
    if file_scenario is None:
        return None
    if (isinstance(file_scenario, dict)
            and isinstance(file_scenario.get("tag"), str)
            and isinstance(file_scenario.get("insight"), str)):
        return file_scenario
    problems.append("JSON 内 scenario 须为含字符串 tag/insight 的对象")
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把 CSV/JSON 数据集样例写入 pipeline/data/(校验 + 原子写)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="输入文件路径(.csv 或 .json)")
    parser.add_argument("--name", help="数据集名,用作文件名(默认取输入文件名主干;"
                                       "经 storage._safe_name 白名单校验)")
    parser.add_argument("--source", required=True, help="数据来源标注(溯源字段 source,必填)")
    parser.add_argument("--captured-at", dest="captured_at",
                        help='采集时间,如 "2026-09-05 08:00"(默认当前时间;'
                             "JSON 内自带 captured_at 时可不传)")
    parser.add_argument("--description", help="数据集描述(默认取 JSON 内 description)")
    parser.add_argument("--scenario-tag", dest="scenario_tag",
                        help="情景标签(与 --scenario-insight 成对,CSV 输入用)")
    parser.add_argument("--scenario-insight", dest="scenario_insight",
                        help="情景解读(与 --scenario-tag 成对,CSV 输入用)")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    path = Path(args.input)
    try:
        if path.suffix.lower() == ".csv":
            segments, meta, problems = _read_csv(path)
        elif path.suffix.lower() == ".json":
            segments, meta, problems = _read_json(path)
        else:
            segments, meta = [], {}
            problems = [f"不支持的输入类型 {path.suffix!r}(仅支持 .csv / .json)"]
    except OSError as exc:
        print(f"导入失败: {exc}", file=sys.stderr)
        sys.exit(_EXIT_INVALID)
    except json.JSONDecodeError as exc:
        print(f"导入失败: {path} 不是合法 JSON: {exc}", file=sys.stderr)
        sys.exit(_EXIT_INVALID)

    name = args.name or path.stem
    try:
        name = storage._safe_name(name, "数据集名")
    except ValueError as exc:
        problems.append(str(exc))

    description = args.description if args.description is not None else meta.get("description", "")
    scenario = _merge_scenario(args, meta.get("scenario"), problems)
    captured_at = args.captured_at or meta.get("captured_at") \
        or datetime.now().strftime("%Y-%m-%d %H:%M")
    problems += validate_segments(segments)

    if problems:
        print(f"导入失败:{path.name} 共 {len(problems)} 处校验问题:", file=sys.stderr)
        for item in problems:
            print(f"  - {item}", file=sys.stderr)
        sys.exit(_EXIT_INVALID)

    doc: dict = {"dataset_id": name, "description": description}
    if scenario is not None:
        doc["scenario"] = scenario
    doc["captured_at"] = captured_at
    doc["source"] = args.source
    doc["segments"] = segments

    target = storage.DATA_DIR / f"{name}.json"
    storage._write_json(target, doc)  # 原子写(临时文件 + os.replace),见 harness/storage.py
    print(f"已写入 {target}(segments: {len(segments)},source: {args.source},"
          f"captured_at: {captured_at})")


if __name__ == "__main__":
    main()
