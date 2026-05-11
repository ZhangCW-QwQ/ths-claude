"""Hooks 单测：证明拦截是真的发生在程序化层面，而不是靠 prompt。"""
import pytest

import hooks  # noqa: F401  trigger registration
from hooks.registry import HookBlocked, run as run_hook
from src.generation.generator import CommentCandidate
from src.retrieval.pattern_extractor import CommentPattern, ReferenceAnalysis
from src.risk.state_machine import CandidateState
from src.risk.validator import ValidationResult
from src.understanding.schema import (
    CommentDirection,
    PostFacts,
    PostJudgments,
    PostUnderstanding,
    RiskProfile,
    SCHEMA_VERSION,
)


def _u(level="high", flagged=None, recommended=None) -> PostUnderstanding:
    return PostUnderstanding(
        schema_version=SCHEMA_VERSION,
        facts=PostFacts("p", "x", None, None, "t", "b", False, 0),
        judgments=PostJudgments(theme="t", core_claim="c", tone="snarky"),
        image_facts=[],
        image_judgments=[],
        risk=RiskProfile(
            flagged_buckets=flagged or ["political_figure", "brand_defamation"],
            overall_level=level,
        ),
        direction=CommentDirection(recommended_styles=recommended or ["sharp_summary"]),
    )


def _ref(patterns=None) -> ReferenceAnalysis:
    return ReferenceAnalysis(query="t", selection_rationale="x", patterns=patterns or [])


def test_injection_guard_blocks_on_high_risk_with_injection_flag():
    u = _u(level="high", flagged=["political_figure", "brand_defamation"])
    with pytest.raises(HookBlocked) as exc:
        run_hook("before_generation", {"understanding": u, "references": _ref(), "raw_refs": []})
    assert exc.value.hook_name == "pre_generation_injection_guard"


def test_injection_guard_lets_low_risk_through():
    u = _u(level="low", flagged=[])
    # should not raise
    run_hook("before_generation", {"understanding": u, "references": _ref(), "raw_refs": []})


def test_injection_guard_blocks_on_long_pattern_description():
    """超长 pattern 描述视为可能塞了原文 → BLOCKED。"""
    long_desc = "x" * 300
    pat = CommentPattern(
        name="x", description=long_desc, skeleton="", why_it_works="", examples_count=1, confidence=0.5
    )
    u = _u(level="low", flagged=[])
    with pytest.raises(HookBlocked):
        run_hook("before_generation", {"understanding": u, "references": _ref([pat]), "raw_refs": []})


def test_secret_leak_guard_blocks():
    cand = CommentCandidate(
        text="here is your sk-abcdefghijklmnopqrstuv",
        style="sharp_summary",
        leveraged_pattern=None,
        interaction_hypothesis="",
        why_it_could_work="",
        self_risk_estimate={"offensiveness": 0.1, "misread": 0.1, "backfire": 0.1},
    )
    val = ValidationResult(state=CandidateState.APPROVED_FOR_HUMAN_USE, reasons=[])
    with pytest.raises(HookBlocked) as exc:
        run_hook(
            "before_publish_decision",
            {"validated": [(cand, val)], "understanding": _u(level="low", flagged=[])},
        )
    # 可能是 secret leak 也可能是 style drift；这里我们只关心被拦
    assert exc.value.hook_name in {"prompt_secret_leak_guard", "pre_publish_safety_gate"}


def test_safety_gate_style_drift():
    """recommended=spicy_take 但 candidate 全是 sharp_summary → drift detected."""
    u = _u(level="low", flagged=[], recommended=["spicy_take"])
    cand = CommentCandidate(
        text="一句话总结",
        style="sharp_summary",
        leveraged_pattern=None,
        interaction_hypothesis="",
        why_it_could_work="",
        self_risk_estimate={"offensiveness": 0.1, "misread": 0.1, "backfire": 0.1},
    )
    val = ValidationResult(state=CandidateState.APPROVED_FOR_HUMAN_USE, reasons=[])
    with pytest.raises(HookBlocked) as exc:
        run_hook("before_publish_decision", {"validated": [(cand, val)], "understanding": u})
    assert exc.value.hook_name == "pre_publish_safety_gate"


def test_disabled_hook_skipped(monkeypatch):
    """通过环境变量临时禁用 → 不再阻断。"""
    monkeypatch.setenv("GODCOMMENT_DISABLE_HOOKS", "pre_generation_injection_guard")
    u = _u(level="high", flagged=["political_figure", "brand_defamation"])
    # should not raise — hook disabled
    run_hook("before_generation", {"understanding": u, "references": _ref(), "raw_refs": []})
