"""PostUnderstanding schema —— 帖子结构化理解的契约。

设计思路（详见 docs/schema.md）：

1. **三层分离**：facts（可验证事实）/ judgments（模型判断）/ derived（综合推断）。
   - 下游用 confidence 区别对待，避免"模型猜测被当成事实喂回去"。
2. **图片是一等公民**：image 字段独立结构化，单独可降级。
3. **风险与互动方向并列**：risk 不是单 bool，而是分项（offensive_topic / political_figure /
   minors_involvement / brand_defamation_risk），方便 Hook 精确否决而不是一刀切。
4. **schema 自带版本号**：迁移友好，evidence 日志能回放。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional

SCHEMA_VERSION = "post_understanding/2026-05-10"

EmotionTone = Literal[
    "neutral", "humorous", "snarky", "angry", "wholesome",
    "boastful", "vulnerable", "polemical", "informative",
]

RiskBucket = Literal[
    "political_figure", "religion", "race_ethnicity", "gender_sexuality",
    "minors_involvement", "brand_defamation", "medical_advice",
    "violence_glorification", "self_harm",
]


@dataclass
class ImageFacts:
    """对每张图片的"事实层" —— 可被外部 OCR / 视觉模型独立验证。"""

    status: Literal["ok", "unavailable", "blocked_nsfw"]
    ocr_text: str = ""
    objects: list[str] = field(default_factory=list)
    scene_caption: str = ""
    estimated_locale: Optional[str] = None
    notes: str = ""


@dataclass
class ImageJudgments:
    """对图片的"模型判断层" —— 必须带 confidence。"""

    sentiment: EmotionTone = "neutral"
    is_meme: bool = False
    likely_punchline: Optional[str] = None
    confidence: float = 0.0  # 0..1


@dataclass
class PostFacts:
    platform: str
    post_id: str
    url: Optional[str]
    posted_at: Optional[str]
    raw_title: str
    raw_body: str
    has_image: bool
    image_count: int
    engagement_metrics: dict = field(default_factory=dict)


@dataclass
class PostJudgments:
    theme: str
    core_claim: str
    tone: EmotionTone
    punch_points: list[str] = field(default_factory=list)
    salt_points: list[str] = field(default_factory=list)        # 槽点
    contrast_points: list[str] = field(default_factory=list)    # 反差点
    why_engaging_hypothesis: str = ""
    confidence: float = 0.0


@dataclass
class RiskProfile:
    flagged_buckets: list[RiskBucket] = field(default_factory=list)
    sensitive_entities: list[str] = field(default_factory=list)  # 人名/品牌/机构
    overall_level: Literal["low", "medium", "high", "do_not_engage"] = "low"
    rationale: str = ""


@dataclass
class CommentDirection:
    recommended_styles: list[str] = field(default_factory=list)  # 见 generation.styles
    avoid_styles: list[str] = field(default_factory=list)
    interaction_levers: list[str] = field(default_factory=list)  # 提问/反差/共情/槽点放大


@dataclass
class PostUnderstanding:
    schema_version: str
    facts: PostFacts
    judgments: PostJudgments
    image_facts: list[ImageFacts]
    image_judgments: list[ImageJudgments]
    risk: RiskProfile
    direction: CommentDirection
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def empty(cls, post_facts: PostFacts) -> "PostUnderstanding":
        return cls(
            schema_version=SCHEMA_VERSION,
            facts=post_facts,
            judgments=PostJudgments(theme="", core_claim="", tone="neutral"),
            image_facts=[],
            image_judgments=[],
            risk=RiskProfile(),
            direction=CommentDirection(),
        )
