"""所有 LLM 调用 / 关键决策都落 evidence/sessions/。

CLAUDE.md §4 决策原则 #2：可复盘 > 可隐蔽。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "evidence" / "sessions"


def _ensure_dir() -> Path:
    _EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    return _EVIDENCE_DIR


def log_event(kind: str, payload: dict[str, Any], *, session_id: str | None = None) -> Path:
    """落一行 JSON。kind 例: llm_call / hook_block / risk_reject / pipeline_step。"""
    sid = session_id or os.environ.get("SESSION_ID") or time.strftime("%Y%m%d-%H%M%S")
    path = _ensure_dir() / f"{sid}.jsonl"
    record = {"ts": time.time(), "kind": kind, **payload}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
