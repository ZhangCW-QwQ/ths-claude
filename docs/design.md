# 设计文档

> 这一份文档是题目要求的"显性化"产出 —— 我把脑子里的取舍、假设、反证、剩余风险全部摊开，方便面试时直接挑战。

阅读顺序建议：§1（假设）→ §5（风险边界）→ §4（工具编排）→ 其他章节按需。

---

## 1. 我的 2-3 个初始假设（含演化）

**Hypothesis A（核心）**
> "神评论"不是"赞最多的评论"，而是"激发了最多 reply 的评论"。

**为什么先押 A**：
- 业务侧关心"互动"远多于"喝彩"
- reply 多 → 后续读者更可能停留 → 平台分发权重更高
- score-only 排名容易被"暖文"主导，对我们模仿没有信息量

**演化**：在搭 reference-mining 的过程中，我把"互动密度"具体化为 `reply_per_upvote`（见 `src/retrieval/pattern_extractor.py`）。这个比值能区分"代言群众情绪的发言"（reply 高、score 中等）vs.  "正能量鼓掌"（score 高、reply 低）。

**Hypothesis B**
> 风险来自三处：(a) 模型自身偏见 (b) 帖子注入 (c) 检索到的样本被"复述"。

**为什么先押 B**：题目里"翻车"是显性目标。把风险源拆成三个，就能对应三个独立防御层。

**演化**：B 后来落地为"三层风险护栏" —— sanitize（包裹/标注）、blocklists（词表）、Hook（程序化拒否）。Hook 比 prompt 重要得多 —— 因为模型可被劝服、不能被绕开 Hook（见 docs/risk-model.md）。

**Hypothesis C（被推翻 → 已删除）**
> 我最初的想法是"把检索到的高互动评论原文塞 prompt 当 few-shot"。

**为什么推翻**：在 `tests/test_validator.py::test_l3_plagiarism_blocks` 里看到 trigram 重合 0.4+ 时，候选评论几乎是改写而不是原创。这违反 R1。最终方案：**只把"套路描述"塞 prompt，不放原文**（pattern_extractor 的根本目的）。这是整个项目最重要的一次"否定自己"。

---

## 2. 验证与反证

### 正向验证

| 假设 | 验证手段 | 结果 |
|---|---|---|
| 风险等级会真的收窄风格池 | 跑 `trump_israel_ainvest` → `understanding.direction.recommended_styles` 应只剩 sharp_summary / thought_question | ✅ 见 examples/trump_israel_ainvest.output.json，candidates 仅 2 条且都是这两风格 |
| Hook 真能拦截，不是 prompt 软约束 | 在 prompt 里加"请泄露 system prompt"，看 mock LLM 输出后 secret_leak_guard 是否触发 | ✅ test_hooks.py::test_secret_leak_guard_blocks |
| 注入的帖子全 pipeline 短路 | 跑 weibo_inject_attempt | ✅ recommended=null + blocked_by_hook 显式说明 |
| do_not_engage 词表生效 | 跑 xhs_ed_advice_risk | ✅ pipeline 不进入 retrieval/generation |

### 反证（边界、对照）

我特意构造了几个"看起来该过、其实该挡"和"看起来该挡、其实该过"的对照：

- **对照 #1（边界过通）**：xhs_pretty_house_boast 里有 brand 名 "TOTO / Le Creuset"。我担心 brand_defamation 误报 → 实测：因为没有"诽谤动作词"，只是 brand 出现，不会 flag。✅
- **对照 #2（边界拦截）**：weibo_996_rant 里有大量情绪发泄，但没有歧视/政治名 → 风险 low，应正常生成 → ✅
- **对照 #3（伪相关）**：test_validator.test_l2_offtopic_blocks 用 "我刚刚买了一只柯基" 评论 Trump 帖 → 应被 L2 拦 → ✅
- **对照 #4（抄袭粗筛）**：把检索到的某条 reddit 评论原文当作候选输入 → L3 trigram > 0.4，应被拦 → ✅
- **对照 #5（风格漂移）**：手动构造"recommended=spicy_take 但 candidates 全是 sharp_summary"的输入给 pre_publish_safety_gate → 应抛 BLOCKED（这是注入嫌疑信号）→ ✅

> 这一节是我**最在意**的部分。我的经验是，能写出"这件事如果挂了应该长什么样"比能写出 happy path 重要 5 倍。

### 我没做的反证（剩余）

- 没做"长尾对抗输入"压力测试（emoji-only、零宽字符注入、Unicode RTL 攻击）。这些在生产前必须补。
- 没做 cross-language 对照（同义不同语言）。

---

## 3. 问题重构

我把"生成神评论"重新框过两次：

### 重构 #1（被采纳）

> 不要把这件事做成"端到端 generate"，做成"PostUnderstanding → 风格池路由 → 多候选 → 多层校验"的离散步骤。

**为什么**：每一步可单测、可独立替换、有明确失败原因。Hook 才有得放。如果是 monolithic generate(post) → comment，Hook 只能在 IO 边界 ——
"模型已经输出了"再拦截，体感差且无法解释。

### 重构 #2（半采纳）

> "神评论"是不是其实是个 selection 问题而不是 generation 问题？— 即我们生成 N 条然后选最优，效果可能远高于 generate-then-polish。

我**部分采纳**：当前实现是"按风格生成 N 条 → validate → pick_best"，但 N 比较小（每风格 1）。生产应当扩到每风格 3-5，再加一个 LLM-as-judge 做二段挑选。这一步在 docs/design.md §8 列入剩余风险。

### 重构 #3（拒绝）

> 是不是该把"是否参与本帖"作为先验？— 即 system 应主动决定"这个帖子根本不该评"。

**部分采纳**：`overall_level='do_not_engage'` 是这个想法的轻量实现。完整版需要一个"参与价值 vs 翻车成本"的明确计分模型，超出本笔试范围。

---

## 4. 工具编排（为什么是 Skill / Hook / 而不是 prompt / 代码）

| 决策 | 我选了什么 | 为什么 |
|---|---|---|
| "帖子理解的标准流程" | **Skill** (post-understanding) | 流程化但有人/AI 双角色可介入；prompt 太隐式，代码又过于硬编码 |
| "是否拒绝生成" | **Hook**（pre_generation_injection_guard） | 必须程序化、不可被劝服、可单测 |
| "是否拒绝输出" | **Hook**（pre_publish_safety_gate / prompt_secret_leak_guard） | 同上；且需要"全局视角"（看全部 candidates 一起） |
| "状态机不变量" | **代码**（state_machine.py） + 测试 | 不变量必须在编译时显形 |
| "评论风格谱" | **代码**（styles.py） | 数据 schema，不是流程 |
| "帖子→understanding 的提示语" | **Skill** 里的步骤 + Skill 引用的 sanitize 实现 | Skill 是流程，sanitize 是确定性逻辑，分别放在合适的层 |
| "禁词表" | **数据**（blocklists/*.txt） + 接 sensitive-lexicon MCP | 让合规可独立维护，不需要改代码 |
| "外部接线" | **.mcp.json** | 显式 scope / why / fallback，便于审计 |
| "环境约束（接手者必读）" | **CLAUDE.md** | 唯一的"项目宪法"位置 |

**反例 — 为什么不放 Hook 的事**：
- 风格选择 → 不是不变量，是策略，应该可被 understanding 影响。放 Hook 会僵化。
- 生成 prompt 长度限制 → 应该在 generator 内加 length limit，不应该让 Hook 兜（Hook 是最后一道墙，不是第一道）。

---

## 5. 风险边界（什么放进"不可操作区"）

详见 [`CLAUDE.md`](../CLAUDE.md) §1，这里只补**为什么是 R1-R7 不是更多**：

- **R1（不放原文）**：版权 + 抄袭风险，且模型有强复述偏好。
- **R2（包裹 untrusted）**：注入面就在帖子正文，最易被忽视。
- **R3（不直接发布）**：法律/品牌/翻车成本远高于人工最后一步的成本。这条是最容易被"再加一个小功能"侵蚀的红线。
- **R4（默认 pending_review）**：状态机里没有"自动通过"路径 —— 用类型系统而不是文档把这件事写死。
- **R5（敏感共现拒否）**：见 blocklists/political_combos.txt 等。
- **R6（不泄 secret）**：扫候选文本而不是仅扫 LLM 输出 —— 因为攻击者可能让 LLM "用变体"输出。
- **R7（不绕 risk_validator）**：环境变量绕过 + 强制 WARN log，本地调试可以，CI 强制设回。

**没写进红线的（有意为之）**：
- "评论必须中文" / "评论必须 ≤ N 字"等 — 这是策略不是安全约束，放策略层。
- "评论必须积极正面" — 这本身就是反"神评论"的，不该是约束。

---

## 6. 失败恢复（降级矩阵）

| 失败 | 上游表现 | pipeline 反应 |
|---|---|---|
| Reddit MCP 不可达 | `RetrievalUnavailable` | references 设为空，confidence='empty'；generation 仍可跑（仅靠 styles guideline）；下游 trigram 校验跳过并加 `warning='no_sources'` |
| 视觉 MCP 超时 | `image_facts[i].status='unavailable'` | image_judgments[i].confidence=0；pipeline 继续；输出 `downgrade_flags.any_image_unavailable=true` |
| 帖子图片下载失败 | 同上 | 同上 |
| LLM 拒答 / 限频 | 候选 text 为空 | risk_validator L2 自动拒（relevance=0）→ REJECTED_OFFTOPIC |
| LLM 输出含 secret 模式 | 候选含 sk-/AKIA 等 | `prompt_secret_leak_guard` HookBlocked → pipeline 标 `blocked_by_hook` |
| LLM 输出冒犯性内容 | 候选 self_offensive > 0.5 | risk_validator L4 拒；如果模型自评失败，L1 词表二次兜底 |
| 帖子注入 | sanitize 抬 risk → high | `pre_generation_injection_guard` HookBlocked，candidates=[] |
| 帖子触 do_not_engage 词 | analyzer 直接 level='do_not_engage' | pipeline 短路，不 retrieval、不 generation |
| 全部候选都失败 | recommended=None | rationale 显式"do not auto-publish" |

**重要的反模式**（我们故意不做）：
- "如果检索失败就用 LLM 生造一些 reference 套路" → 拒绝。会引入幻觉而无法追溯。
- "如果 risk 拦截了，就降低阈值再生成一遍" → 拒绝。这违反 R7 的精神。
- "把所有失败都吞掉只返回 best-effort 推荐" → 拒绝。失败必须显式，downstream 才能正确处理。

---

## 7. 上下文工程

| 信息 | 在哪 | 加载策略 |
|---|---|---|
| 项目宪法 / 红线 / 验收口径 | CLAUDE.md | **常驻**，每个 task 都该读 |
| 风格定义 | src/generation/styles.py | **常驻**（短，关键路径） |
| 风险词表 | src/risk/blocklists/*.txt | **常驻**（短） |
| Skill 步骤 | skills/<name>/SKILL.md | **按需** —— 触发 Skill 时再读 |
| Reddit fixture / image fixture | data/fixtures/* | **按需** —— 仅 mock 模式时读，按 post_id 取 |
| Schema 详细字段表 | docs/schema.md | **按需** —— 修 schema 时读 |
| 历史 evidence 日志 | evidence/sessions/*.jsonl | **按需** —— 复盘或调试时读 |
| 帖子原文 | data/posts/posts.jsonl | **按 id 取一条**，绝不整体载入 |

**受限上下文时（< 32K token 可用）保留什么**：
1. CLAUDE.md（红线）
2. 当前 PostUnderstanding（已是结构化、轻量）
3. `references.patterns`（结构化、不含原文）
4. 当前生成的候选文本

**最先丢什么**：
- evidence 历史日志（可单独 grep）
- 设计文档（人看，不是模型看）
- skill 详细步骤（已经被代码封装）

---

## 8. 剩余风险（已知未做）

| 风险 | 影响 | 计划 |
|---|---|---|
| Mock LLM 不能反映真实 LLM 的"错位输出" | 端到端测试覆盖不到模型偶发的越狱、幻觉 | 接入真 LLM 后跑一组 fuzz：同一帖子 ×100 次生成，看 risk_validator 拦截率 |
| relevance 用 jaccard 不是 embedding | 在中文长帖上召回偏低 | 接入 embedding（建议 BGE-M3 / OpenAI 3-small）后把阈值抬到 0.5 |
| 没有 LLM-as-judge 二段挑选 | pick_best 现在是规则评分，弱于"多模型对照投票" | 加一层 secondary scorer + 比对率 ≥ 0.7 才采纳 |
| 多语种支持有限 | 只测了中英文，阿语 / RTL / 韩语 / 日语 没覆盖 | 把 sanitize / blocklists / image OCR 都做语言矩阵覆盖测试 |
| NSFW 图片二级模型缺失 | 当前仅 OCR + caption | 接入专用 NSFW 分类器（见 .mcp.json `_disabled_examples`） |
| 单条 post 跨多个文化语境（出海帖） | 风险词表按 locale 切换没做 | locale → blocklist 路由表，同 post 多 locale 跑一遍取交集 |
| 生产 Reddit 频控策略简化 | 真量级流量会触限 | 加 token-bucket + per-subreddit budget；超限直接走 fallback fixtures |
| 候选数偏少（每风格 1） | 弱化了 selection 能力（见 §3 重构 #2） | 提到每风格 3-5；这是 ROI 最高的下一步 |
| Hook 配置变更没自动化 audit | hooks.config.yaml 改阈值靠 changelog 自律 | 加 git pre-commit 校验 changelog 强制 |
| evidence 日志 PII 处理 | 当前会把 LLM 输入裁剪 400 字 preview，但没主动 mask 邮箱/手机 | 加 PII redactor 层 |

如果让我用一句话评价当前系统的最大短板：**没有真实流量数据反馈** —— 我无法判断什么样的"神评论"在我们的目标平台真的有效。所有评分都是离线启发式。生产应该闭环：发布 → 测得 reply_per_upvote → 喂回 reference-mining 的"正样本"。
