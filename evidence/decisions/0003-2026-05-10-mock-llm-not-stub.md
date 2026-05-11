# Decision 0003 — Mock LLM 是"决定性可读模板"，不是 monkey-patched 第三方 SDK

**日期**：2026-05-10
**作者**：候选人

## 背景

测试需要不依赖真 LLM。常规做法是 monkey-patch 第三方 SDK（openai / anthropic）。我没这么做。

## 决策

在 `src/utils/llm_client.py` 定义 `LLM` Protocol + `MockLLM` 类，整个 pipeline 通过 `get_llm()` 拿实例。`MockLLM` 是"种子化的可读模板生成器"。

理由：
- 测试不应耦合到第三方 SDK 的内部 API（接口随时变）
- Mock 输出"看起来像合理评论"比"返回固定字符串"对测试更有信号
- 决定性（hash 种子）让测试稳定可重跑
- 永远不输出违规内容，避免"测试 fixture 本身违规"的尴尬

## 副作用

mock 的输出风格简单 → relevance 阈值在 mock 模式下需要放宽到 0.10（生产用 embedding 时应抬到 0.5）。这条已经在 `src/risk/validator.py` 注释和 `docs/design.md §8` 里显式说明。

## 验证

`tests/test_pipeline_e2e.py` 全部跑通；`scripts/run_all_examples.py` 输出可读结果。

## 教训

Mock 的设计要服务于"暴露 pipeline 行为"，不是"绕过 LLM 调用"。
