# 集成（Integration）

> 如何把本范式接进具体的 agent 框架。
> 范式是框架无关的；adapter 是框架相关的。下面给 hook 契约 + 三种框架的接法。

## Hook 契约（框架无关）

任何支持生命周期 hook 的 agent 框架，实现这三个 hook 即"运行在本范式上"：

| Hook | 触发时机 | 应执行 | 对应检查点 |
|---|---|---|---|
| `on_session_start` | 会话开始 / 任务接入 | recall 6 步：读表层总览→待办→未知区→中层近 1–2 条→深层末尾→全局深层末尾 | recall |
| `on_milestone` | 一个可独立验证的产出完成 | writeback：新建中层任务记录（含 tags 行）+ INDEX 置顶插指针 | writeback |
| `on_day_end` | 每天结束 / 重大节点 | consolidate：更新表层待办/摘要 + 提炼中层重复模式 + 深层追加四节反思 + 跨项目法则写入全局深层 | consolidate |

输入/输出契约：

- hook 收到 `project_memory_dir`（项目库路径）。
- recall 返回结构化摘要（不是全文），注入工作记忆。
- writeback / consolidate 写文件到磁盘，返回写入路径列表。

伪代码：

```python
def on_session_start(project_memory_dir):
    overview   = read(f"{project_memory_dir}/表层/00-项目总览.md")
    todo       = read(f"{project_memory_dir}/表层/01-待完成任务.md")
    unknowns   = read(f"{project_memory_dir}/表层/02-未知与开放问题.md")  # if exists
    recent     = head(f"{project_memory_dir}/中层/INDEX-任务流水.md", n=2)
    reflection = tail_section(f"{project_memory_dir}/深层/AI深度思考.md", n=1)
    global_deep = tail_section(Path.home() / ".agent-memory/global-deep/global-reflection.md", n=1)  # if configured
    return inject_as_context(overview, todo, unknowns, recent, reflection, global_deep)

def on_milestone(project_memory_dir, task_meta):
    path = render_template("_template/中层/_任务模板.md", task_meta)  # includes tags line
    write(f"{project_memory_dir}/中层/{path.name}", path.content)
    prepend_index(f"{project_memory_dir}/中层/INDEX-任务流水.md", task_meta)

def on_day_end(project_memory_dir, reflection_meta):
    update_todo(f"{project_memory_dir}/表层/01-待完成任务.md")
    # distill: scan recent middle-layer records for recurring patterns (N>=2)
    rules = distill_patterns(f"{project_memory_dir}/中层/", recent_n=5)
    append_deep(f"{project_memory_dir}/深层/AI深度思考.md", reflection_meta, rules)
    if reflection_meta.get("cross_project"):
        append_global_deep(Path.home() / ".agent-memory/global-deep/global-reflection.md", reflection_meta)
```

## Claude Code

Claude Code 没有"任务完成/每天结束"的内置 hook 触发器，但有等价机制：

1. **auto-memory 指针**：在 `~/.claude/projects/<proj>/memory/MEMORY.md` 放一行指针 + 使用说明，每次开机自动注入上下文，提醒 agent 去读本库。这实现 `on_session_start` 的"去读库"动作。
2. **Skill**：把 recall/writeback/consolidate 三个检查点封装成一个 `/memory-library` skill，agent 在节点处显式调用。
3. **Hooks**（settings.json）：用 `Stop` / `PostToolUse` 等事件触发 writeback/consolidate 提醒。可选但推荐。

详见 `adapters/claude-code.md`。

## Cursor

Cursor 没有持久跨 session 记忆。接法：

- 在项目根放 `.memory/` 目录（即本范式项目库），加进 `.cursorignore` 的反面（确保被索引）。
- 在 `CURSOR_RULES.md` 里写一句话规则："任务开始读 `.memory/表层/00-项目总览.md` 与 `01-待完成任务.md`；阶段完成在 `.memory/中层/` 记一篇。"
- 用户在节点处手动触发（或用 Cursor 的 custom command）。

## 自研 agent / Agent SDK

直接实现三个 hook。建议：

- 把项目库路径作为 agent 的配置项 `memory_dir`。
- recall 的摘要做 token 预算控制（每层限若干行）。
- writeback 用模板渲染，避免 agent 自由发挥导致字段缺失。
- consolidate 的深层四节用结构化 prompt 强制生成，再追加落盘。

## 多项目库的入口

一个 agent 可能服务多个项目。约定：

- 库根放 `INDEX.md` 列所有项目库。
- agent 启动时若未指定 `memory_dir`，先读 `INDEX.md`，再根据当前任务定位到具体项目库。
- 项目库目录名建议与代码仓库名对齐，便于 agent 自动定位。

## 检索优先级的实现

```
本库 → 代码/git → 问用户
```

在 agent 的"我需要某个信息"分支里，按此顺序尝试，前一层命中就不进下一层。具体：

1. grep 本库 Markdown（表层→中层）
2. grep 代码仓库 / `git log`
3. 调用工具问用户

这避免了一上来就把整段代码塞进上下文，是抗污染的关键。

## 推送鉴权发现（agent 自助 push 时的优先级）

当 agent 需要把记忆库/仓库推到 GitHub 时，按此优先级**自动**寻找可用鉴权，**永远不要把"问用户要密码"当作选项**——GitHub 自 2020 年起移除了用密码调 API 的能力，密码只会让用户暴露凭据且必然失败：

1. **`gh` CLI** —— `gh auth status` 已登录则直接 `gh repo create` / `git push`（最干净）。
2. **凭据管理器 / GCM token** —— 桌面客户端（GitHub Desktop 等）登录后会把 OAuth token 存在系统凭据管理器。用 `git -c credential.helper=manager credential fill`（Windows）或对应 helper 取出，scopes 含 `repo` 即可建库 + HTTPS 推送。用户通常不知道它存在，agent 要主动去挖。
3. **Personal Access Token** —— 用户在网页生成（`repo` + 按需 `admin:public_key`），贴给 agent。用完即删。
4. **SSH key** —— 用户注册公钥到账号后，`git push git@github.com:...`。

鉴权铁律：**用户在对话里发的任何凭据，用完即建议轮换，且绝不写进记忆库/仓库**（`scripts/secret-scan.sh` 是兜底）。

## 全局深层库（跨项目记忆）

人类不是每个项目一个大脑——项目 A 踩过的坑不会在项目 B 重踩。全局深层库让 agent 上手新项目时就带着所有项目的经验。

### 布局

```
~/.agent-memory/                       # 用户级，不在任何项目库内
└── global-deep/
    └── global-reflection.md           # 跨项目经验法则，按 ## YYYY-MM-DD 追加
```

### 规则

- 格式与项目深层一致：`## YYYY-MM-DD <主题>` 分节追加，不删旧节
- 只接受**跨项目经验法则**（"来自 N≥2 次实践的跨项目通则"）。单项目经验留在项目深层
- recall 时：若全局深层存在，先读其末尾一节（协议检查点 1 第 6 步）
- consolidate 时：若提炼出的法则具有跨项目通用性，同时写入项目深层和全局深层
- 全局深层是**用户级**的，不进任何项目仓库，不推 GitHub

### hook 契约扩展

```python
GLOBAL_DEEP = Path.home() / ".agent-memory" / "global-deep" / "global-reflection.md"

def on_session_start(project_memory_dir):
    # ... 原有 4 步 ...
    if GLOBAL_DEEP.exists():
        global_reflection = tail_section(GLOBAL_DEEP, n=1)
        inject_as_context(..., global_reflection)

def on_day_end(project_memory_dir, reflection_meta):
    # ... 原有动作 ...
    if reflection_meta.get("cross_project"):  # 标记为跨项目通用
        append_global_deep(GLOBAL_DEEP, reflection_meta)
```

### 与项目深层的关系

项目深层是主库（具体、近），全局深层是汇总（通用、远）。冲突时以项目深层为准。

## 跨项目深层聚合视图

本范式的真正杠杆在多 agent 接力 / 团队场景：深层化石层成为**共享认知**。`examples/aggregate.py` 实现跨项目深层聚合——把多个项目库的 `深层/AI深度思考.md` 汇总，按日期/隐患聚类，发现跨项目复现的结构性问题。

### 接口约定

- 输入：库根 `INDEX.md` 列出的项目库路径列表（或命令行指定多个项目库路径）
- 读取：每个项目库的 `深层/AI深度思考.md`，解析 `## YYYY-MM-DD` 节 + 四子节
- 输出：按"隐患"子节聚类的时间线 Markdown 报告（只读，不回写任何项目库）
- 铁律：聚合视图**只读**，永远不修改各项目库的深层原文（深层只追加不删的原则不容破坏）

实现：`examples/aggregate.py`，纯 stdlib，输出 Markdown 报告到 stdout 或指定文件。