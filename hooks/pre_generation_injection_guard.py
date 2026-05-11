"""Hook: pre_generation_injection_guard

触发点：pipeline 在调用 generator 之前。
作用：
  1) 检查 PostUnderstanding 是否被标记 brand_defamation（即 sanitize 阶段发现注入 markers）。
     若是 + 风险 high → 直接拒绝生成，pipeline 走"无候选 + 显式 reason"。
  2) 检查 references 字段里有没有意外混入的"原始评论原文"（CLAUDE.md R1）。

阻断策略（非可绕过）：
  - 若 understanding.risk.flagged_buckets 包含 'brand_defamation' 且 risk.overall_level == 'high'
    → 抛 HookBlocked。pipeline 会捕获后落 evidence 并返回空推荐。
  - 若 references 的 patterns 列表中任何 description 字段过长（> 240 字符），视作可能塞了原文 → 拒。

误报处理：
  - 长 description 误报：在 hooks.config.yaml 里把 max_description_chars 调高。
  - 政治/宗教共现误报：在 understanding.notes 里加 "appeal:..." 字符串后人工 review；
    Hook 不接受 LLM 自己附加的 appeal —— 必须人手填。
"""
from __future__ import annotations

from .registry import HookBlocked, register

MAX_PATTERN_DESCRIPTION_CHARS = 240


@register(
    name="pre_generation_injection_guard",
    event="before_generation",
    blocking=True,
    description=(
        "在生成前拦截两类风险：(a) 帖子注入嫌疑 + 高风险 → 拒绝生成； "
        "(b) reference patterns 里疑似混入了 Reddit 原文 → 拒绝生成。"
    ),
)
def guard(ctx: dict) -> None:
    understanding = ctx["understanding"]
    references = ctx["references"]

    # (a) 注入 + 高风险
    if (
        "brand_defamation" in understanding.risk.flagged_buckets
        and understanding.risk.overall_level == "high"
    ):
        raise HookBlocked(
            "pre_generation_injection_guard",
            reason="post text contains injection markers AND risk_level=high; refusing to generate.",
            payload={"flagged": understanding.risk.flagged_buckets},
        )

    # (b) pattern 描述过长 → 可能塞了原文
    for p in references.patterns:
        if len(p.description) > MAX_PATTERN_DESCRIPTION_CHARS:
            raise HookBlocked(
                "pre_generation_injection_guard",
                reason=(
                    f"reference pattern '{p.name}' description={len(p.description)} chars "
                    f"exceeds {MAX_PATTERN_DESCRIPTION_CHARS}; suspect raw-comment leakage."
                ),
                payload={"pattern": p.name, "len": len(p.description)},
            )
