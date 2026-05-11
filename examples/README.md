# 端到端示例输出

每个 `<post_id>.output.json` 是一次 `python -m src.pipeline run --post-id <id>` 的完整产物。
重跑命令：

```bash
python scripts/run_all_examples.py
```

可视化版：直接打开 `demo/index.html`（双击即可），交互式 dashboard 加载这些 JSON 的关键字段。

## 11 条示例

| 示例 | 演示什么 | 路径 |
|---|---|---|
| [`trump_israel_ainvest.output.json`](./trump_israel_ainvest.output.json) | **必测样本**：政治+宗教共现 → high → 强制只走 sharp_summary / thought_question | recommended ✓ |
| [`weibo_inject_attempt.output.json`](./weibo_inject_attempt.output.json) | **对抗 1：Prompt Injection**。`pre_generation_injection_guard` 直接 BLOCKED | hook blocked |
| [`xhs_ed_advice_risk.output.json`](./xhs_ed_advice_risk.output.json) | **do_not_engage** 短路。pipeline 完全不进入 retrieval/generation | short-circuit |
| [`9gag_cat_meme.output.json`](./9gag_cat_meme.output.json) | **图片是一等公民**。纯图无文，靠 image fixture 的 OCR + caption 走通 | recommended ✓ |
| [`zhihu_career_serious.output.json`](./zhihu_career_serious.output.json) | **严肃求助**。系统主动选 thought_question，不发"是的废了"型 | recommended ✓ |
| [`xhs_pretty_house_boast.output.json`](./xhs_pretty_house_boast.output.json) | **图文炫耀**。两张室内图 + 品牌名（TOTO / Le Creuset），不会触发 brand_defamation 误报 | recommended ✓ |
| [`weibo_996_rant.output.json`](./weibo_996_rant.output.json) | **职场情绪发泄**。情绪强但不犯线，sharp_summary + spicy_take 全部进入候选池 | recommended ✓ |
| [`hn_ai_safety_announce.output.json`](./hn_ai_safety_announce.output.json) | **技术圈低情绪**。系统不"瞎抖机灵"，优先 sharp_summary | recommended ✓ |
| [`xhs_food_multi_image.output.json`](./xhs_food_multi_image.output.json) | **多图聚合**。3 张图独立 image_facts，pipeline 聚合判断 | recommended ✓ |
| [`weibo_brand_negative.output.json`](./weibo_brand_negative.output.json) | **品牌负评边界**。负面 + 品牌名出现但不诽谤 → 候选不会输出"垃圾品牌" | recommended ✓ |
| [`hn_layoff_discussion.output.json`](./hn_layoff_discussion.output.json) | **严肃求共情**。被裁叙事 → 思考型反问，不引战 | recommended ✓ |

## 怎么读这份 JSON

每份输出有 6 块：

1. `understanding` — 帖子结构化理解（schema 在 `src/understanding/schema.py`）
2. `reference_analysis` — 检索到的"套路"，**不**含原文
3. `candidates` — 3-5 条候选，每条带 `validation` 子对象
4. `recommended` — 选中的最优候选；可能是 `null`
5. `recommended_rationale` — 为什么是这条 / 为什么没有
6. `downgrade_flags` + `blocked_by_hook` — 异常路径的标记

> Trump 那条的 `understanding.risk.overall_level == "high"` 但仍生成候选 —— 这是**有意的**：高风险下我们仍试图给出参考评论，只是把风格池压到了最安全的两个；evidence 日志里能看到完整决策链。
