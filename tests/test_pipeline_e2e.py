"""端到端冒烟测试：每一条测试帖子都能跑出可解释的结果。"""
import json

import pytest

from src.pipeline import run_one


@pytest.mark.parametrize("post_id", [
    "trump_israel_ainvest",
    "xhs_pretty_house_boast",
    "reddit_aita_birthday",
    "weibo_996_rant",
    "hn_ai_safety_announce",
    "9gag_cat_meme",
    "weibo_inject_attempt",
    "xhs_ed_advice_risk",
    "zhihu_career_serious",
    "ig_image_only_failed",
    "xhs_food_multi_image",
    "weibo_brand_negative",
    "hn_layoff_discussion",
])
def test_pipeline_produces_valid_output_shape(post_id):
    out = run_one(post_id)
    # 必填字段
    assert "understanding" in out
    assert "reference_analysis" in out
    assert "candidates" in out
    assert "recommended_rationale" in out
    assert "downgrade_flags" in out
    # rationale 非空
    assert out["recommended_rationale"]
    # JSON 可序列化
    json.dumps(out, ensure_ascii=False)


def test_injection_post_is_blocked():
    out = run_one("weibo_inject_attempt")
    assert out["recommended"] is None
    assert out["blocked_by_hook"] is not None
    assert "injection" in out["blocked_by_hook"].lower() or "injection" in out["recommended_rationale"].lower()


def test_do_not_engage_post_short_circuits():
    out = run_one("xhs_ed_advice_risk")
    assert out["recommended"] is None
    assert out["candidates"] == []
    assert out["downgrade_flags"].get("do_not_engage") is True


def test_image_only_failed_does_not_invent():
    out = run_one("ig_image_only_failed")
    # 图片不可用应在 downgrade_flags 标出
    assert out["downgrade_flags"]["any_image_unavailable"] is True
    # 关键：不应"假装看到了图片"。 image_facts[0].status 必须是 unavailable
    assert out["understanding"]["image_facts"][0]["status"] == "unavailable"


def test_high_risk_post_uses_only_safe_styles():
    out = run_one("trump_israel_ainvest")
    used_styles = {c["style"] for c in out["candidates"]}
    assert used_styles.issubset({"sharp_summary", "thought_question"}), (
        f"high-risk post must not use spicy/witty; got {used_styles}"
    )
