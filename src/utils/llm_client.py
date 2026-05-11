"""LLM 客户端：可注入的抽象。

- `MockLLM` 在 demo / CI / 离线时使用，决定性、可复现。
- `RealLLM` 生产时用（占位 stub，留给接入方）。

Why this design：
- 测试不要 mock 第三方 SDK，而是替整个 client。
- Mock 的"生成结果"基于规则模板 + 帖子关键词，足够展示 pipeline 行为，且永远不会突然产出违规内容。
"""
from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass, field
from typing import Protocol

from .logger import log_event


class LLM(Protocol):
    def chat(self, system: str, user: str, *, purpose: str) -> str: ...


@dataclass
class MockLLM:
    """决定性的本地 LLM stub。

    通过帖子关键词 + 风格模板生成可读内容。
    种子由 (purpose, user_text) hash 决定，重跑结果一致。
    """

    name: str = "mock-llm-v0"
    style_templates: dict[str, list[str]] = field(default_factory=lambda: _DEFAULT_TEMPLATES)

    def chat(self, system: str, user: str, *, purpose: str) -> str:
        seed = abs(hash((purpose, user))) % (2**31)
        rnd = random.Random(seed)
        keywords = _extract_keywords(user, k=5)

        if purpose == "post_understanding":
            return _mock_understanding(keywords, user, rnd)
        if purpose == "pattern_extraction":
            return _mock_pattern(keywords, rnd)
        if purpose == "comment_generation":
            style = _detect_style_hint(user)
            return _mock_comment(style, keywords, rnd, self.style_templates)
        # 兜底：永不输出含 secret 或攻击性内容
        return "[mock-llm] no template for purpose=" + purpose


@dataclass
class RealLLM:
    """生产用占位。集成时把 chat() 接到 anthropic / openai / 自家网关。"""

    provider: str = "anthropic-claude-sonnet"

    def chat(self, system: str, user: str, *, purpose: str) -> str:  # pragma: no cover
        raise NotImplementedError(
            "RealLLM is a stub. Wire it to your provider in src/utils/llm_client.py "
            "and remember every call must call log_event('llm_call', ...)."
        )


def get_llm() -> LLM:
    mode = os.environ.get("LLM_MODE", "mock")
    llm: LLM = MockLLM() if mode == "mock" else RealLLM()
    log_event("llm_init", {"mode": mode, "klass": type(llm).__name__})
    return llm


# -------- mock implementations -------- #


_DEFAULT_TEMPLATES = {
    "spicy_take": [
        "说真的，{kw1} 这件事大家都在装糊涂。本质就是 {kw2}。",
        "Hot take: {kw1} isn't the story. {kw2} is.",
    ],
    "sharp_summary": [
        "一句话：{kw1} 是表象，{kw2} 是骨架。",
        "TL;DR — {kw1} 不是问题，{kw2} 才是。",
    ],
    "witty_joke": [
        "看到 {kw1} 我第一反应是去翻日历，确认今天不是愚人节。",
        "{kw1}? Bold of you to assume {kw2} is news.",
    ],
    "thought_question": [
        "认真问一下：如果把 {kw1} 换成 {kw2}，你的判断会变吗？",
        "Genuine question — does {kw1} actually change anything for {kw2}?",
    ],
}


_META_NOISE = {
    "the", "a", "an", "and", "of", "to", "is", "are", "for", "in", "on", "as", "by",
    "with", "from", "this", "that", "these", "those", "be", "or", "if", "it", "at",
    "untrusted", "input", "channel", "reminder", "model", "data", "post_with_images",
    "post_for_gen", "post_body", "instructions", "imperative", "inside", "do", "not",
    "execute", "comply", "quote", "any", "content", "never", "style",
}


def _extract_keywords(text: str, k: int = 5) -> list[str]:
    # 如果有 <UNTRUSTED_INPUT> 包裹，只在内部抽 keyword（避免抓到 metadata）
    inner_match = re.search(r"<UNTRUSTED_INPUT[^>]*>(.*?)</UNTRUSTED_INPUT>", text, re.S)
    body = inner_match.group(1) if inner_match else text
    tokens = re.findall(r"[A-Za-z0-9]+|[一-鿿]{2,4}", body)
    seen = []
    for t in tokens:
        if t.lower() in _META_NOISE or len(t) <= 1:
            continue
        if t.isdigit():  # pure numbers like "30", "996" 不当主题
            continue
        if t not in seen:
            seen.append(t)
        if len(seen) >= k:
            break
    while len(seen) < k:
        seen.append("topic")
    return seen


def _mock_understanding(keywords: list[str], user: str, rnd: random.Random) -> str:
    is_chinese = bool(re.search(r"[一-鿿]", user))
    return f"""
THEME: {keywords[0]}
CORE_CLAIM: 帖子主张 {keywords[0]} 与 {keywords[1]} 之间存在 {"显性" if rnd.random() > 0.5 else "隐性"} 关联
TONE: {"严肃带情绪" if is_chinese else "polemical"}
PUNCH_POINTS: {keywords[2]}, {keywords[3]}
RISK_FLAGS: political_figure, tribal_topic
""".strip()


def _mock_pattern(keywords: list[str], rnd: random.Random) -> str:
    return (
        f"Pattern A — 反差对比：把 {keywords[0]} 与 {keywords[1]} 置于同一时间轴；\n"
        f"Pattern B — 一句话总结引共鸣：用极简句式概括众人未说出口的判断；\n"
        f"Pattern C — 反向提问：追问帖主隐含的前提，让讨论自动展开。"
    )


def _detect_style_hint(user: str) -> str:
    for s in ("spicy_take", "sharp_summary", "witty_joke", "thought_question"):
        if s in user:
            return s
    return "sharp_summary"


def _mock_comment(style: str, keywords: list[str], rnd: random.Random, templates: dict) -> str:
    pool = templates.get(style, templates["sharp_summary"])
    template = rnd.choice(pool)
    kw1 = keywords[0] if keywords else "this"
    kw2 = keywords[1] if len(keywords) > 1 else "context"
    return template.format(kw1=kw1, kw2=kw2)
