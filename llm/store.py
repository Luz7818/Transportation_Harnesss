"""LLM 持久化设施:响应缓存、调用审计日志、草稿存储。

三个目录都是运行期产物(已列入 .gitignore):
- llm_cache/     响应缓存,按「模型+用途+提示词」哈希存取,同输入同输出 → 评测可复现、成本可控;
- llm_runs.jsonl 调用审计日志(追加写):时间/用途/模型/耗时/token/缓存命中,LLM 行为全程可追溯;
- drafts/        LLM 草稿(坏例建议),pending → 人工确认成为正式 replaycase / discarded 丢弃。
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime
from pathlib import Path

from harness import storage

DRAFTS_DIR = storage.PROJECT_ROOT / "drafts"
CACHE_DIR = storage.PROJECT_ROOT / "llm_cache"
JOURNAL_FILE = storage.PROJECT_ROOT / "llm_runs.jsonl"

_LOCK = threading.Lock()
_UNSAFE = re.compile(r"[^A-Za-z0-9_\-\u4e00-\u9fff]")


# ---------- 响应缓存 ----------

def cache_key(model: str, purpose: str, system: str, user: str) -> str:
    raw = f"{model}|{purpose}|{system}|{user}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def cache_get(key: str) -> dict | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def cache_put(key: str, data: dict) -> None:
    with _LOCK:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_DIR / f"{key}.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CACHE_DIR / f"{key}.json")


def cache_count() -> int:
    return len(list(CACHE_DIR.glob("*.json"))) if CACHE_DIR.exists() else 0


# ---------- 审计日志 ----------

def journal_append(purpose: str, model: str, elapsed_ms: float,
                   usage: dict, cache_hit: bool) -> None:
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "purpose": purpose, "model": model,
        "elapsed_ms": round(elapsed_ms, 1),
        "cache_hit": cache_hit, "usage": usage,
    }
    with _LOCK:
        JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def journal_tail(n: int = 5) -> list[dict]:
    if not JOURNAL_FILE.exists():
        return []
    lines = JOURNAL_FILE.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ---------- 草稿存储 ----------

def _draft_path(draft_id: str) -> Path:
    return DRAFTS_DIR / f"{draft_id}.json"


def next_draft_id() -> str:
    numbers = [int(m.group(1)) for p in DRAFTS_DIR.glob("draft-*.json")
               if (m := re.fullmatch(r"draft-(\d+)", p.stem))]
    return f"draft-{max(numbers, default=0) + 1:04d}"


def save_draft(draft: dict) -> Path:
    with _LOCK:
        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        path = _draft_path(draft["draft_id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    return path


def load_draft(draft_id: str) -> dict | None:
    path = _draft_path(_UNSAFE.sub("_", str(draft_id)))
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_drafts() -> list[dict]:
    if not DRAFTS_DIR.exists():
        return []
    out = []
    for p in sorted(DRAFTS_DIR.glob("draft-*.json"), reverse=True):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def delete_draft(draft_id: str) -> bool:
    path = _draft_path(_UNSAFE.sub("_", str(draft_id)))
    if not path.exists():
        return False
    path.unlink()
    return True
