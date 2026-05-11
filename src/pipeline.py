"""端到端 pipeline 编排。

CLI:
    python -m src.pipeline run --post-id <id>           # 单条
    python -m src.pipeline run-all                       # 跑 data/posts/posts.jsonl 全部
    python -m src.pipeline self-check                    # 跑配置自检（不调 LLM）

设计：
- 失败显式：每一步可独立失败，pipeline 决定降级/中断（CLAUDE.md §4 #3）。
- 全程落 evidence/sessions/<session>.jsonl。
- Hooks 是仓库最后一道墙；这里**不跳过**它们，由 hooks/__init__.py 注册的 hook 在每个关键 enter/exit 调用。
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .generation.generator import generate_candidates
from .retrieval.pattern_extractor import extract_patterns
from .retrieval.reddit_client import RetrievalUnavailable, search_high_engagement_comments
from .risk.state_machine import CandidateState
from .risk.validator import pick_best, validate
from .understanding.analyzer import analyze_post
from .utils.logger import log_event

# 注：hooks 通过 import 触发自注册
from hooks import registry as hook_registry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
POSTS_PATH = ROOT / "data" / "posts" / "posts.jsonl"


def _serialize(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    if isinstance(obj, CandidateState):
        return obj.value
    return obj


def _load_post(post_id: str) -> dict:
    if not POSTS_PATH.exists():
        raise FileNotFoundError(f"posts.jsonl missing at {POSTS_PATH}")
    for line in POSTS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if obj["id"] == post_id:
            return obj
    raise KeyError(f"post_id {post_id!r} not found in {POSTS_PATH}")


def run_one(post_id: str, *, session_id: str | None = None) -> dict:
    sid = session_id or f"{post_id}-{int(time.time())}"
    os.environ.setdefault("SESSION_ID", sid)

    raw = _load_post(post_id)

    # 1) Understanding
    understanding = analyze_post(raw)
    hook_registry.run("post_understanding_done", {"understanding": understanding})

    # do_not_engage 短路：完全不进入 retrieval/generation
    if understanding.risk.overall_level == "do_not_engage":
        from .retrieval.pattern_extractor import ReferenceAnalysis

        log_event("pipeline_do_not_engage", {"post_id": post_id, "rationale": understanding.risk.rationale})
        return {
            "post_id": post_id,
            "session_id": sid,
            "understanding": _serialize(understanding),
            "reference_analysis": _serialize(
                ReferenceAnalysis(
                    query="(skipped: do_not_engage)",
                    selection_rationale="post tripped do_not_engage; no retrieval performed",
                    confidence="empty",
                )
            ),
            "candidates": [],
            "recommended": None,
            "recommended_rationale": (
                f"Post is flagged 'do_not_engage' — system refuses to produce comments. "
                f"Reason: {understanding.risk.rationale}"
            ),
            "blocked_by_hook": None,
            "downgrade_flags": {
                "retrieval_offline": False,
                "any_image_unavailable": any(im.status != "ok" for im in understanding.image_facts),
                "injection_suspected": "brand_defamation" in understanding.risk.flagged_buckets,
                "do_not_engage": True,
            },
        }

    # 2) Retrieval (with downgrade)
    query = (understanding.judgments.theme or raw.get("title", post_id))[:80]
    try:
        retrieval = search_high_engagement_comments(query)
        references = extract_patterns(retrieval)
        raw_refs = retrieval.sources
    except RetrievalUnavailable as e:
        log_event("retrieval_downgrade", {"post_id": post_id, "error": str(e)})
        # 降级：用空 reference，pipeline 仍可生成（confidence 低）
        from .retrieval.pattern_extractor import ReferenceAnalysis

        references = ReferenceAnalysis(
            query=query,
            selection_rationale="retrieval unavailable; running in style-heuristic-only mode",
            confidence="empty",
        )
        raw_refs = []

    # Hook: 注入 / 引用守卫
    blocked_reason: str | None = None
    try:
        hook_registry.run(
            "before_generation",
            {
                "understanding": understanding,
                "references": references,
                "raw_refs": raw_refs,
            },
        )
        # 3) Generation
        candidates = generate_candidates(understanding, references)

        # 4) Validation per candidate
        validated = []
        for c in candidates:
            v = validate(
                c,
                understanding=understanding,
                references=references,
                raw_reference_sources=raw_refs,
            )
            validated.append((c, v))

        # Hook: 安全门（生成后、推荐前）
        hook_registry.run(
            "before_publish_decision", {"validated": validated, "understanding": understanding}
        )

        # 5) Pick best
        best = pick_best(validated)
    except hook_registry.HookBlocked as blocked:
        log_event(
            "pipeline_hook_blocked",
            {"post_id": post_id, "hook": blocked.hook_name, "reason": blocked.reason},
        )
        candidates = []
        validated = []
        best = None
        blocked_reason = f"hook[{blocked.hook_name}] BLOCKED: {blocked.reason}"

    output = {
        "post_id": post_id,
        "session_id": sid,
        "understanding": _serialize(understanding),
        "reference_analysis": _serialize(references),
        "candidates": [
            {
                **_serialize(c),
                "validation": _serialize(v),
            }
            for c, v in validated
        ],
        "recommended": (
            {**_serialize(best[0]), "validation": _serialize(best[1])} if best else None
        ),
        "recommended_rationale": (
            f"Picked style={best[0].style}, relevance={best[1].metrics.get('relevance')}, "
            f"backfire={best[1].metrics.get('self_backfire')} — best of "
            f"{sum(1 for _, v in validated if v.passed)} passing candidates."
            if best
            else (
                blocked_reason
                or "No candidate passed validation. Pipeline returns empty recommendation; do not auto-publish."
            )
        ),
        "blocked_by_hook": blocked_reason,
        "downgrade_flags": {
            "retrieval_offline": references.confidence != "online",
            "any_image_unavailable": any(
                im.status != "ok" for im in understanding.image_facts
            ),
            "injection_suspected": "brand_defamation" in understanding.risk.flagged_buckets,
        },
    }

    log_event("pipeline_done", {"post_id": post_id, "passed": sum(1 for _, v in validated if v.passed)})
    return output


def run_all() -> list[dict]:
    posts = [json.loads(line) for line in POSTS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [run_one(p["id"]) for p in posts]


def self_check() -> dict:
    """检查关键文件存在、blocklists 加载、hooks 注册成功。不做任何 LLM 调用。"""
    issues = []
    must_exist = [
        ROOT / "CLAUDE.md",
        ROOT / ".mcp.json",
        ROOT / "data" / "posts" / "posts.jsonl",
        ROOT / "src" / "risk" / "blocklists" / "slurs.txt",
    ]
    for p in must_exist:
        if not p.exists():
            issues.append(f"missing: {p}")
    hooks_registered = list(hook_registry.list_hooks())
    if "before_publish_decision" not in hooks_registered:
        issues.append("hook 'before_publish_decision' not registered")
    return {"ok": not issues, "issues": issues, "hooks_registered": hooks_registered}


def _cli():
    parser = argparse.ArgumentParser("godcomment-pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    one = sub.add_parser("run")
    one.add_argument("--post-id", required=True)
    one.add_argument("--mode", choices=["mock", "real"], default="mock")
    one.add_argument("--out", default=None)
    sub.add_parser("run-all")
    sub.add_parser("self-check")

    args = parser.parse_args()
    if args.cmd == "run":
        os.environ["LLM_MODE"] = args.mode
        os.environ["REDDIT_MODE"] = args.mode
        result = run_one(args.post_id)
        out_path = Path(args.out) if args.out else None
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if out_path:
            out_path.write_text(text, encoding="utf-8")
            print(f"wrote {out_path}")
        else:
            print(text)
    elif args.cmd == "run-all":
        results = run_all()
        print(json.dumps({"count": len(results)}, ensure_ascii=False))
    elif args.cmd == "self-check":
        report = self_check()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    _cli()
