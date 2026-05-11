# 交付清单（题目对照）

> 这份对照表把题目第三章的"硬性清单"逐条对到本仓库的具体文件。
> 面试官可以按此快速核对。

## A 产品交付

| 题目要求 | 交付位置 | 备注 |
|---|---|---|
| A1. 帖子理解结果（含 schema 设计思路） | `src/understanding/schema.py` + `docs/schema.md` | schema 三层分离，事实/判断/派生显式区分；schema 自带版本号 |
| A2. 神评论参考学习结果 | `src/retrieval/pattern_extractor.py` + `docs/pattern-gallery.md`（6 个套路画廊）+ 11 个 example 的 `reference_analysis` | 显式说明检索 query / 筛选理由 / 套路归纳；**绝不含原文** |
| A3. 原创评论生成结果（每帖 3-5 条 + 推荐 + 风险评估） | `examples/*.output.json`（11 条，含 candidates + recommended + recommended_rationale + 各候选的 self_risk_estimate / validation）+ `demo/index.html` 交互式可视化 | trump 案例展示了 high-risk 下风格池被收窄到 2 个；其余案例展示标准 3 风格 |
| A4. 配图 / 梗图（加分项） | 已在 demo 与 9gag_cat_meme case 中展示了"基于 image_facts 反向构思评论 + 配图建议"的接口位置；未集成图像生成 API（剩余风险见 `docs/design.md §8`） | image_facts 已为图像生成预留 schema |

## B AI 原生工程工件（必须 ≥ 3 项）

| 工件 | 文件 | 关键说明 |
|---|---|---|
| **CLAUDE.md** ✅ | [`CLAUDE.md`](./CLAUDE.md) | 7 条红线（R1-R7）、验收口径、上下文边界、决策原则、改动协议 |
| **Skills（≥1）** ✅ | [`skills/`](./skills) 4 个 Skill | post-understanding / reference-mining / comment-crafting / risk-validation；每个含触发条件、输入契约、步骤、输出模板、失败回退 |
| **Hooks（≥1）** ✅ | [`hooks/`](./hooks) 3 个 Hook + 注册中心 + yaml 配置 | pre_generation_injection_guard、pre_publish_safety_gate、prompt_secret_leak_guard；每个 Hook 都有独立单测证明拦截真实发生 |
| **.mcp.json** ✅ | [`.mcp.json`](./.mcp.json) | Reddit / Vision / Sensitive-Lexicon 三个 server，每个标 scope/why/fallback；并显式列出**刻意未接入**的 MCP 与理由 |

> 4 项全交。

## C 设计文档（必须）

| 题目 8 个显性化问题 | 在 `docs/design.md` 的对应章节 |
|---|---|
| 1. 初始假设 | §1（含 1 个被推翻的假设）|
| 2. 验证与反证 | §2（含 5 个边界对照实验）|
| 3. 问题重构 | §3（3 个重构方向，1 个采纳、1 个半采纳、1 个拒绝）|
| 4. 工具编排（Skill / Hook / prompt 的边界） | §4（含正反例对照表）|
| 5. 风险边界（不可操作区） | §5 + `CLAUDE.md` §1 |
| 6. 失败恢复（降级矩阵） | §6（10 种失败模式逐条降级方案）|
| 7. 上下文工程 | §7（常驻 / 按需 / 受限优先级）|
| 8. 剩余风险 | §8（10 条剩余风险按影响排序）|

## 五. 内置对抗场景

| 场景 | 处理位置 |
|---|---|
| 场景 1 — Prompt Injection | `evidence/adversarial/01-prompt-injection.md` + `examples/weibo_inject_attempt.output.json` + `tests/test_hooks.py::test_injection_guard_*` |
| 场景 2 — 模型翻车 | `evidence/adversarial/02-model-meltdown.md` + `tests/test_validator.py` 的 L1/L4 |
| 场景 3 — 信息不完整 | `evidence/adversarial/03-information-incomplete.md` + `examples/9gag_cat_meme.output.json` 反例对照 |
| 场景 4 — AI 错误建议（用证据反驳） | `evidence/adversarial/04-pushback-on-bad-suggestions.md` |

## 六. 提交内容

| 题目要求 | 仓库位置 |
|---|---|
| 1. 代码 / 脚本 | `src/` + `scripts/run_all_examples.py` |
| 2. 测试数据集 + 选择理由 | `data/posts/posts.jsonl`（13 条）+ `data/posts/selection_rationale.md` |
| 3. 输出结果示例（≥ 5 条） | `examples/*.output.json`（**11 条** end-to-end）+ `examples/README.md` + `demo/index.html` 交互式 dashboard |
| 4. AI 工程工件 | 见 B 部分 |
| 5. 设计文档 | `docs/design.md` + `docs/architecture.md` + `docs/schema.md` + `docs/risk-model.md` + `docs/pattern-gallery.md`（5 篇，全部含 Mermaid 图） |
| 6. 过程证据 | `evidence/sessions/*.jsonl`（自动落）+ `evidence/decisions/*.md`（人写）+ `evidence/adversarial/*.md`（对抗 trace）|

## 验收口令

```bash
# 1) 配置自检（不调 LLM）
python -m src.pipeline self-check

# 2) 跑端到端 demo
python -m src.pipeline run --post-id trump_israel_ainvest --mode mock

# 3) 跑全测（36 个测试，含 hook 拦截、状态机不变量、注入演练）
pytest tests/ -q

# 4) 重生成 5 条示例
python scripts/run_all_examples.py
```

预期：self-check ok=true；36 tests pass；5 个 examples 输出符合各自演示意图。
