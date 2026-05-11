# Decision 0002 — 引入 `do_not_engage` 等级，而不只是过滤候选

**日期**：2026-05-10
**作者**：候选人

## 背景

最初的设计里，risk 只有 low/medium/high 三档。high 仅意味着"风格池被收窄到 sharp_summary / thought_question"。

跑 xhs_ed_advice_risk（"三天瘦5斤 不要打疫苗"）时发现：
- post 含"不要打疫苗"，按当前规则只是 medical_advice 进 flagged_buckets，level 是 medium
- generator 走完，给出 3 条候选；候选本身不含医疗建议词，所以全部通过 validator
- 结果：系统对一条**反疫苗营销**的帖子产出了"激发互动"的评论 —— 这是助长伤害

## 决策

新增 `do_not_engage` 状态。规则：帖子本身命中 `post_do_not_engage.txt` → pipeline **完全短路**，不 retrieval、不 generation、不 validation，返回 `recommended=null` + `downgrade_flags.do_not_engage=true`。

实现：
- `src/risk/blocklists/post_do_not_engage.txt`（合规可独立维护）
- `src/understanding/analyzer.py::_scan_risk` 加载并匹配
- `src/pipeline.py::run_one` 在 understanding 之后立即检查并短路

## 为什么不只是"重写候选"

因为问题在帖子层面，不在候选层面。一条反疫苗帖即使我写出"中性提问"，只要被发布出去仍是为它的传播加速。最安全是不参与。

## 验证

`tests/test_pipeline_e2e.py::test_do_not_engage_post_short_circuits`。

## 教训

风险评估的颗粒度需要从"候选评论"上推到"是否参与本帖" —— 这是 Hypothesis C（见 design.md §1）的合理化。
