# Three-Layer Agent Memory

> A filesystem-native, version-controllable **long-memory paradigm for AI agents**.
> 让智能体在长任务线里**不丢初心、不稀释记忆、能自我进化**。
>
> English abstract below · 正文以中文为主（与作者实际使用环境一致）。

**English abstract:** A minimal, framework-agnostic memory architecture for long-horizon AI agents. Memory is split by *stability* into three layers — **Surface** (stable tenets/philosophy/needs), **Middle** (timestamped task logs), **Deep** (agent metacognition & reflection). A small **recall/writeback protocol** binds when each layer is read and written. The Deep layer plus the rolling index forms a persisted self-improvement loop — the agent reads its own past reflections, mines recurring failure modes, and rewrites its tenets. Storage is plain Markdown on disk: human-readable, git-diffable, zero infrastructure. This repo contains the protocol spec, storage schema, template kit, integration guide, and a sanitized case study.

---

## 这是什么

一个**面向任意 AI agent 的通用长期记忆范式**。它把"记忆"从模型上下文里拿出来，落成磁盘上的纯 Markdown 三层结构，再用一套轻量协议规定 agent 何时读、何时写。

它不是数据库，不是 RAG，不是 vector store。它是**认知架构的最小可持久化形态**：

| 认知科学概念 | 本范式对应 | 物理形态 |
|---|---|---|
| 语义记忆（慢变事实/信念） | 表层 | `表层/00-项目总览.md` |
| 情景记忆（带时间戳的事件） | 中层 | `中层/YYYY-MM-DD_*.md` |
| 元认知（对自身的反思） | 深层 | `深层/AI深度思考.md` |
| 工作记忆初始化 | 开机必读协议 | recall 4 步 |
| 记忆巩固（睡眠期的回放/重写） | 阶段记中层 + 每天更新表层/深层 | writeback 3 步 |

## 为什么需要它

单次会话上下文有限，长任务线会被压缩、被遗忘。AI 会**丢失项目初心**、偏离方向、重复踩同一个坑、把"做了什么"复述得头头是道却给不出"结构性更优的路径"。

本范式用一个外部化的、按稳定性分层的记忆体对抗这件事。核心洞察是：

> **记忆要按"变不变"分层存放，而不是按"是什么"分类存放。**
> 越不容易变的东西越靠前读，越容易变的东西越靠后写、越频繁刷新。

## 三层结构

```
<project>/
├── 表层/                      # 稳定。开机读一眼找回初心。
│   ├── 00-项目总览.md         # 名称/目的/宗旨/哲学/需求/偏好/服务器指引/内容摘要/项目大纲
│   └── 01-待完成任务.md       # 高频更新，单独成文件
├── 中层/                      # 流水。每阶段任务一篇。
│   ├── INDEX-任务流水.md      # 时间线索引，新任务置顶插一行
│   └── YYYY-MM-DD_<版本或主题>_<简述>.md
└── 深层/                      # 反思。AI 高于人类常规认知的审视。
    └── AI深度思考.md           # 按日期分节追加，不拆文件、不删旧节
```

## 协议（agent 必须遵守的 3 个检查点）

1. **开机 / 任务开始** → recall：读表层总览 → 待办 → 中层最近 1–2 条 → 深层末尾。
2. **阶段任务完成** → writeback：在中层新建一篇任务记录，并在 INDEX 置顶插指针。
3. **每天结束 / 重大节点** → consolidate：更新表层待办与摘要，在深层**追加**一段反思（现状审视/优化方案/隐患/预期）。

详见 [`PROTOCOL.md`](PROTOCOL.md)。

## 自我进化机制

深层 + INDEX 构成一个**持久化的自我改进闭环**：agent 每次反思都追加进 `AI深度思考.md`，下次开机必读末尾。重复出现的隐患会被识别为结构性问题，进而推动表层宗旨/准则的更新。这就是 agent 的"进化"——不是改权重，而是改自己的**信念与行为准则**。

详见 [`EVOLUTION.md`](EVOLUTION.md)。

## 仓库内容

| 文件 | 作用 |
|---|---|
| [`PROTOCOL.md`](PROTOCOL.md) | 协议规范：recall / writeback / consolidate 三个检查点的完整规则 |
| [`SCHEMA.md`](SCHEMA.md) | 存储模式：目录布局、文件命名、字段约定 |
| [`PARADIGM.md`](PARADIGM.md) | 范式定位：为什么这是一套"程序范式"而非笔记模板 |
| [`EVOLUTION.md`](EVOLUTION.md) | 自我进化：深层反思闭环、隐患挖掘、准则更新机制 |
| [`INTEGRATION.md`](INTEGRATION.md) | 集成：如何接入 Claude Code / Cursor / 自研 agent，hook 契约 |
| [`_template/`](_template/) | 模板套件：复制即用，含三层骨架文件 |
| [`case-study.md`](case-study.md) | 脱敏案例：长任务线中三层记忆如何防止上下文漂移 |
| [`adapters/claude-code.md`](adapters/claude-code.md) | Claude Code 适配：auto-memory 指针 + skill + hooks |

## 快速开始

```bash
git clone https://github.com/cultwlpbmx/three-layer-agent-memory.git
cp -r three-layer-agent-memory/_template /path/to/your-project-memory
# 重命名目录为项目名，填写 表层/00-项目总览.md，开始记第一篇中层任务
```

让你的 agent 读 `PROTOCOL.md` 并遵守三个检查点即可。无需任何运行时依赖。

## 许可

MIT — 见 [`LICENSE`](LICENSE)。拿去用、改、卖，都行。如果你用它建了自己的 agent 记忆库，欢迎开 issue 留个链接。

## 来源

本范式从一个真实的长周期项目（家庭教育领域 AI agent，Flutter + FastAPI + MongoDB）里提炼而来——那个项目跑了数十个版本、横跨数月，靠这套结构在没有向量数据库、没有额外服务的情况下保持了方向锚。案例见 [`case-study.md`](case-study.md)（已脱敏）。