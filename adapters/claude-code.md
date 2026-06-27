# Adapter: Claude Code

> 把本范式接进 Claude Code 的最小可行方式。
> Claude Code 没有"任务完成/每天结束"的内置触发器，但有三种等价机制组合实现三个检查点。

## 机制映射

| 协议检查点 | Claude Code 实现 |
|---|---|
| recall（开机） | auto-memory `MEMORY.md` 放指针 + 使用说明（自动注入）→ 提醒 agent 读库 |
| writeback（阶段完成） | `/memory-library` skill 显式调用；可选 `Stop` hook 提醒 |
| consolidate（天结束） | `/memory-library` skill；可选 `Stop` hook + 日程提醒 |

## 1. auto-memory 指针（实现 recall）

在 `~/.claude/projects/<proj>/memory/MEMORY.md` 顶部放指针块：

```markdown
# Project Memory Index

> ⚠️ 开机必读 —— 桌面三层长记忆库
> 结构化三层长记忆在：<项目记忆库根路径>
> 使用说明见该库 README.md；总索引 INDEX.md 列所有项目库。
> 协议：任务开始先读该项目 表层/00-项目总览.md + 01-待完成任务.md
>       + 中层/INDEX-任务流水.md 近况 + 深层/AI深度思考.md 末尾；
>       阶段完成在中层记一篇；每天结束更新表层并追加深层思考。
> 可调用 /memory-library skill 加载完整协议。

- [项目记忆库](project-memory-library.md) — 桌面三层长记忆库位置与协议（开机必读指针）
```

auto-memory 每次开机自动注入，agent 看到"开机必读"就会去读库。这完成了 recall 的"触发去读"动作；实际读哪几个文件由 `PROTOCOL.md` 检查点 1 规定。

## 2. Skill（实现 writeback / consolidate）

把三个检查点封装成 `memory-library` skill（`~/.claude/skills/memory-library/SKILL.md`）。skill 内容要点：

- **触发**：用户开始项目任务、完成一个阶段、或结束一天时调用。
- **recall 分支**：读 4 个文件，输出结构化摘要。
- **writeback 分支**：从 `_任务模板.md` 复制，填字段，落盘，INDEX 置顶插指针。
- **consolidate 分支**：更新表层待办/摘要，深层追加四节（现状审视/优化方案/隐患/预期）。

skill 让 agent 在节点处**一次调用完成纪律**，而不是靠记得"现在该写中层了"。

## 3. Hooks（可选但推荐，强制纪律）

在 `~/.claude/settings.json` 用 `Stop` hook 在会话结束时提醒：

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo '【记忆纪律】若本次完成了一个可验证产出 → 调 /memory-library 记中层；若是天结束/重大节点 → 更新表层+追加深层。'"
          }
        ]
      }
    ]
  }
}
```

`Stop` hook 的输出会回到 agent，作为"该不该写记忆"的提醒。这把"靠自觉"升级成"系统提醒"。详见 Claude Code hooks 文档。

> 用 `update-config` skill 可帮你写入 settings.json，而不必手改。

## 4. 与 auto-memory 的并行关系

- **auto-memory（MEMORY.md）**：细粒度单点事实，一条一事，自动注入。
- **三层库（桌面）**：结构化长记忆，按需读取，不自动注入。
- 两套并行，宗旨/哲学/方向以三层库表层为准，冲突在三层库勘误。

不要把三层库的内容塞进 auto-memory——那会污染自动注入的上下文。auto-memory 只放**指针**，正文留在三层库。

## 5. 快速接入清单

- [ ] 在桌面建项目记忆库根（复制 `_template/`）
- [ ] 在 auto-memory `MEMORY.md` 放指针块
- [ ] 安装 `/memory-library` skill
- [ ] （可选）配 `Stop` hook 做纪律提醒
- [ ] 第一次开工：执行 recall 4 步，记第一篇中层，追加深层首节