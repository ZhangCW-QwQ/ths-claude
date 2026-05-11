---
name: risk-validation
trigger:
  - "候选评论已生成，pipeline 第 4 步，pick 推荐前必走"
inputs:
  required:
    - candidate: CommentCandidate
    - understanding: PostUnderstanding
  optional:
    - references / raw_reference_sources（用于 trigram 抄袭粗筛）
outputs:
  schema: src/risk/validator.py::ValidationResult
failure_modes:
  - blocklist 文件缺失 → 抛 FileNotFoundError，**不要降级**（CLAUDE.md §4 #3）
  - relevance 用 mock 实现时阈值偏低 → 在文档显式说明，生产换 embedding 时把阈值抬到 ≥0.5
---

# Skill: 候选评论风险校验（5 层）

## 触发条件

每一条 CommentCandidate 必走，**没有例外路径**。

绕过它需要环境变量 `ALLOW_UNVALIDATED=1` + 显式 WARN 日志（仅供本地调试，CI 强制设回）。

## 步骤

### L1 显式词表（确定性，最先跑）

依次检查：
- `slurs.txt`：任意命中 → `REJECTED_RISK`
- `political_combos.txt`：任意 (a, b) 共现 → `REJECTED_RISK`
- `medical_advice.txt`：任意短语命中 → `REJECTED_RISK`

理由：这一层成本极低、误报极少、解释力最强。生产词表由合规给。

### L2 相关度

`topic_relevance(post_text, comment_text)`：
- mock 实现：jaccard(top-20 keywords, comment_tokens) × length_penalty
- 阈值：mock 模式 0.10；生产 embedding 0.5
- 不达 → `REJECTED_OFFTOPIC`

### L3 抄袭粗筛

对 `raw_reference_sources` 中的每条评论 body 算 char-trigram 重合度。
任意 ≥ 0.4 → `REJECTED_PLAGIARISM`。

这一关存在的目的是**双保险** —— 我们已经在 prompt 阶段不放原文，但 LLM 可能从训练数据里独立"想到"相同句子。

### L4 自评风险阈值

来自 generator._self_risk：
- offensiveness > 0.5 → `REJECTED_RISK`
- backfire > 0.5 → `REJECTED_RISK`

这是软指标，但放进 hard gate —— 因为模型的自评通常**偏低估**，过线说明问题真的明显。

### L5 状态机校验

只允许下列终态：
- `APPROVED_FOR_HUMAN_USE`（仅供人编辑参考）
- `REJECTED_RISK`
- `REJECTED_OFFTOPIC`
- `REJECTED_PLAGIARISM`

任何其他状态 → `pre_publish_safety_gate` Hook 直接 BLOCK 整个 pipeline。

## 输出模板

```json
{
  "state": "approved_for_human_use",
  "reasons": [],
  "metrics": {
    "relevance": 0.42,
    "max_trigram_overlap": 0.18,
    "self_offensive": 0.10,
    "self_misread": 0.15,
    "self_backfire": 0.15
  }
}
```

## 失败回退

| 失败 | 兜底 |
|---|---|
| blocklist 加载失败 | **不**降级，pipeline 抛错。词表是核心安全约束。 |
| relevance 极端值（NaN） | 视作 0.0 → REJECTED_OFFTOPIC |
| 没有 raw_reference_sources（retrieval 降级） | L3 跳过，metrics 标 `max_trigram_overlap=0` + warning="no_sources" |

## 关联

- 上游：comment-crafting
- 下游：`pick_best`（在 validate 完成后选最优）
- Hook 联动：`pre_publish_safety_gate` 在所有候选 validate 后再做一次"全局视角"检查
