# 集成（Integration）

> 如何把本范式接进具体的 agent 框架。
> 范式是框架无关的；adapter 是框架相关的。下面给 hook 契约 + 三种框架的接法。

## Hook 契约（框架无关）

任何支持生命周期 hook 的 agent 框架，实现这三个 hook 即"运行在本范式上"：

| Hook | 触发时机 | 应执行 | 对应检查点 |
|---|---|---|---|
| `on_session_start` | 会话开始 / 任务接入 | recall 4 步：读表层总览→待办→中层近 1–2 条→深层末尾 | recall |
| `on_milestone` | 一个可独立验证的产出完成 | writeback：新建中层任务记录 + INDEX 置顶插指针 | writeback |
| `on_day_end` | 每天结束 / 重大节点 | consolidate：更新表层待办/摘要 + 深层追加四节反思 | consolidate |

输入/输出契约：

- hook 收到 `project_memory_dir`（项目库路径）。
- recall 返回结构化摘要（不是全文），注入工作记忆。
- writeback / consolidate 写文件到磁盘，返回写入路径列表。

伪代码：

```python
def on_session_start(project_memory_dir):
    overview   = read(f"{project_memory_dir}/表层/00-项目总览.md")
    todo       = read(f"{project_memory_dir}/表层/01-待完成任务.md")
    recent     = head(f"{project_memory_dir}/中层/INDEX-任务流水.md", n=2)
    reflection = tail_section(f"{project_memory_dir}/深层/AI深度思考.md", n=1)
    return inject_as_context(overview, todo, recent, reflection)

def on_milestone(project_memory_dir, task_meta):
    path = render_template("_template/中层/_任务模板.md", task_meta)
    write(f"{project_memory_dir}/中层/{path.name}", path.content)
    prepend_index(f"{project_memory_dir}/中层/INDEX-任务流水.md", task_meta)

def on_day_end(project_memory_dir, reflection_meta):
    update_todo(f"{project_memory_dir}/表层/01-待完成任务.md")
    append_deep(f"{project_memory_dir}/深层/AI深度思考.md", reflection_meta)
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