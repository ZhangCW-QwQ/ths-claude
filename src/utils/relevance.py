"""相关性 / 重合度的 zero-dep 实现，供 risk_validator 用。

为什么不上 embedding：
- 本仓库 CI 必须无外网无依赖跑通
- 神评论的"相关性"在 token-level 重合就能拦掉 80% 的离题候选
- 真生产换成 embedding 只需要替换这两个函数的实现

把"算法"留在这里、把"接口"暴露给 risk_validator —— 后续替换零侵入。
"""
from __future__ import annotations

import re
from collections import Counter

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[一-鿿]{2,4}|[一-鿿]")


def _tokens(text: str) -> list[str]:
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def jaccard(a: str, b: str) -> float:
    sa, sb = set(_tokens(a)), set(_tokens(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def trigram_overlap(a: str, b: str) -> float:
    """char trigram overlap，用于"抄袭"风险粗筛。"""

    def grams(s: str) -> Counter:
        s = re.sub(r"\s+", " ", s.strip().lower())
        if len(s) < 3:
            return Counter()
        return Counter(s[i : i + 3] for i in range(len(s) - 2))

    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    inter = sum((ga & gb).values())
    union = sum((ga | gb).values())
    return inter / union if union else 0.0


def topic_relevance(post_text: str, comment_text: str) -> float:
    """估算评论与帖子的相关度 ∈ [0, 1]。

    简化模型：jaccard(post_keywords, comment_tokens) + 长度惩罚
    """
    post_tokens = [t for t in _tokens(post_text) if len(t) > 1]
    if not post_tokens:
        return 0.0
    keywords = set(t for t, _ in Counter(post_tokens).most_common(20))
    comment_tokens = set(_tokens(comment_text))
    if not comment_tokens:
        return 0.0
    overlap = len(keywords & comment_tokens) / len(keywords)
    # 评论太短的稳定性差，给一个 mild 惩罚
    length_penalty = 1.0 if len(comment_text) >= 8 else 0.6
    return min(1.0, overlap * length_penalty * 1.2)
