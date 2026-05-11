# PostUnderstanding Schema

> 这份文档解释 `src/understanding/schema.py` 的设计取舍。
> 目的不是逐字段复述，而是说"为什么这样分层"。

## 三层分离

```
PostUnderstanding
├── facts          ← 可验证事实（不允许 LLM 介入）
├── judgments      ← 模型主观判断（必须带 confidence）
├── image_facts[]  ← 图片层独立可降级
├── image_judgments[]
├── risk           ← 与 hooks/blocklists 共享的风险结构
└── direction      ← 推荐与避免的风格、互动方向
```

**为什么不把 facts 和 judgments 合并**：
- 下游 risk_validator 对"事实"和"判断"的处理不同。比如 `theme` 是判断（可能错），`platform` 是事实（错就是数据问题）。
- evidence 日志回放时，区分这两层能定位错误在 LLM 还是上游数据。

**为什么图片是独立子结构**：
- 图片 IO 失败概率显著高于文字（下载、超时、NSFW、格式不支持）
- 我们要能"图片挂了但 pipeline 继续"
- 所以 image_facts 和 image_judgments 是 list（每张图独立 status）

## 字段是事实还是判断

| 字段 | 类型 | 谁产出 |
|---|---|---|
| `facts.platform` / `post_id` / `url` / `posted_at` / `engagement_metrics` | 事实 | 上游数据源 |
| `facts.has_image` / `image_count` | 事实 | analyzer（确定性） |
| `image_facts[i].status` / `ocr_text` / `objects` / `scene_caption` | **事实**（来自外部 vision API，可验证） | image-understanding MCP |
| `image_judgments[i].sentiment` / `is_meme` / `likely_punchline` | 判断 | analyzer 后处理 + LLM |
| `judgments.theme` / `core_claim` / `tone` / `punch_points` | 判断 | LLM |
| `risk.flagged_buckets` / `sensitive_entities` / `overall_level` | **事实**（确定性词表扫描，不让 LLM 染指） | analyzer._scan_risk |
| `direction.recommended_styles` / `avoid_styles` / `interaction_levers` | 派生 | analyzer._decide_direction（规则） |

**关键决策**：风险评估**完全不让 LLM 参与**。理由：
1. 风险扫描需要可解释、可单测、可审计。
2. LLM 在"自评是否冒犯"上系统性偏低估。
3. 风险结构需要能在 Hook 里硬拦截 —— 必须是规则。

## 为什么 schema 有版本号

`SCHEMA_VERSION = "post_understanding/2026-05-10"`

- 写进每条 understanding，方便 evidence 回放。
- 升级时旧 evidence 不会瞎对齐。
- 任何 schema 改动需要 bump 版本 + 在 docs/changelog 留一行。

## 与 prompt 的关系

generator 的 prompt 模板**只读**这些字段：
- `judgments.theme / core_claim / tone / punch_points`
- `direction.interaction_levers`
- `risk.overall_level`

generator 的 prompt **不读**：
- `facts.engagement_metrics`（数字泄露易被反推帖子）
- `image_facts[i].ocr_text`（已经在 understanding 阶段融入了 judgments）
- `risk.sensitive_entities`（避免模型"用名字"）

如果哪天有需求把 `engagement_metrics` 喂给 generator，必须先经过 PII / 数值脱敏。
