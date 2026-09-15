"""本地存储:replaycase 库(cases/)、评测集清单(evalsets/)、数据集(pipeline/data/)、报告(reports/)。

cases 按失败标签分目录存放,一个 case 一个 JSON 文件,便于人工浏览与 git 管理。
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

from harness.models import ReplayCase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = PROJECT_ROOT / "cases"
EVALSETS_DIR = PROJECT_ROOT / "evalsets"
DATA_DIR = PROJECT_ROOT / "pipeline" / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

# 写文件互斥锁:FastAPI 的同步端点跑在线程池里,并发写必须串行化
_LOCK = threading.Lock()

# 标签会用作目录名,过滤文件系统/路径注入风险字符
_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')

# 数据集/评测集/报告等名称直接拼进文件路径(HTTP 入参可达),只放行安全字符,
# 从源头杜绝 ../ 路径穿越读取任意 JSON
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-\u4e00-\u9fff]+$")


def _safe_name(name: str, kind: str = "名称") -> str:
    """校验用作文件名的标识符(数据集/评测集/报告 ID),非法即抛 ValueError。"""
    name = str(name).strip()
    if not name or len(name) > 128 or not _SAFE_NAME.fullmatch(name):
        raise ValueError(f"非法{kind}: {name!r}")
    return name


def _read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload) -> None:
    """原子写入:先写临时文件再替换,避免并发/中断导致 JSON 半截损坏。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def safe_label(label: str) -> str:
    """把失败标签净化成可安全用作目录名的字符串。"""
    cleaned = _UNSAFE_CHARS.sub("_", str(label).strip()).strip(". ")
    return cleaned or "未分类"


def load_cases() -> list[ReplayCase]:
    """扫描 cases/ 下全部 replaycase,按 case_id 排序返回。"""
    cases = [ReplayCase.from_dict(_read_json(p)) for p in sorted(CASES_DIR.glob("*/*.json"))]
    return sorted(cases, key=lambda c: c.case_id)


def load_case(case_id: str) -> ReplayCase | None:
    for case in load_cases():
        if case.case_id == case_id:
            return case
    return None


def delete_case(case_id: str) -> bool:
    """删除一条 replaycase,并同步从所有评测集清单中移除;case 不存在返回 False。

    文件删除与评测集清单更新在同一把锁内完成,避免并发下出现"悬空引用"。
    """
    target = None
    for path in CASES_DIR.glob("*/*.json"):
        if path.stem == case_id:
            target = path
            break
    if target is None:
        return False
    with _LOCK:
        target.unlink()
        for manifest_path in EVALSETS_DIR.glob("*.json"):
            payload = _read_json(manifest_path)
            if case_id in payload.get("case_ids", []):
                payload["case_ids"] = [c for c in payload["case_ids"] if c != case_id]
                _write_json(manifest_path, payload)
    return True


def save_case(case: ReplayCase) -> Path:
    """沉淀一条 replaycase 到 cases/<标签>/<case_id>.json(幂等覆盖,原子写入)。"""
    path = CASES_DIR / safe_label(case.label) / f"{case.case_id}.json"
    with _LOCK:
        _write_json(path, case.to_dict())
    return path


def load_evalset(name: str = "evalset_v1") -> dict:
    """加载评测集清单:{"evalset_id", "description", "case_ids"}。"""
    path = EVALSETS_DIR / f"{_safe_name(name, '评测集名')}.json"
    payload = _read_json(path)
    payload.setdefault("evalset_id", name)
    return payload


def list_evalsets() -> list[dict]:
    """列出全部评测集清单(含规模),供看板/客户端下拉选择。"""
    out = []
    for p in sorted(EVALSETS_DIR.glob("*.json")):
        payload = _read_json(p)
        out.append({
            "evalset_id": payload.get("evalset_id", p.stem),
            "description": payload.get("description", ""),
            "created_at": payload.get("created_at", ""),
            "case_count": len(payload.get("case_ids", [])),
        })
    return out


def load_evalset_cases(name: str = "evalset_v1") -> list[ReplayCase]:
    """按清单中 case_ids 的顺序取出 replaycase(评测集的构成是版本化的)。"""
    manifest = load_evalset(name)
    by_id = {c.case_id: c for c in load_cases()}
    missing = [cid for cid in manifest["case_ids"] if cid not in by_id]
    if missing:
        raise KeyError(f"评测集 {name} 引用了不存在的 case: {missing}")
    return [by_id[cid] for cid in manifest["case_ids"]]


def add_case_to_evalset(case_id: str, name: str = "evalset_v1") -> bool:
    """把已存在的 case 加入评测集清单;已存在则返回 False。"""
    with _LOCK:
        path = EVALSETS_DIR / f"{_safe_name(name, '评测集名')}.json"
        payload = _read_json(path)
        if case_id in payload["case_ids"]:
            return False
        payload["case_ids"].append(case_id)
        _write_json(path, payload)
        return True


def load_dataset(name: str) -> list[dict]:
    """加载交通数据集,返回路段列表。"""
    path = DATA_DIR / f"{_safe_name(name, '数据集名')}.json"
    return _read_json(path)["segments"]


def list_datasets() -> list[dict]:
    out = []
    for p in sorted(DATA_DIR.glob("*.json")):
        payload = _read_json(p)
        out.append({"name": p.stem, "description": payload.get("description", ""),
                    "scenario": payload.get("scenario")})
    return out


def save_report(version: str, payload: dict) -> Path:
    """保存一次评测的 JSON 报告,文件名形如 report_v1_20260914_010203.json。"""
    ts = payload.get("timestamp", "").replace(":", "").replace("-", "")
    path = REPORTS_DIR / f"report_{version}_{ts}.json"
    _write_json(path, payload)
    return path


def save_evolution_summary(payload: dict) -> Path:
    """持久化一次自进化运行的完整摘要(逐轮轨迹/停止原因),供看板时间线回放。"""
    path = REPORTS_DIR / f"evolution_{payload['timestamp']}.json"
    _write_json(path, payload)
    return path


def list_evolutions() -> list[dict]:
    """列出全部自进化运行记录(按时间倒序)。"""
    out = []
    for p in sorted(REPORTS_DIR.glob("evolution_*.json"), reverse=True):
        payload = _read_json(p)
        out.append({
            "evolution_id": p.stem,
            "timestamp": payload.get("timestamp"),
            "evalset_id": payload.get("evalset_id"),
            "total_cases": payload.get("total_cases"),
            "baseline": payload.get("baseline"),
            "rounds": payload.get("rounds"),
            "best": payload.get("best"),
            "stop_reason": payload.get("stop_reason"),
            "iterations_used": payload.get("iterations_used"),
            "md_report": payload.get("md_report"),
        })
    return out


def load_evolution(evolution_id: str) -> dict:
    path = REPORTS_DIR / f"{_safe_name(evolution_id, '进化记录 ID')}.json"
    return _read_json(path)


def list_reports() -> list[dict]:
    """列出全部评测报告(按时间倒序),供看板与版本对比使用。"""
    out = []
    for p in sorted(REPORTS_DIR.glob("report_*.json"), reverse=True):
        payload = _read_json(p)
        out.append({
            "report_id": p.stem,
            "version": payload.get("version"),
            "evalset_id": payload.get("evalset_id"),
            "accuracy": payload.get("accuracy"),
            "passed_count": payload.get("passed_count"),
            "total": payload.get("total"),
            "timestamp": payload.get("timestamp"),
        })
    return out


def load_report(report_id: str) -> dict:
    path = REPORTS_DIR / f"{_safe_name(report_id, '报告 ID')}.json"
    return _read_json(path)
