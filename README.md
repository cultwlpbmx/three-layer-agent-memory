# Three-Layer Agent Memory

> A filesystem-native, version-controllable **long-memory paradigm for AI agents**.
>
> [中文](README.md) | [English](README_EN.md)
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
| 情景记忆（带时间戳的事件） | 中层 | `中层/YYYY-MM-DD_*.md`（含 tags 联想索引） |
| 元认知（对自身的反思） | 深层 | `深层/AI深度思考.md` |
| 工作记忆初始化 | 开机必读协议 | recall 6 步 |
| 记忆巩固（睡眠期的回放/重写） | 阶段记中层 + 每天更新表层/深层 + **提炼重复模式** | writeback + consolidate |
| 记忆压缩/归档（防止膨胀） | 中层归档机制 | `中层/archive/`（超阈值压缩为摘要行） |
| 联想记忆（场景触发相关记忆） | 标签联想回溯 | `--tag` 参数按标签过滤 |
| 跨项目记忆迁移 | 全局深层库 | `~/.agent-memory/global-deep/` |
| 元认知边界（知道不知道什么） | 未知与开放问题 | `表层/02-未知与开放问题.md` |

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
│   ├── 01-待完成任务.md       # 高频更新，单独成文件
│   └── 02-未知与开放问题.md    # 认知缺口 + 开放问题（推荐，可选）
├── 中层/                      # 流水。每阶段任务一篇，含 tags 行（联想回溯）。
│   ├── INDEX-任务流水.md      # 时间线索引，新任务置顶插行
│   ├── YYYY-MM-DD_<版本或主题>_<简述>.md
│   ├── _任务模板.md           # 留作复制
│   └── archive/              # 归档区（超 20 篇后压缩为摘要行）
└── 深层/                      # 反思。AI 高于人类常规认知的审视。
    └── AI深度思考.md           # 按日期分节追加，不拆文件、不删旧节

~/.agent-memory/global-deep/   # 用户级，跨项目经验法则（不在任何项目库内）
└── global-reflection.md        # 新项目 recall 时先读，继承所有项目经验
```

## 协议（agent 必须遵守的 3 个检查点）

1. **开机 / 任务开始** → recall：读表层总览 → 待办 → 未知与开放问题（若有）→ 中层最近 1–2 条 → 深层末尾 → 全局深层末尾（若配置）。
2. **阶段任务完成** → writeback：在中层新建一篇任务记录（含 **agent 签名** + tags 行），并在 INDEX 置顶插指针。
3. **每天结束 / 重大节点** → consolidate：更新表层待办与摘要，**从中层提炼重复模式为经验法则**，在深层**追加**一段反思（含 agent 签名 + 现状审视/优化方案/隐患/预期）。若法则跨项目通用，同时写入全局深层。

详见 [`PROTOCOL.md`](PROTOCOL.md)。

## 自我进化机制

深层 + INDEX 构成一个**持久化的自我改进闭环**：agent 每次反思都追加进 `AI深度思考.md`，下次开机必读末尾。consolidate 时从中层任务记录里**提炼跨任务重复模式**（N≥2 才提炼），将其转化为经验法则。重复出现的隐患会被识别为结构性问题，进而推动表层宗旨/准则的更新。跨项目通用的法则写入全局深层，让新项目继承所有旧项目的经验。这就是 agent 的"进化"——不是改权重，而是改自己的**信念与行为准则**。

详见 [`EVOLUTION.md`](EVOLUTION.md)。

## 仓库内容

| 文件 | 作用 |
|---|---|
| [`PROTOCOL.md`](PROTOCOL.md) | 协议规范：recall / writeback / consolidate 三个检查点（含提炼协议） |
| [`SCHEMA.md`](SCHEMA.md) | 存储模式：目录布局、文件命名、字段约定、标签、归档、全局深层、本地化映射 |
| [`PARADIGM.md`](PARADIGM.md) | 范式定位：为什么这是一套"程序范式"而非笔记模板 |
| [`EVOLUTION.md`](EVOLUTION.md) | 自我进化：深层反思闭环、提炼规则、隐患挖掘、准则更新机制 |
| [`INTEGRATION.md`](INTEGRATION.md) | 集成：hook 契约 + 全局深层库 + 跨项目聚合 + 推送鉴权 |
| [`_template/`](_template/) | 模板套件（中文，canonical）：含表层/中层/深层 + 未知与开放问题 + archive |
| [`_template-en/](_template-en/) | 模板套件（英文，Surface/Middle/Deep + 02-unknowns） |
| [`three_layer_memory/`](three_layer_memory/) | **v0.5 Python library**：importable `Memory`/`recall`/`log`/`consolidate`/`init`/`snapshot`/`validate`，零依赖，`log`/`consolidate` 含 `agent` 签名参数 |
| [`examples/memory_adapter.py`](examples/memory_adapter.py) | CLI（5 分钟读懂的范式门面）：薄包装库，含 `recall --tag` 联想回溯 |
| [`examples/mcp_server.py`](examples/mcp_server.py) | **v0.5 MCP server**：7 个 tool，任何 MCP client 零代码接入，跨 agent 共享同一份记忆，含 agent 签名 |
| [`examples/aggregate.py`](examples/aggregate.py) | 跨项目深层聚合 CLI：只读报告，按时间线/隐患/跨项目重复主题聚类 |
| [`scripts/secret-scan.sh`](scripts/secret-scan.sh) | 推送前密钥扫描（防止把真实密钥推公开） |
| [`.github/workflows/secret-scan.yml`](.github/workflows/secret-scan.yml) | 可选 CI：每次 push/PR 自动跑密钥扫描 |
| [`case-study.md`](case-study.md) | 脱敏案例：长任务线中三层记忆如何防止上下文漂移 |
| [`adapters/claude-code.md`](adapters/claude-code.md) | Claude Code 适配：auto-memory 指针 + skill + hooks |

## 适用边界 / Boundaries

本范式擅长：
- 长周期、多版本、会丢失上下文的项目（数周到数月）
- 多 session / 多 agent 接力的工作流
- 需要保留"我们为什么这么决定"的审计场景
- 有明确宗旨/哲学、需要锚定不偏航的产品

本范式不擅长：
- 一次性问答、短任务（开销大于收益）
- 纯检索型任务（用 vector RAG 更直接）
- 无文件系统访问的纯沙箱 agent（需要 adapter 改用远端存储）

**诚实的边界**：本范式只强制**机制**（何时读/写哪一层、用哪个模板），**不强制反思质量**。深层四节写得多深，取决于模型反思能力——**模型越弱，进化越慢**。弱模型会把深层写成流水账，进化闭环退化为"记日记"。提炼协议（N≥2 才提炼、证据链强制）是对策，但不是根治——它防"随意提炼"，不防"提炼不出"。它不与 RAG/向量检索冲突——后者解决"找相关知识"，本范式解决"保持方向与自我"，可叠加。全局深层、标签、归档、未知区都是**可选增强**，核心四条不变约束不变。

## 快速开始

### 方式 A：Python library（一行接入任何 Python agent）

```bash
git clone https://github.com/cultwlpbmx/three-layer-agent-memory.git
cd three-layer-agent-memory
pip install -e .            # 零运行时依赖
```

```python
from three_layer_memory import Memory, init, snapshot

# 一键建库（从模板脚手架）
init("/path/to/my-project-memory", locale="zh")

# agent 上来一行拿到三问答案 + 完整上下文
m = Memory("/path/to/my-project-memory")
r = m.recall()                      # on_session_start → {overview, todo, unknowns, recent_middle, last_deep, ...}
print(r.as_prompt_block())           # 注入模型 context

# 阶段完成记中层（文件名唯一，多 agent 并发零碰撞）
m.log(version="V0.1", summary="first task", tags=("#auth", "#deploy"))

# 天结束追加深层反思（append-only，原子追加）
m.consolidate(topic="kickoff", review="...", plan="...", risk="...", forecast="...", agent="claude-code")

# 校验 + 可视化快照
print(m.validate())                 # schema 校验
snapshot("/path/to/...", "out.html")  # 单页 HTML，浏览器直开
```

三个基本问题（这项目是什么 / 走到哪 / 下一步）已由 `recall()` 的 `overview` + `todo` + `last_deep` 回答——不需要单独的 brief。

### 方式 B：MCP server（跨 agent + 跨模型共享同一份记忆）

```bash
pip install -e ".[mcp]"            # 装 mcp 可选依赖
python examples/mcp_server.py       # stdio MCP server
```

任何 MCP client（Claude Desktop / Cursor / Codex / Windsurf / Cline）在 MCP 配置加一行就接上：

```json
{
  "mcpServers": {
    "three-layer-agent-memory": {
      "command": "python",
      "args": ["<path-to-repo>/examples/mcp_server.py"]
    }
  }
}
```

7 个 tool：`three_layer_recall` / `_log` / `_consolidate` / `_snapshot` / `_init` / `_validate` / `_aggregate`。
**agent 和模型都是过客，记忆是常驻**——切 agent 不丢记忆，这是 Mem0/Letta（per-agent runtime）结构上做不了的事。

### 方式 C：CLI（5 分钟能读懂的范式门面）

```bash
python examples/memory_adapter.py init /path/to/my-project-memory --locale zh
python examples/memory_adapter.py recall /path/to/my-project-memory --budget 2000
python examples/memory_adapter.py log /path/to/my-project-memory --version V0.1 --summary "first task" --tags "#auth #deploy"
python examples/memory_adapter.py consolidate /path/to/my-project-memory --topic "..." --review "..." --plan "..." --risk "..." --forecast "..."
python examples/memory_adapter.py validate /path/to/my-project-memory
python examples/memory_adapter.py snapshot /path/to/my-project-memory out.html
```

### 并发写入协调（结构本身已解决）

多 agent 同时写记忆库不用锁——靠设计消解：
- 中层任务记录唯一命名（date+version+summary）→ 多 agent 并发写零碰撞
- 深层 append-only → 原子追加安全
- 表层 todo by design 只由 consolidate 单写者改（agent 在中层提议，consolidate 合并）
- recall 读最近 INDEX = 隐式协调（agent 知道别人刚做了什么）

可选 `Memory.claim()` 锁是 escape hatch，v0.5 是 stub，等真实并发冲突了 v0.6 再实现。

### 配置全局深层（跨项目记忆）

```bash
mkdir -p ~/.agent-memory/global-deep
echo "# Global reflection" > ~/.agent-memory/global-deep/global-reflection.md
# recall 会自动读末尾一节，consolidate 可写跨项目法则
```

### 推送前密钥扫描

```bash
./scripts/secret-scan.sh   # 确认没把真实密钥写进库
```

## 目标与已验证（Aspiration vs Verified）

本项目的长期目标是**超越人类记忆的局限**。为了诚实地区分"想去哪"和"到了哪"，我们把目标拆成六级阶梯（详见 [EVOLUTION.md](EVOLUTION.md)）：

| 级 | 名称 | 状态（2026-08-15） |
|---|---|---|
| L0 | 不灭——换 agent/模型无需人类解释即可接手 | ✅ 已验证 ×3 |
| L1 | 可审计——任一决策可还原当时所知与理由 | ◐ 部分达成 |
| L2 | 以错导正——错误转为边界，主动调出+定期回访 | ◐ 雏形 |
| L3 | 自知盲区 | ◐ 雏形 |
| L4 | 预言自己——证伪率可测且证伪真实改准则 | ◐ 雏形 |
| L5 | 闭环自转（保留人类否决权） | ❌ 未启动 |

核心主张（L2）：**记忆没有遗忘，只有分类**。人类的弱点是好了伤疤忘了痛——边界随时间稀释，错误重演。本范式的回答：错误不被删除，而是转岗为边界；在相关场景被主动调出；被定期回访。降级不是遗忘，是从"指导行为"转为"守护行为"。

### 已验证案例：跨模型冷启动接手（L0，2026-08-15）

第三个模型家族（zcode / GLM-5.3，此前从未接触本项目）在只给记忆库路径、零人工解释的情况下：读完三层记忆 → 定位表层过期三周、待办自相矛盾、归档从未执行等问题 → 遵守范式规则完成修复（未动逐字保留区、归档而非删除、深层只追加）→ 修复公开仓库与同步代码中的真实 bug。整个接手的上下文 **100% 来自记忆库**。这是"agent 过客、记忆常驻"的第三次验证，也是首次跨模型验证。

## 商业化

本项目提供云端服务，让 AI agent 跨设备、跨 agent 共享记忆：

| 功能 | 免费 | Pro ¥9.9/月（¥99/年） | Team ¥49/月（¥499/年） |
|---|---|---|---|
| 本地库 + CLI | ✅ | ✅ | ✅ |
| GitHub 代码仓库 | ✅ | ✅ | ✅ |
| OSS 云端同步 | ❌ | ✅ | ✅ |
| 自动同步（agent 无感知） | ❌ | ✅ | ✅ |
| Web 控制台 | ❌ | ✅ | ✅ |
| MCP server | 本地 | ✅ | ✅ |
| 多用户协作 | ❌ | ❌ | ✅ |
| 跨项目知识迁移 | ❌ | ❌ | ✅ |
| 元元认知 + 预测验证 | ❌ | ❌ | ✅ |
| 项目数 | 3 | 20 | 无限 |
| 存储空间 | - | 2GB | 10GB |

**使用方式**：

```python
from three_layer_memory import Memory
from three_layer_memory.auto_sync import AutoSync

# 免费用户（本地）
m = Memory("/path/to/project-memory")
r = m.recall()

# Pro 用户（云端同步）
m = AutoSync(Memory("/path/to/project"),
    api_key="tlam_sk_xxxx",
    device_id="my-laptop")
r = m.recall()    # 自动 pull
m.log(...)        # 自动 push
```

**控制台**：[wlpworld.com](https://wlpworld.com) （已备案：宁ICP备2025010683号-5，全站 HTTPS）

**核心哲学**：记忆即是认知，认知即是记忆。我们卖的不是存储，是认知资产——让认知跨设备/跨 agent 持久化。

## 许可

MIT — 见 [`LICENSE`](LICENSE)。如果你用它建了自己的 agent 记忆库，欢迎开 issue 留个链接。

## 来源

本范式从一个真实的长周期项目（家庭教育领域 AI agent，Flutter + FastAPI + MongoDB）里提炼而来——那个项目跑了数十个版本、横跨数月，靠这套结构在没有向量数据库、没有额外服务的情况下保持了方向锚。案例见 [`case-study.md`](case-study.md)（已脱敏）。