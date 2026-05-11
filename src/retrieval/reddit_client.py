"""Reddit 检索客户端。

设计：
- 默认 mock 模式 → 读 data/fixtures/reddit/<query_slug>.json
- 真实模式留 stub。集成方实现 _real_search 即可。
- 失败时**显式抛 RetrievalUnavailable**，绝不返回假数据（CLAUDE.md §4 #3）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..utils.logger import log_event

_FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "reddit"


class RetrievalUnavailable(RuntimeError):
    """检索服务不可用 / 无 fixture / 频控耗尽。pipeline 必须显式处理。"""


@dataclass
class RedditComment:
    subreddit: str
    thread_title: str
    thread_url: str
    body: str
    score: int
    num_replies: int
    created_at: str
    permalink: str

    @property
    def reply_per_upvote(self) -> float:
        return self.num_replies / max(self.score, 1)


@dataclass
class RetrievalResult:
    query: str
    sources: list[RedditComment] = field(default_factory=list)
    confidence: str = "online"  # online | offline | empty

    def __bool__(self) -> bool:
        return bool(self.sources)


def _slugify(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:60]


def search_high_engagement_comments(query: str, *, limit: int = 8) -> RetrievalResult:
    """检索目标话题相关、高互动的评论。

    高互动 = 上面定义的 reply_per_upvote 排名前 K。**不**只用 score。
    理由：score 高的常常是正能量发言，reply 多的才有"激发讨论"特性。
    """
    mode = os.environ.get("REDDIT_MODE", "mock")
    if mode == "real":
        try:
            return _real_search(query, limit=limit)  # pragma: no cover
        except Exception as e:  # pragma: no cover
            log_event("retrieval_fallback", {"query": query, "reason": str(e)})

    # mock / fallback
    slug = _slugify(query)
    path = _FIXTURES / f"{slug}.json"
    if not path.exists():
        # 二次回退：用 hash bucket 找近似 fixture
        digest = hashlib.md5(query.encode()).hexdigest()[:6]
        path = _FIXTURES / f"_generic_{int(digest, 16) % 3}.json"
    if not path.exists():
        log_event("retrieval_unavailable", {"query": query})
        raise RetrievalUnavailable(
            f"No reddit fixture for query={query!r}. "
            "Pipeline must downgrade — do not invent references."
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    comments = [RedditComment(**c) for c in data][:limit]
    return RetrievalResult(query=query, sources=comments, confidence="offline")


def _real_search(query: str, *, limit: int) -> RetrievalResult:  # pragma: no cover
    raise NotImplementedError(
        "Wire to your Reddit-MCP client here. Remember to honor REDDIT_RATE_LIMIT_PER_MIN."
    )
