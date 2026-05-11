"""候选评论状态机。CLAUDE.md §1 R4：默认 pending_review，没有"自动通过"路径。"""
from __future__ import annotations

from enum import Enum


class CandidateState(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED_FOR_HUMAN_USE = "approved_for_human_use"  # 仅供人类编辑参考使用
    REJECTED_RISK = "rejected_risk"
    REJECTED_OFFTOPIC = "rejected_offtopic"
    REJECTED_PLAGIARISM = "rejected_plagiarism"


# 允许的状态转移图
ALLOWED_TRANSITIONS = {
    CandidateState.DRAFT: {CandidateState.PENDING_REVIEW},
    CandidateState.PENDING_REVIEW: {
        CandidateState.APPROVED_FOR_HUMAN_USE,
        CandidateState.REJECTED_RISK,
        CandidateState.REJECTED_OFFTOPIC,
        CandidateState.REJECTED_PLAGIARISM,
    },
    # APPROVED_FOR_HUMAN_USE 是终态。这里不存在"系统自动发布"路径 —— 有意为之（红线 R3）。
    CandidateState.APPROVED_FOR_HUMAN_USE: set(),
    CandidateState.REJECTED_RISK: set(),
    CandidateState.REJECTED_OFFTOPIC: set(),
    CandidateState.REJECTED_PLAGIARISM: set(),
}


def can_transition(src: CandidateState, dst: CandidateState) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, set())
