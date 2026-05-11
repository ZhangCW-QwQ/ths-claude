#!/usr/bin/env python3
"""批量重跑 5 条示例并写到 examples/<id>.output.json。

用法：
    python scripts/run_all_examples.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("LLM_MODE", "mock")
os.environ.setdefault("REDDIT_MODE", "mock")
os.environ.setdefault("SESSION_ID", "examples-batch")

from src.pipeline import run_one  # noqa: E402

EXAMPLE_IDS = [
    "trump_israel_ainvest",
    "weibo_inject_attempt",
    "xhs_ed_advice_risk",
    "9gag_cat_meme",
    "zhihu_career_serious",
    # 扩展示例 — 共 8 条，覆盖更多形态
    "xhs_pretty_house_boast",
    "weibo_996_rant",
    "hn_ai_safety_announce",
    "xhs_food_multi_image",
    "weibo_brand_negative",
    "hn_layoff_discussion",
]


def main():
    out_dir = ROOT / "examples"
    out_dir.mkdir(exist_ok=True)
    for pid in EXAMPLE_IDS:
        result = run_one(pid)
        (out_dir / f"{pid}.output.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"wrote examples/{pid}.output.json — recommended={result.get('recommended') is not None}")


if __name__ == "__main__":
    main()
