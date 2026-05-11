# Decision 0001 — 不把检索到的 reddit 原文塞进 generation prompt

**日期**：2026-05-10
**作者**：候选人

## 背景

最初的草稿是把 reference-mining 的 top-K 评论原文拼进 generator 的 prompt 当作 few-shot 范例。理由是"few-shot 通常效果好"。

## 触发反悔的证据

写第一版 generator + 第一版 risk_validator 之后，跑 trump_israel_ainvest，发现：

```
candidate.text = "But actually, demanding hostage release is the bipartisan position — pretending it's a Trump-only stance is rewriting recent history."
trigram_overlap with retrieved_comment_3 = 0.62
```

候选评论几乎是检索结果原文的小幅改写。这违反 R1（CLAUDE.md），也是版权风险。

## 决策

把 generator 的 reference 输入从"原文 list"改为"pattern 描述 list"，新增 `pattern_extractor` 模块专门做"套路抽取"。

代码上：
- `src/retrieval/pattern_extractor.py` 是这次改动的产物
- generator 的 prompt 模板把 `Reference patterns (use as inspiration, NEVER copy text)` 标注得很明显
- 新增 Hook `pre_generation_injection_guard` 检查 pattern.description 长度（> 240 字符即视为可能塞了原文）

## 验证

跑 `tests/test_validator.py::test_l3_plagiarism_blocks` 复现"原文当候选"被拦的场景；跑 `tests/test_hooks.py::test_injection_guard_blocks_on_long_pattern_description` 复现"description 过长"被拦。

新跑 trump_israel_ainvest，trigram_overlap 降到 0.23。

## 没采纳的备选

- "保留原文，只是在 prompt 里写'不要直接复述'" — 模型软约束被反复证明会漏。拒。
- "保留原文，但对每条候选做 LLM-as-judge 抄袭检测" — 加大成本与延迟，且仍是软约束。拒。

## 教训

这条决策让我意识到：**风险护栏的工作量不是写一段防御代码，而是改数据流让风险源根本不进入下游**。
