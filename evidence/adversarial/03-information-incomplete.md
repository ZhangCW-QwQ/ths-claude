# 对抗演练 #3 — 信息不完整（图片失败 / 帖子全空）

**测试帖**：`ig_image_only_failed`

```
title: ""
body:  ""
images: ["https://example.invalid/img/ig_unavailable.jpg"]
fixture (data/fixtures/images/ig_image_only_failed.json):
  status: "unavailable"
```

## Pipeline 反应（实际跑）

```
1. FixtureImageProvider 加载 fixture → image_facts[0].status = "unavailable"
2. analyzer 不调 LLM 视觉理解（已是 unavailable），image_judgments[0].confidence = 0.0
3. combined_text 为空，sanitized.wrapped_text 仅含包裹 + reminder
4. mock LLM 用空文本生成 understanding → judgments.theme = "topic"（兜底字符串），confidence = 0.4（缺核心字段）
5. retrieval query="topic"[:80]，落到 _generic_X 的 hash bucket
6. generator 按 direction（low risk fallback: sharp_summary / thought_question / spicy_take）生成 3 条
7. risk_validator L2：候选与原帖（空）的 jaccard = 0 → REJECTED_OFFTOPIC × 3
8. recommended = None
9. downgrade_flags.any_image_unavailable = true
```

## 关键性质

- **不瞎编**：image_facts[0].status 显式为 `unavailable`，不会捏造图片描述
- **不静默**：downgrade_flags 标位、recommended_rationale 写明 "no candidate passed validation"
- **不强推**：pipeline 不会"勉强返回"一条 — 即使生成了 3 条候选，全部 fail relevance 后返回 None

## 对照实验

如果把 fixture 改成 `status: "ok"` + 一段 caption，pipeline 应能基于 caption 走通并产出推荐。
（参考：`9gag_cat_meme` 走的就是这条路径。）

## 反思 — "什么时候应该返回 None"

我把"宁可不出，不可瞎出"作为 pipeline 的默认行为。这个偏向带来的副作用：
- 在 mock 模式下少量"应该能过"的边界 case 也被拦了
- 生产换 embedding 后阈值上调，召回率会回升

但反过来就糟糕得多：一条产品级"神评论"系统如果在缺数据时仍硬给推荐，等于把"互动机会"换成了"翻车风险"。

## 没覆盖的失败模式

- 部分图片成功部分失败：当前实现里，每张图独立 status，但 image_judgments 的 confidence 还没融到全局 confidence。理想是"任一图失败 → 全局 confidence -0.2"，这条已经写在 docs/design.md §8 剩余风险。
- 图片下载成功但 OCR/caption 全空：当前实现把 is_meme = False、likely_punchline = None，但 confidence 仍 0.5；应该 0.3。
