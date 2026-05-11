"""Hook: pre_publish_safety_gate

触发点：候选评论生成 + risk_validator 判定后，挑"推荐"前。

这一关比 risk_validator 多一层"对照阅读"：
- risk_validator 是按候选的"自评 + 文本特征"判
- 这里再补一道：候选**整体**是否覆盖了 understanding.direction.recommended_styles
  至少一个？如果系统全部走偏（比如 understanding 推荐 sharp_summary 但全成了 spicy_take）
  → 这是**信号**：generator 可能被 prompt-injection 偷换风格。

并强制：任何路径都不能把 state 跳过 PENDING_REVIEW 直接到"published"（红线 R3）。

非阻断：仅当全部候选 fail 且 enforce 模式下才拒绝；其他情况只 warn。
"""
from __future__ import annotations

from src.risk.state_machine import CandidateState

from .registry import HookBlocked, register


@register(
    name="pre_publish_safety_gate",
    event="before_publish_decision",
    blocking=True,
    description=(
        "推荐前安全门：禁止任何状态绕过 PENDING_REVIEW 上推；检查风格是否被偷换；"
        "若全部候选都走偏离推荐风格 → 抛 BLOCKED，pipeline 必须返回空推荐 + 提示人审。"
    ),
)
def gate(ctx: dict) -> None:
    validated = ctx["validated"]
    understanding = ctx["understanding"]

    if not validated:
        return

    # 1) 任何 state 不允许是 published / approved 之外的伪状态
    bad_states = []
    for c, v in validated:
        if v.state not in {
            CandidateState.APPROVED_FOR_HUMAN_USE,
            CandidateState.REJECTED_RISK,
            CandidateState.REJECTED_OFFTOPIC,
            CandidateState.REJECTED_PLAGIARISM,
        }:
            bad_states.append((c.style, v.state))
    if bad_states:
        raise HookBlocked(
            "pre_publish_safety_gate",
            reason=f"unexpected candidate state(s): {bad_states}",
            payload={"bad_states": [(s, st.value) for s, st in bad_states]},
        )

    # 2) 风格漂移检测
    recommended = set(understanding.direction.recommended_styles)
    actual = {c.style for c, _ in validated}
    if recommended and not (recommended & actual):
        raise HookBlocked(
            "pre_publish_safety_gate",
            reason=(
                f"style drift: recommended={sorted(recommended)} but candidates produced "
                f"only {sorted(actual)}. Possible prompt-injection mid-pipeline."
            ),
            payload={"recommended": sorted(recommended), "actual": sorted(actual)},
        )
