"""验证 risk_validator 的 5 层。"""
import pytest

from src.generation.generator import CommentCandidate
from src.retrieval.reddit_client import RedditComment
from src.risk.state_machine import CandidateState
from src.risk.validator import validate
from src.understanding.schema import (
    CommentDirection,
    PostFacts,
    PostJudgments,
    PostUnderstanding,
    RiskProfile,
    SCHEMA_VERSION,
)


def _u(post_text: str = "Trump Israel great ally Hamas hostage release") -> PostUnderstanding:
    return PostUnderstanding(
        schema_version=SCHEMA_VERSION,
        facts=PostFacts(
            platform="news",
            post_id="t1",
            url=None,
            posted_at=None,
            raw_title=post_text,
            raw_body="",
            has_image=False,
            image_count=0,
        ),
        judgments=PostJudgments(theme="Trump", core_claim="", tone="snarky", confidence=0.7),
        image_facts=[],
        image_judgments=[],
        risk=RiskProfile(),
        direction=CommentDirection(recommended_styles=["sharp_summary"]),
    )


def _c(text: str, **kwargs) -> CommentCandidate:
    return CommentCandidate(
        text=text,
        style=kwargs.get("style", "sharp_summary"),
        leveraged_pattern=None,
        interaction_hypothesis="",
        why_it_could_work="",
        self_risk_estimate={"offensiveness": 0.1, "misread": 0.1, "backfire": 0.1},
    )


def test_l1_political_combo_blocks():
    c = _c("trump treason confirmed")  # 命中 trump|treason
    res = validate(c, understanding=_u())
    assert res.state == CandidateState.REJECTED_RISK
    assert any("political_combo" in r for r in res.reasons)


def test_l1_medical_advice_blocks():
    c = _c("不要打疫苗，多喝水就好。")
    res = validate(c, understanding=_u("vaccine debate ongoing"))
    assert res.state == CandidateState.REJECTED_RISK
    assert any("medical" in r for r in res.reasons)


def test_l2_offtopic_blocks():
    c = _c("我刚刚买了一只柯基")
    res = validate(c, understanding=_u("Trump Israel ally release hostages"))
    assert res.state == CandidateState.REJECTED_OFFTOPIC


def test_l3_plagiarism_blocks():
    c = _c("Calling someone a great ally is the cheapest foreign policy in the world.")
    refs = [
        RedditComment(
            subreddit="x",
            thread_title="t",
            thread_url="",
            body="Calling someone a 'great ally' is the cheapest foreign policy in the world.",
            score=10,
            num_replies=1,
            created_at="",
            permalink="",
        )
    ]
    res = validate(c, understanding=_u(), raw_reference_sources=refs)
    assert res.state == CandidateState.REJECTED_PLAGIARISM
    assert res.metrics["max_trigram_overlap"] >= 0.4


def test_l4_self_offensive_blocks():
    cand = _c("you're stupid trash and idiotic")  # contains 'stupid' & 'idiot' & 'trash'
    res = validate(cand, understanding=_u())
    # offensiveness self-bumps to 0.7 in generator._self_risk; but here we set manually
    cand.self_risk_estimate = {"offensiveness": 0.7, "misread": 0.1, "backfire": 0.1}
    res = validate(cand, understanding=_u())
    assert res.state == CandidateState.REJECTED_RISK


def test_pass_through_on_clean_relevant_short():
    c = _c("Trump Israel — words are the cheapest foreign policy.")
    res = validate(c, understanding=_u())
    # 可能 L2 边缘但不应触红线 L1/L4
    assert not any(r.startswith("L1") or r.startswith("L4") for r in res.reasons)
