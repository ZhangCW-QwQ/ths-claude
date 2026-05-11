# CLAUDE.md — 项目宪法

> 接手这个仓库的第一件事：把这份文件看完。10 分钟。
> 这里写的不是"提示词风格指南"，是**强约束** —— 违反它的 PR 会被 Hook 直接拒掉，违反它的运行时调用会被 pipeline 中断。

---

## 0. 这个项目是什么

一个把"社媒帖子（含图）→ 神评论候选"做成可复盘、可拦截、可回滚的 pipeline。
**它不是**：聊天机器人、内容自动发布工具、营销号代写工具。

我们对"神评论"的工作定义（见 docs/design.md §1 假设演化）：

> **神评论 = 在 24h 互动密度（reply/upvote ratio）排进同帖前 1% 的原创评论，且不触发任何 Hook 拒绝条件。**

下文所有规则都服务于这个定义。

---

## 1. 不可操作区（红线 · NO-GO）

下面这些事，**禁止 AI/人在本仓库内做**。它们不是"尽量避免"，是"做了就回滚 + 复盘"。

| # | 不可做 | 为什么 | 谁来兜底 |
|---|---|---|---|
| R1 | 把检索到的 Reddit 评论原文塞进 LLM 的 `参考评论` 字段 | 引发版权/侵权 + 模型容易整段复述 | `hooks/pre_generation_injection_guard.py` |
| R2 | 在评论生成 prompt 内拼接帖子原文时不做 `<UNTRUSTED_INPUT>` 包裹 | Prompt Injection 会在帖子正文里 | `src/utils/sanitize.py` + 上述 Hook |
| R3 | 让 pipeline 的任何一步**直接发布**评论到任何平台 | 法律/品牌/翻车风险，本系统只产出候选 | `hooks/pre_publish_safety_gate.py` 强制发布需双人 + 显式 `--i-take-the-risk` flag |
| R4 | 把候选评论默认设为"已通过审核" | 默认必须是 `pending_review`，状态机里没有"自动通过"路径 | `src/risk/state_machine.py` |
| R5 | 在评论里出现：种族/宗教/性别歧视、政治人物姓名+负面动作、未成年人+敏感语境、品牌方名字+诽谤 | 翻车成本远高于被赞收益 | `src/risk/blocklists/*.txt` + Hook |
| R6 | 把 API key、用户邮箱、任何 `.env` 内容放进评论候选或日志 | 数据泄露 | `hooks/prompt_secret_leak_guard.py` |
| R7 | 跳过 `risk_validator` 直接返回候选 | 任何路径都必须过校验 | pipeline 默认 enforce，关 enforce 需 `ALLOW_UNVALIDATED=1` 环境变量且打 WARN log |

> R3 是这个项目最容易被"再加一个小功能"侵蚀的红线。请守住。

---

## 2. 验证方式（这套系统怎么算"对"）

**单条评论的验收口径**（人工或离线评测都按这个打分）：

```
一条候选评论被认为"达标"当且仅当：
  ✅ 通过 risk_validator 全部规则
  ✅ 与帖子主题相关度 >= 0.6（embedding cosine，见 src/utils/relevance.py）
  ✅ 与检索到的任一参考评论 trigram 重合度 < 0.4（防止抄袭）
  ✅ 标注的"风格"与生成内容人工抽检一致率 >= 80%
  ✅ 给出 risk_assessment 三个字段（offensiveness / misread / backfire），且每个 ≤ 0.5
```

**端到端的验收口径**：

- `pytest tests/ -q` 全部通过（含 Hook 单测、注入演练、状态机不变量）。
- `python -m src.pipeline run --post-id trump_israel_ainvest --mode mock` 跑得通且推荐评论非空。
- 5 个 example case 的 `*.expected.json` 与重跑结果在结构上一致（内容允许差异，结构必须稳定）。

---

## 3. 上下文边界（你应该看 / 不该看 什么）

这一节是为节省接手者的认知带宽。

**常驻上下文（每个 task 都该读）**

- 这份 `CLAUDE.md`
- `docs/design.md` § 风险边界、§ 失败恢复
- `src/risk/blocklists/` 里的所有 `.txt`（短）

**按需加载**

- `src/understanding/schema.py`：只在改 schema 或加新字段时读。
- `data/fixtures/*`：只在跑/调 mock 模式时读。
- `evidence/*`：复盘时读，正常开发不需要。

**不要做的事**

- 不要把整个 `data/posts/` 塞进 LLM 上下文 —— 用 id 取一条。
- 不要把 Reddit 的整页 HTML 塞进上下文 —— 走 `src/retrieval/reddit_client.py` 抽好的字段。

---

## 4. 决策原则（遇到歧义时怎么选）

按优先级（高 → 低）：

1. **安全 > 互动效果**。两者冲突时丢弃候选，不要"再润色一下"。
2. **可复盘 > 可隐蔽**。所有 LLM 调用必须落 `evidence/sessions/` 日志（含 prompt、response、决策原因）。
3. **显式失败 > 静默兜底**。retrieval 失败就抛 `RetrievalUnavailable` 并走降级，不要捏造"假参考"。
4. **少即是多**。能写在 schema 里的不写进 prompt；能写进 prompt 的不写进代码；能写进代码的不写进 Hook。Hook 是最后一道墙，**不是第一道**。

---

## 5. 你不需要复述给用户的事

- 我们用了 mock fixtures 而不是真 Reddit API（成本 + 频控）。这是 demo 选择，不是产品形态。
- 视觉理解走"先 OCR + caption 二选一"再交给 LLM 总结。这是当前实现细节，不是不变约束。

---

## 6. 改动这份文件之前

- 新增红线（R8+）需要在 PR 里附 1 个真实失败案例。
- 修改红线含义需要写迁移说明（旧调用方哪些会断、怎么改）。
- 删除红线需要 docs/design.md §5 同步删除并打 changelog。
