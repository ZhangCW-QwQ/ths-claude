# Skills

每个子目录是一个 Skill。Skill 不是 prompt —— Skill 是一个**可复用的工作流**，包含：

- 触发条件（什么时候启用这个 Skill）
- 输入契约（必需 / 可选 / 不准带）
- 步骤（人 / AI 都能照做）
- 输出模板（schema 化）
- 失败回退（每一步可能怎么挂、挂了怎么办）

| Skill | 用途 |
|---|---|
| [post-understanding](./post-understanding) | 把一条多模态帖子转成 PostUnderstanding |
| [reference-mining](./reference-mining) | 在 Reddit 检索高互动评论并抽"套路" |
| [comment-crafting](./comment-crafting) | 基于 understanding + 套路，生成多风格候选 |
| [risk-validation](./risk-validation) | 对候选做 5 层校验、给出推荐 |

> 所有 Skill 必须显式列出"失败回退"。没有这一节的 Skill PR 会被拒。
