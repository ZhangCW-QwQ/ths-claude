"""定义"神评论"风格谱。

每个风格自带：
- 解释（给人看的）
- 适用条件（给路由用的）
- 不该用的场景（给 risk 用的）
- 一段精简的 generation guideline（给 LLM 看的，**不放原始范文**）
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Style:
    name: str
    cn_name: str
    when_to_use: str
    when_not_to_use: str
    guideline: str  # 这段会被拼到 LLM prompt 里


STYLES: dict[str, Style] = {
    "spicy_take": Style(
        name="spicy_take",
        cn_name="引战型观点",
        when_to_use="帖子有明显观点对立、读者情绪已激活时",
        when_not_to_use="涉及种族/宗教/未成年人/医疗 → 直接走 sharp_summary",
        guideline=(
            "Write one short paragraph (≤2 sentences) that takes a contrarian-but-defensible "
            "stance. Avoid attacking individuals; attack the framing. Never use slurs."
        ),
    ),
    "sharp_summary": Style(
        name="sharp_summary",
        cn_name="一针见血型总结",
        when_to_use="任何场景，是 fallback；读者想要的是那句他们没说出口的话。",
        when_not_to_use="帖子完全无观点（纯求助/纯炫耀） — 改用 thought_question",
        guideline=(
            "One sentence. ≤25 chars (zh) or ≤15 words (en). Compress the post's hidden "
            "premise into a punchline. Do not insult."
        ),
    ),
    "witty_joke": Style(
        name="witty_joke",
        cn_name="抖机灵型玩笑",
        when_to_use="帖子语气轻松、笑点明显、风险等级 ≤ medium",
        when_not_to_use="严肃话题、悲剧、求助、医疗、政治+宗教共现",
        guideline=(
            "One witty line that piggybacks on a clear punchline in the post. Self-aware tone. "
            "Skip if the joke requires impersonating a real person."
        ),
    ),
    "thought_question": Style(
        name="thought_question",
        cn_name="发人深省型提问",
        when_to_use="高风险话题、严肃话题、求助、想引出二次讨论时",
        when_not_to_use="纯娱乐/纯炫耀（显得用力过猛）",
        guideline=(
            "One open-ended question that flips a hidden assumption in the post. "
            "Must invite a real answer, not a rhetorical gotcha."
        ),
    ),
}


def styles_for(direction_recommended: list[str], risk_level: str) -> list[Style]:
    """按方向推荐 + 风险等级筛风格。"""
    pool = [STYLES[s] for s in direction_recommended if s in STYLES]
    if not pool:
        pool = [STYLES["sharp_summary"], STYLES["thought_question"]]
    if risk_level in ("high", "do_not_engage"):
        # 高风险时砍掉 spicy / witty
        pool = [s for s in pool if s.name in ("sharp_summary", "thought_question")]
    return pool
