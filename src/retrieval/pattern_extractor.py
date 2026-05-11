"""把检索到的高互动评论 → 抽出"套路"，而不是把原文塞回 prompt。

为什么这件事至关重要（CLAUDE.md §1 R1）：
- 把别人评论的原文喂给 LLM，模型会有强烈的"复述偏好"，最终输出常常是改写而非原创。
- 而且原文受版权保护，复述风险高于创作风险。

我们的做法：
1. 对评论分类（讽刺/反转/提问/共情/数据型/类比型 …）
2. 抽出"句式骨架"（去掉具体名词，留模式）
3. 写一段"模式说明"给生成模块看，**不**把原文塞进 prompt。
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from ..utils.llm_client import LLM, get_llm
from ..utils.logger import log_event
from .reddit_client import RedditComment, RetrievalResult


@dataclass
class CommentPattern:
    name: str           # e.g. "punchy_one_liner"
    description: str    # 自然语言说明
    skeleton: str       # 去具体词的句式骨架 (模板化)
    why_it_works: str   # 一句话说明为什么有效
    examples_count: int  # 抽自多少条样本（不附原文）
    confidence: float


@dataclass
class ReferenceAnalysis:
    query: str
    selection_rationale: str
    patterns: list[CommentPattern] = field(default_factory=list)
    sample_count: int = 0
    confidence: str = "offline"

    def to_dict(self) -> dict:
        return asdict(self)


# 预定义的 pattern 探测规则（廉价 baseline，生产可换 LLM 抽取）
_PATTERNS_RULES = [
    ("punchy_one_liner", lambda c: len(c.body) <= 60 and c.reply_per_upvote > 0.05,
     "极简一句话总结，下面接力讨论",
     "<short, punchy summary>",
     "代言群众情绪，门槛低、转发欲望高"),
    ("rhetorical_question", lambda c: "?" in c.body or "？" in c.body,
     "提问式评论，把判断让给读者",
     "<setup statement> ... <question that flips the framing>",
     "提问比断言更安全，且引导回复"),
    ("contrast_setup", lambda c: re.search(r"(but|but actually|其实|然而)", c.body, re.I),
     "先承认对方再反转",
     "<concede X> ... <but flip to Y>",
     "反转触发认知失调，激发回复欲"),
    ("data_drop", lambda c: bool(re.search(r"\d{2,}", c.body)),
     "丢出一个具体数字制造可信度",
     "<concrete number> + <implication>",
     "数字让评论不像情绪发泄、更像内行"),
    ("self_deprecating", lambda c: re.search(r"(I am|i'm|me too|same here|我也|我就是)", c.body, re.I),
     "自嘲共情型",
     "<self-include statement> ... <relatable pain>",
     "把读者拉进来，比单纯的判断更有粘性"),
]


def extract_patterns(result: RetrievalResult, *, llm: LLM | None = None) -> ReferenceAnalysis:
    if not result.sources:
        return ReferenceAnalysis(
            query=result.query,
            selection_rationale="no sources retrieved; pipeline downgraded to style heuristics.",
            confidence=result.confidence,
        )

    # 第一步：基于 reply_per_upvote 的"互动密度"筛选，再叠加多样性
    ranked = sorted(result.sources, key=lambda c: c.reply_per_upvote, reverse=True)
    selected = _diversify(ranked, k=min(6, len(ranked)))

    rationale = (
        f"从 {len(result.sources)} 条里筛 {len(selected)} 条："
        " 1) 排除纯 upvote-bait（高 score 但低 reply 的鼓掌型）"
        " 2) 按 reply/upvote 排序选互动密度最高的 top-K"
        " 3) 通过 subreddit + 长度做多样性兜底，避免同套路"
    )

    patterns: dict[str, CommentPattern] = {}
    for c in selected:
        for name, predicate, desc, skeleton, why in _PATTERNS_RULES:
            if predicate(c):
                p = patterns.get(name)
                if p is None:
                    patterns[name] = CommentPattern(
                        name=name,
                        description=desc,
                        skeleton=skeleton,
                        why_it_works=why,
                        examples_count=1,
                        confidence=0.5,
                    )
                else:
                    p.examples_count += 1
                    p.confidence = min(0.95, p.confidence + 0.1)

    log_event(
        "pattern_extracted",
        {"query": result.query, "selected_n": len(selected), "patterns": list(patterns.keys())},
    )

    return ReferenceAnalysis(
        query=result.query,
        selection_rationale=rationale,
        patterns=list(patterns.values()),
        sample_count=len(selected),
        confidence=result.confidence,
    )


def _diversify(comments: list[RedditComment], k: int) -> list[RedditComment]:
    """简单去重 + subreddit 分散。"""
    out: list[RedditComment] = []
    seen_subs: dict[str, int] = {}
    for c in comments:
        if seen_subs.get(c.subreddit, 0) >= 2:
            continue
        out.append(c)
        seen_subs[c.subreddit] = seen_subs.get(c.subreddit, 0) + 1
        if len(out) >= k:
            break
    return out
