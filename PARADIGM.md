# 为什么这是一套"程序范式"

> 不是笔记模板，是智能体的认知架构。
> 本文回答用户的核心问题：**项目记忆库能不能做成一个程序范式，应用到 AI agent 的进化中？**
> 答案：能，而且它本质上已经是。本文把它从"一个人的笔记习惯"抽象成"可被任意 agent 实现的范式"。

## 1. 范式 vs 模板

模板是"填空"；范式是"规定计算如何发生的一组不变约束"。

本范式的不变约束有四条：

1. **记忆按稳定性分三层**（表层/中层/深层），而不是按主题分类。
2. **三个检查点**（recall / writeback / consolidate）规定 agent 何时读、何时写每一层。
3. **检索优先级**：记忆库 → 代码 → 问用户。
4. **深层只追加不删**，宗旨逐字保留且具有仲裁优先级。

只要一个 agent 满足这四条，它就"运行在本范式上"——无论它底层是 Claude、GPT、还是本地模型，无论它的记忆存本地 Markdown 还是远端对象存储。这四条约束就是范式的"接口"。

## 2. 与认知架构的对应

本范式是认知科学里**多重记忆系统**在 agent 上的最小可持久化实现：

| 认知系统 | 功能 | 本范式 |
|---|---|---|
| 语义记忆 | 慢变事实、信念、规则 | 表层（宗旨/哲学/偏好） |
| 情景记忆 | 带时间戳的具体事件 | 中层（任务流水，含 tags 联想索引） |
| 元认知 | 对自身思维的反思 | 深层（AI 深度思考） |
| 元认知边界 | 知道自己不知道什么 | 表层（未知与开放问题） |
| 工作记忆 | 当前活跃的上下文 | 模型上下文窗口 |
| 记忆巩固 | 睡眠期回放、重写、强化 | consolidate 检查点（含提炼） |
| 记忆压缩 | 旧情节记忆淡出，保留语义 | 中层归档机制 |
| 联想记忆 | 场景触发相关记忆 | 标签联想回溯（`--tag`） |
| 跨域记忆迁移 | A 领域经验迁移到 B | 全局深层库 |

关键差异在于：大多数 agent 框架把"记忆"等同于"往上下文里塞更多 token"（= 只用工作记忆）。本范式把记忆**外化**并**分层**，让工作记忆在每个检查点只装载它此刻需要的那一层。

## 3. 为什么外化 + 分层能对抗上下文污染

模型上下文有三个硬约束：窗口大小、注意力稀释、压缩遗忘。

- **窗口**：长任务必然超窗，超窗就被压缩，压缩就丢信息。
- **稀释**：塞进来的东西越多，每条信息的边际注意越低。
- **遗忘**：压缩不是智能选择，是机械截断，经常丢的恰好是"初心"。

本范式的解法不是"塞更多"，而是"**按需取更少、更准**"：
- recall 只取 4 个文件的关键节，不是整库。
- 检索按优先级走，能用 `file:line` 解决的不贴整段。
- 越稳定的越靠前读，保证"初心"总是最先被装载。

这等价于给 agent 一个**外部索引**：上下文窗口里只放索引项，正文留在磁盘上按需打开。

## 4. 作为"程序范式"意味着什么

一个范式要能被**实现**、被**移植**、被**演化**。本范式三者皆可：

- **实现**：见 `INTEGRATION.md` 的 hook 契约——`on_session_start` → recall，`on_milestone` → writeback，`on_day_end` → consolidate。任何支持 hook 的 agent 框架都能实现。
- **移植**：存储是纯 Markdown，不绑定任何框架。换 agent 只换 adapter，不换记忆体。
- **演化**：见下一节，以及 `EVOLUTION.md`。

把它叫"程序范式"还因为它**规定了数据流的形状**：

```
        ┌── recall (开机) ────────────────┐
        │                                  ▼
   磁盘记忆 ──► 工作记忆 ──► 行动 ──► 结果
        ▲                                  │
        └── writeback (阶段) / consolidate (天) ◄─┘
```

这是一个**有状态的闭环**，不是无状态的一问一答。闭环的存在使"进化"成为可能。

## 5. 它如何驱动 agent 的进化

"进化"在权重层面意味着改参数；在范式层面意味着**改自己的信念与行为准则**。本范式实现后者，且可追溯：

1. **持久化元认知**：深层 `AI深度思考.md` 把 agent 每次的反思永久落盘。
2. **反思被回读**：recall 第 4 步强制读深层末尾——agent 下次开工时**必须面对自己上次的判断**。
3. **重复隐患 → 准则更新**：同一个隐患在深层反复出现，说明它是结构性问题，应升级为表层"应用准则"。本范式把"准则"放在表层宗旨之下、逐字保留区之外，专门承接这种进化。
4. **不删旧节 = 思想化石层**：深层保留全部历史判断，可以追溯"我们为什么从 A 走到 B"。这是组织级的可审计智能。

这套闭环就是 agent 的进化机制：**反思 → 沉淀 → 回读 → 修正准则 → 新一轮反思**。权重没变，但 agent 的行为已经按它自己的历史经验优化了。详见 `EVOLUTION.md`。

## 6. 适用边界

本范式擅长：
- 长周期、多版本、会丢失上下文的项目（数周到数月）
- 多 session / 多 agent 接力的工作流
- 需要保留"我们为什么这么决定"的审计场景
- 有明确宗旨/哲学、需要锚定不偏航的产品

本范式不擅长：
- 一次性问答、短任务（开销大于收益）
- 纯检索型任务（用 vector RAG 更直接）
- 无文件系统访问的纯沙箱 agent（需要 adapter 改用远端存储）

它不与 RAG/向量检索冲突——后者解决"找相关知识"，本范式解决"保持方向与自我"。二者可叠加：本范式做顶层锚，RAG 做中层检索。
## 7. 目标阶梯（Aspiration Ladder）

本范式的长期目标是超越人类记忆的局限。为了让这个目标可检验而非口号，把它拆成六级阶梯——**目标是愿景，声明只限于已验证的事实**：

| Level | Name | Criterion | Status (2026-08-15) |
|---|---|---|---|
| L0 | Outlive agents | A new agent/model takes over correctly with zero human explanation | ✅ Verified ×3 (claude → codex → zcode/GLM) |
| L1 | Auditable | Any past decision can be reconstructed: what was known, why chosen | ◐ Partial |
| L2 | Errors guard the path | No forgetting, only classification: mistakes become boundaries that are actively recalled and periodically revisited | ◐ Prototype |
| L3 | Know its blind spots | Surfaces never-reflected dimensions, confirmed valuable by humans | ◐ Prototype |
| L4 | Calibrated self-prediction | Falsification rate measured; falsified predictions actually change rules | ◐ Prototype |
| L5 | Closed-loop self-revision | Reflection changes behavior without human relay — with permanent human veto & rollback | ❌ Not started (deliberately gated) |

**L2 in one sentence**: human memory's fatal flaw is that boundaries fade — "the scar heals and the pain is forgotten" — so mistakes repeat. This paradigm's answer: never delete a mistake, **reclassify it as a boundary**, actively recall it when the path approaches, and revisit it periodically so time never dilutes it. Demotion is not forgetting; demotion is a transfer from *directing* behavior to *guarding* behavior.

Rules: ladder levels only advance on one-off event evidence (not self-assessment), confirmed by a human. Claims of capability must always carry verification date and data.
