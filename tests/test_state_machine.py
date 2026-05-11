"""验证：状态机里没有"自动 published"路径（CLAUDE.md R3）。"""
from src.risk.state_machine import ALLOWED_TRANSITIONS, CandidateState, can_transition


def test_no_state_named_published():
    """系统的状态枚举里根本没有 'published' —— 这是设计选择。"""
    assert "published" not in [s.value for s in CandidateState]


def test_approved_is_terminal():
    """APPROVED_FOR_HUMAN_USE 是终态，不可再转 —— 没有'转去发布'的路径。"""
    assert ALLOWED_TRANSITIONS[CandidateState.APPROVED_FOR_HUMAN_USE] == set()


def test_rejected_states_are_terminal():
    for s in (
        CandidateState.REJECTED_RISK,
        CandidateState.REJECTED_OFFTOPIC,
        CandidateState.REJECTED_PLAGIARISM,
    ):
        assert ALLOWED_TRANSITIONS[s] == set()


def test_only_pending_goes_to_terminal():
    """从 DRAFT 只能去 PENDING_REVIEW；从 PENDING_REVIEW 才能去任一终态。"""
    assert ALLOWED_TRANSITIONS[CandidateState.DRAFT] == {CandidateState.PENDING_REVIEW}
    assert can_transition(CandidateState.PENDING_REVIEW, CandidateState.APPROVED_FOR_HUMAN_USE)
    assert not can_transition(CandidateState.DRAFT, CandidateState.APPROVED_FOR_HUMAN_USE)
