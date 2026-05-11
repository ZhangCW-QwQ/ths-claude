"""pytest 公共 fixture & path 设置。"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LLM_MODE", "mock")
os.environ.setdefault("REDDIT_MODE", "mock")
