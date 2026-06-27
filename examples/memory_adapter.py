#!/usr/bin/env python3
"""
Three-Layer Agent Memory — reference adapter.

A minimal, dependency-free, runnable implementation of the three protocol
checkpoints (see ../PROTOCOL.md). Wire your agent's lifecycle hooks to the
three subcommands and you are "running on the paradigm" — no framework lock-in.

  recall        <- on_session_start   load 4 recall files into working memory
  log           <- on_milestone       create a middle-layer task record + index pointer
  consolidate   <- on_day_end         append a deep-layer reflection (the evolution point)

Locale-aware: auto-detects Chinese layer dirs (表层/中层/深层) or English
(Surface/Middle/Deep). See ../SCHEMA.md "Localization".

Usage:
  python memory_adapter.py recall <memory_dir>

  python memory_adapter.py log <memory_dir> \
      --version V5.4.14 --summary "测试反馈修复" \
      --entry "用户反馈十项"

  python memory_adapter.py consolidate <memory_dir> \
      --topic "范式提取" \
      --review "整体判断…" \
      --plan "结构性更优的路径…" \
      --risk "还未爆但会爆的点…" \
      --forecast "若按当前轨迹，短/中期会发生什么…"

Exit codes: 0 success, 1 bad usage, 2 missing memory dir / files.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

# Force UTF-8 stdout/stderr — Windows consoles default to cp936/GBK and choke on
# the ⚠ / 中文 chars that legitimately appear in memory files.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# --- locale mapping ------------------------------------------------------------

# Chinese (canonical) -> English. Both directions supported at runtime.
ZH = {
    "surface": "表层",
    "middle": "中层",
    "deep": "深层",
    "overview": "00-项目总览.md",
    "todo": "01-待完成任务.md",
    "index": "INDEX-任务流水.md",
    "task_template": "_任务模板.md",
    "deep_file": "AI深度思考.md",
}
EN = {
    "surface": "Surface",
    "middle": "Middle",
    "deep": "Deep",
    "overview": "00-overview.md",
    "todo": "01-todo.md",
    "index": "INDEX-task-log.md",
    "task_template": "_task-template.md",
    "deep_file": "AI-deep-reflection.md",
}


def detect_locale(root: Path) -> dict:
    """Return the layer-name map for whichever locale this memory dir uses."""
    if (root / ZH["surface"]).is_dir():
        return ZH
    if (root / EN["surface"]).is_dir():
        return EN
    # fall back to Chinese (canonical) so error messages name expected dirs
    return ZH


def paths(root: Path, loc: dict) -> dict:
    s, m, d = root / loc["surface"], root / loc["middle"], root / loc["deep"]
    return {
        "overview": s / loc["overview"],
        "todo": s / loc["todo"],
        "index": m / loc["index"],
        "middle_dir": m,
        "deep_file": d / loc["deep_file"],
        "task_template": m / loc["task_template"],
    }


# --- checkpoint 1: recall -----------------------------------------------------

DEEP_SECTION_RE = re.compile(r"^## .+", re.MULTILINE)


def cmd_recall(args) -> int:
    root = Path(args.memory_dir)
    if not root.is_dir():
        print(f"error: memory dir not found: {root}", file=sys.stderr)
        return 2
    loc = detect_locale(root)
    p = paths(root, loc)

    def head(path: Path, n: int) -> str:
        if not path.exists():
            return f"[missing: {path.name}]"
        lines = path.read_text(encoding="utf-8").splitlines()
        return "\n".join(lines[:n])

    def tail_table(path: Path, n: int) -> str:
        """Last n data rows of the INDEX markdown table (skip header/separators)."""
        if not path.exists():
            return f"[missing: {path.name}]"
        rows = [
            ln for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip().startswith("|") and not set(ln.strip()) <= set("|- ")
        ]
        # drop the header row (first one left after separator filter)
        rows = [r for r in rows if not r.strip().startswith("| 日期") and "|----" not in r]
        return "\n".join(rows[-n:])

    def last_deep_section(path: Path) -> str:
        if not path.exists():
            return f"[missing: {path.name}]"
        text = path.read_text(encoding="utf-8")
        starts = [m.start() for m in DEEP_SECTION_RE.finditer(text)]
        if not starts:
            return "(no reflections yet)"
        s = starts[-1]
        return text[s:].rstrip()

    summary = f"""# Recall summary — {root.name} ({date.today()})

## [1/4] Surface overview ({p['overview'].name})
{head(p['overview'], 40)}

## [2/4] Surface todo ({p['todo'].name})
{head(p['todo'], 40)}

## [3/4] Middle recent (last 2 of {p['index'].name})
{tail_table(p['index'], 2)}

## [4/4] Deep last reflection ({p['deep_file'].name})
{last_deep_section(p['deep_file'])}
"""
    print(summary)
    print(
        "[recall] inject the above into working memory, then act. "
        "Retrieval priority: memory → code/git → ask user.",
        file=sys.stderr,
    )
    return 0


# --- checkpoint 2: writeback (log a milestone) --------------------------------

TASK_TEMPLATE = """# {date} {version} — {summary}

- **时间戳**：{date}（开始）→（结束）
- **版本/分支**：{version}
- **入口**：{entry}

## 任务清单
- [ ] <项 1>
- [ ] <项 2>

## 完成情况
- ✅ <完成了什么，附关键 file:line / 端点 / 版本号>
- ⚠️ <部分完成，说明卡在哪>
- ❌ <未完成，原因>

## 遇到的困难
- <踩坑、根因、绕过方式；写"真因"而非表象>

## 关键产出
- 代码改动：<file:line 级要点，不整段贴>
- 部署：<脚本名、服务器、版本号、验证结果>
- 验证：<analyze/编译/curl/真机 结果数字>

## 遗留与下一步
- [ ] <由此衍生的新待办，同步进表层 todo>

## 关联
- 相关旧记忆 / 上下层：[[...]]
"""

TASK_TEMPLATE_EN = """# {date} {version} — {summary}

- **Timestamp**: {date} (start) → (end)
- **Version/branch**: {version}
- **Entry**: {entry}

## Task checklist
- [ ] <item 1>
- [ ] <item 2>

## Done
- ✅ <what was done, with key file:line / endpoint / version>
- ⚠️ <partially done, where it stuck>
- ❌ <not done, why>

## Difficulties
- <pit, root cause, workaround; the *real* cause, not the symptom>

## Key output
- Code changes: <file:line level, no full pastes>
- Deploy: <script, server, version, verification>
- Verify: <analyze/compile/curl/device result numbers>

## Leftover & next
- [ ] <new todo derived, sync into surface todo>

## Links
- Related memory / layers: [[...]]
"""

INDEX_HEADER_RE = re.compile(r"^\| *日期 *\| *任务记录 *\|", re.MULTILINE)
INDEX_HEADER_RE_EN = re.compile(r"^\| *Date *\| *Task record *\|", re.MULTILINE)


def cmd_log(args) -> int:
    root = Path(args.memory_dir)
    if not root.is_dir():
        print(f"error: memory dir not found: {root}", file=sys.stderr)
        return 2
    loc = detect_locale(root)
    p = paths(root, loc)
    is_en = loc is EN

    today = date.today().isoformat()
    safe_summary = re.sub(r"[\\/:*?\"<>|]", "_", args.summary)
    fname = f"{today}_{args.version}_{safe_summary}.md"
    task_path = p["middle_dir"] / fname

    tmpl = TASK_TEMPLATE_EN if is_en else TASK_TEMPLATE
    content = tmpl.format(
        date=today, version=args.version, summary=args.summary, entry=args.entry
    )
    task_path.write_text(content, encoding="utf-8")

    # prepend a pointer row to the INDEX, right after the header separator
    idx_path = p["index"]
    if idx_path.exists():
        text = idx_path.read_text(encoding="utf-8")
        row = f"| {today} | `{fname}` | {args.summary} |\n" if not is_en else \
              f"| {today} | `{fname}` | {args.summary} |\n"
        # insert after the first |---| separator line
        m = re.search(r"^\|[-: |]+\|\s*$", text, re.MULTILINE)
        if m:
            insert_at = m.end()
            text = text[:insert_at] + "\n" + row + text[insert_at:]
        else:
            text = text.rstrip() + "\n" + row
        idx_path.write_text(text, encoding="utf-8")
    else:
        print(f"warn: index missing, task file still written: {task_path}", file=sys.stderr)

    print(f"[writeback] created {task_path}")
    print(f"[writeback] prepended pointer in {idx_path}")
    print("[writeback] fill in the task record, then sync leftover todos into surface todo.",
          file=sys.stderr)
    return 0


# --- checkpoint 3: consolidate (append a deep reflection) ---------------------

DEEP_SECTION_ZH = """## {date} {topic}

### 现状审视
{review}

### 优化方案
{plan}

### 隐患
{risk}

### 预期
{forecast}
"""

DEEP_SECTION_EN = """## {date} {topic}

### Status review
{review}

### Better path
{plan}

### Risks
{risk}

### Forecast
{forecast}
"""


def cmd_consolidate(args) -> int:
    root = Path(args.memory_dir)
    if not root.is_dir():
        print(f"error: memory dir not found: {root}", file=sys.stderr)
        return 2
    loc = detect_locale(root)
    p = paths(root, loc)
    is_en = loc is EN

    today = date.today().isoformat()
    section = (DEEP_SECTION_EN if is_en else DEEP_SECTION_ZH).format(
        date=today, topic=args.topic, review=args.review,
        plan=args.plan, risk=args.risk, forecast=args.forecast,
    )

    deep = p["deep_file"]
    if deep.exists():
        text = deep.read_text(encoding="utf-8").rstrip() + "\n\n" + section
    else:
        text = section
    deep.write_text(text, encoding="utf-8")

    print(f"[consolidate] appended reflection to {deep}")
    print(
        "[consolidate] now update surface todo (check off done, add new, reprioritize) "
        "and overview summary if there was real progress.",
        file=sys.stderr,
    )
    return 0


# --- CLI ----------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="memory_adapter",
        description="Three-Layer Agent Memory reference adapter (see PROTOCOL.md).",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("recall", help="on_session_start: load 4 recall files")
    pr.add_argument("memory_dir")
    pr.set_defaults(func=cmd_recall)

    pl = sub.add_parser("log", help="on_milestone: write a middle-layer task record")
    pl.add_argument("memory_dir")
    pl.add_argument("--version", required=True, help="e.g. V5.4.14 or backend")
    pl.add_argument("--summary", required=True, help="short description (filename-safe)")
    pl.add_argument("--entry", default="<本次工作起点>", help="what triggered this work")
    pl.set_defaults(func=cmd_log)

    pc = sub.add_parser("consolidate", help="on_day_end: append a deep reflection")
    pc.add_argument("memory_dir")
    pc.add_argument("--topic", required=True)
    pc.add_argument("--review", required=True, help="现状审视 / status review")
    pc.add_argument("--plan", required=True, help="优化方案 / better path")
    pc.add_argument("--risk", required=True, help="隐患 / risks")
    pc.add_argument("--forecast", required=True, help="预期 / forecast")
    pc.set_defaults(func=cmd_consolidate)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())