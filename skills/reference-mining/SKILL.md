---
name: reference-mining
trigger:
  - "已有 PostUnderstanding，需要从 Reddit 等参考社区学习高互动评论的'套路'"
  - "pipeline 第 2 步"
inputs:
  required:
    - understanding.judgments.theme: 用作主 query
    - understanding.judgments.tone: 影响语气方向筛选
  optional:
    - extra_queries: list[str]，可选的二级 query
  forbidden:
    - 把 PostUnderstanding 整体往 Reddit MCP 塞 —— 暴露过多上下文 + 浪费 tokens
outputs:
  schema: src/retrieval/pattern_extractor.py::ReferenceAnalysis
failure_modes:
  - retrieval API 不可用 → 抛 RetrievalUnavailable；pipeline 走"无参考、降级 confidence"路径
  - 检索到 0 条 → ReferenceAnalysis.patterns=[]，不要凭空捏造 pattern
  - 命中评论但全是 link/img-only → 视作无效，跳过这些样本而不是 fail
---

# Skill: 神评论"套路"挖掘

## 触发条件

PostUnderstanding 已生成 + 风险等级 ≠ `do_not_engage`。

如果 `risk.overall_level == 'do_not_engage'`，**不要**做检索 —— 直接返回空 ReferenceAnalysis 并标 confidence=`empty`。

## 步骤

### 1. 构造 query

主 query：`understanding.judgments.theme[:80]`。
副 query（可选）：从 `judgments.punch_points` 取 1 个补充。

**不要**把帖子的整段正文当 query —— 那会让检索结果偏向"帖子复刻"而非"通用套路"。

### 2. 调用 reddit-search MCP（最小权限）

只用 `search.public` + `comments.read`。
取 `limit=8` ，rank 用我们自定义的 `reply_per_upvote`，**不要**信任 Reddit 自带的 `top` 排序（那个偏向"暖文"）。

### 3. 多样性筛选

按 (subreddit + 长度桶) 去重，每 sub 最多取 2 条。
目标 K = 6。

### 4. **套路抽取**（关键）

对每条入选的评论，检测它命中下面哪些 pattern：

| pattern | 检测信号 |
|---|---|
| `punchy_one_liner` | 长度 ≤ 60 字符 + reply_per_upvote 高 |
| `rhetorical_question` | 含 `?` / `？` |
| `contrast_setup` | 含 `but / 然而 / 其实` |
| `data_drop` | 含 ≥ 2 位数字 |
| `self_deprecating` | 含 `I am / 我也 / same here` |

记录该 pattern 的 `examples_count` 与 `confidence`，**不要**记原文。

### 5. 写选择理由

`selection_rationale` 必须显式说明：
- 为什么按 reply_per_upvote 而非 score
- 多样性 / 去重做了什么
- 哪些样本被丢、为什么

## 输出模板

```json
{
  "query": "trump israel ally",
  "selection_rationale": "排除...; 取 reply_per_upvote top-K; subreddit 去重",
  "patterns": [
    { "name": "punchy_one_liner", "description": "...", "skeleton": "...",
      "why_it_works": "...", "examples_count": 3, "confidence": 0.7 }
  ],
  "sample_count": 6,
  "confidence": "online"
}
```

## 失败回退

| 失败 | 兜底 |
|---|---|
| MCP 不可达 / 超时 / 频控 | `RetrievalUnavailable`；pipeline 把 references.confidence 设为 `empty`，generation 仍可跑（仅靠 styles guideline） |
| 检索 0 结果 | `patterns=[]`, `selection_rationale="empty results"`，不要捏造 |
| 全为图片评论 | 跳过，记录在 `selection_rationale` 末尾 |

## 关联

- 上游：post-understanding
- 下游：comment-crafting（读 patterns，**不**读原始评论）
- 安全约束：违反 CLAUDE.md R1（pattern 描述里塞原文）会被 Hook `pre_generation_injection_guard` 拒绝
