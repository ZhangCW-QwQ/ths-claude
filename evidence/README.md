# 过程证据

> 题目要求："关键 AI session 日志 / 截屏 / 录屏（任选，能体现你如何构造上下文、如何验证、如何纠偏）"
>
> 这里放三类：
> - `sessions/*.jsonl` — pipeline 每次跑都自动落，记录 LLM 调用、Hook 触发、状态机转移
> - `decisions/*.md` — 我（候选人）开发过程中的关键决策与"反悔"记录
> - `adversarial/*.md` — 三个对抗演练（注入 / 翻车 / 信息缺失）的端到端 trace

## sessions/

每条 pipeline 调用产生一份 `<session_id>.jsonl`。每行一条事件：

```jsonl
{"ts": 1778425446.12, "kind": "llm_call", "purpose": "post_understanding", "post_id": "trump_israel_ainvest", ...}
{"ts": 1778425446.18, "kind": "pattern_extracted", "query": "Trump", "patterns": [...]}
{"ts": 1778425446.22, "kind": "hook_ok", "hook": "pre_generation_injection_guard", "event": "before_generation"}
{"ts": 1778425446.30, "kind": "risk_validation", "post_id": "trump_israel_ainvest", "state": "approved_for_human_use", ...}
{"ts": 1778425446.31, "kind": "pipeline_done", "post_id": "trump_israel_ainvest", "passed": 2}
```

> 看 `examples-batch.jsonl` 是最近一次 `scripts/run_all_examples.py` 的批量产物。

## decisions/

我的关键决策日志（人写的）。文件命名 `NNNN-YYYY-MM-DD-<short-name>.md`。

## adversarial/

三个对抗场景的 step-by-step trace + 复盘。
