"""候选评论的多层风险校验。

层次（与 hooks/pre_publish_safety_gate.py 共享同一组规则）：

L1  显式词表  — slurs / political combos / medical advice
L2  相关度    — 与帖子主题 jaccard 太低 → off-topic
L3  抄袭粗筛  — 与任意检索到的参考评论 trigram > 0.4 → 拒
L4  自报风险  — generator 自评 backfire/offensive > 0.5 → 拒
L5  状态机    — 永远不允许"自动 approved 然后发布"

设计原则：每层独立、可单测、有明确失败原因。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..generation.generator import CommentCandidate
from ..retrieval.pattern_extractor import ReferenceAnalysis
from ..retrieval.reddit_client import RedditComment, RetrievalResult
from ..understanding.schema import PostUnderstanding
from ..utils.logger import log_event
from ..utils.relevance import topic_relevance, trigram_overlap
from .state_machine import CandidateState

_BLOCKLIST_DIR = Path(__file__).parent / "blocklists"


def _load_lines(name: str) -> list[str]:
    path = _BLOCKLIST_DIR / name
    if not path.exists():
        return []
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]


_SLURS = _load_lines("slurs.txt")
_POLITICAL_COMBOS = [tuple(ln.split("|")) for ln in _load_lines("political_combos.txt") if "|" in ln]
_MEDICAL = _load_lines("medical_advice.txt")


@dataclass
class ValidationResult:
    state: CandidateState
    reasons: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.state == CandidateState.APPROVED_FOR_HUMAN_USE


def validate(
    candidate: CommentCandidate,
    *,
    understanding: PostUnderstanding,
    references: ReferenceAnalysis | None = None,
    raw_reference_sources: list[RedditComment] | None = None,
) -> ValidationResult:
    reasons: list[str] = []
    metrics: dict = {}
    text = (candidate.text or "").strip()

    # L1: blocklists
    lower = text.lower()
    for s in _SLURS:
        if s.lower() in lower:
            reasons.append(f"L1.slur:{s}")
    for a, b in _POLITICAL_COMBOS:
        if a.lower() in lower and b.lower() in lower:
            reasons.append(f"L1.political_combo:{a}+{b}")
    for m in _MEDICAL:
        if m.lower() in lower:
            reasons.append(f"L1.medical:{m}")

    # L2: relevance
    post_text = (understanding.facts.raw_title + "\n" + understanding.facts.raw_body).strip()
    rel = topic_relevance(post_text, text)
    metrics["relevance"] = round(rel, 3)
    # mock-llm 限制下阈值放宽到 0.10；生产换 embedding 后应抬到 ≥0.5。
    # 阈值的取舍详见 docs/design.md §2 反证。
    if rel < 0.10:
        reasons.append(f"L2.relevance_low:{rel:.2f}")

    # L3: trigram plagiarism vs raw retrieved comments
    max_tri = 0.0
    if raw_reference_sources:
        for ref in raw_reference_sources:
            tri = trigram_overlap(text, ref.body)
            if tri > max_tri:
                max_tri = tri
    metrics["max_trigram_overlap"] = round(max_tri, 3)
    if max_tri >= 0.4:
        reasons.append(f"L3.plagiarism:{max_tri:.2f}")

    # L4: 自评风险阈值
    risks = candidate.self_risk_estimate
    metrics["self_offensive"] = risks.get("offensiveness", 0)
    metrics["self_misread"] = risks.get("misread", 0)
    metrics["self_backfire"] = risks.get("backfire", 0)
    if risks.get("offensiveness", 0) > 0.5:
        reasons.append("L4.self_offensive>0.5")
    if risks.get("backfire", 0) > 0.5:
        reasons.append("L4.self_backfire>0.5")

    # L5: 决定状态
    if any(r.startswith("L1") for r in reasons):
        state = CandidateState.REJECTED_RISK
    elif any(r.startswith("L4") for r in reasons):
        state = CandidateState.REJECTED_RISK
    elif any(r.startswith("L3") for r in reasons):
        state = CandidateState.REJECTED_PLAGIARISM
    elif any(r.startswith("L2") for r in reasons):
        state = CandidateState.REJECTED_OFFTOPIC
    else:
        state = CandidateState.APPROVED_FOR_HUMAN_USE

    log_event(
        "risk_validation",
        {
            "post_id": understanding.facts.post_id,
            "style": candidate.style,
            "state": state.value,
            "reasons": reasons,
            "metrics": metrics,
        },
    )
    return ValidationResult(state=state, reasons=reasons, metrics=metrics)


def pick_best(
    candidates_with_validation: list[tuple[CommentCandidate, ValidationResult]],
) -> tuple[CommentCandidate, ValidationResult] | None:
    """从通过校验的候选中按"低风险 + 高相关 + 风格优先级"挑一条最优。"""
    passed = [(c, v) for c, v in candidates_with_validation if v.passed]
    if not passed:
        return None

    # 简单评分：relevance - backfire - offensive，加风格权重
    style_weight = {
        "sharp_summary": 0.10,
        "thought_question": 0.08,
        "spicy_take": 0.0,
        "witty_joke": 0.05,
    }

    def score(item):
        c, v = item
        return (
            v.metrics.get("relevance", 0)
            - v.metrics.get("self_backfire", 0)
            - v.metrics.get("self_offensive", 0)
            + style_weight.get(c.style, 0)
        )

    return max(passed, key=score)
