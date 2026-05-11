"""Hook: prompt_secret_leak_guard

触发点：generator 输出每条候选时（同时也在 before_publish_decision 上巡检一次）。

作用：扫候选评论文本里有没有疑似 API key / token / 私钥。
触发后：直接抛 HookBlocked，pipeline 把该候选标 REJECTED_RISK 并落 evidence。

为什么必须在 Hook 而不在 Prompt：
- Prompt 里说"别泄露 secret"是软约束，模型可被各种社工绕过
- 程序化扫描是确定性的、可单测、可审计

误报处理：
- 用户故意写"sk-fake" 之类的演示串 → 在 hooks.config.yaml 里维护 allow-list 正则
"""
from __future__ import annotations

from src.utils.sanitize import looks_like_secret

from .registry import HookBlocked, register


@register(
    name="prompt_secret_leak_guard",
    event="before_publish_decision",
    blocking=True,
    description="扫候选文本里的疑似 secret；命中即抛 BLOCKED。",
)
def guard(ctx: dict) -> None:
    validated = ctx["validated"]
    leaks = []
    for c, _v in validated:
        if looks_like_secret(c.text):
            leaks.append((c.style, c.text[:80]))
    if leaks:
        raise HookBlocked(
            "prompt_secret_leak_guard",
            reason=f"candidate text contains pattern resembling a secret: {len(leaks)} match(es)",
            payload={"matches": [{"style": s, "preview": p} for s, p in leaks]},
        )
