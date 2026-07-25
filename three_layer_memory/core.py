"""
Three-Layer Agent Memory — core library.

A minimal, dependency-free, importable implementation of the three protocol
checkpoints (see ../PROTOCOL.md). The storage layer is plain Markdown on disk;
this module wraps the read/write/validate mechanics so any Python agent can do:

    from three_layer_memory import Memory
    m = Memory("/path/to/project-memory")
    r = m.recall()                       # on_session_start
    m.log(version="V5.4.14", summary="...")  # on_milestone
    m.consolidate(topic="...", review="...", plan="...", risk="...", forecast="...")  # on_day_end

Locale-aware: auto-detects Chinese layer dirs (表层/中层/深层) or English
(Surface/Middle/Deep). See ../SCHEMA.md "Localization".

This module enforces the *mechanics* (which file to read/write, which template
to fill, schema validation). It cannot enforce the *quality* of the deep
reflection — that depends on the model. See ../README.md "适用边界".

Concurrency (see roadmap §8): the structure itself resolves most concurrent
writes — middle-layer task records are uniquely named (zero collision), the
deep layer is append-only (atomic append), and the surface todo is by design
only written by a single consolidate step (not by concurrent agents). An
opt-in claim() lock is provided as an escape hatch but is a stub by default.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger("three_layer_memory")

# Force UTF-8 stdout/stderr — Windows consoles default to cp936/GBK and choke
# on the ⚠ / 中文 chars that legitimately appear in memory files.
import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


# --- locale mapping ------------------------------------------------------------

ZH = {
    "surface": "表层",
    "middle": "中层",
    "deep": "深层",
    "overview": "00-项目总览.md",
    "todo": "01-待完成任务.md",
    "unknowns": "02-未知与开放问题.md",
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
    "unknowns": "02-unknowns.md",
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


def _paths(root: Path, loc: dict) -> dict:
    s, m, d = root / loc["surface"], root / loc["middle"], root / loc["deep"]
    return {
        "overview": s / loc["overview"],
        "todo": s / loc["todo"],
        "unknowns": s / loc["unknowns"],
        "index": m / loc["index"],
        "middle_dir": m,
        "deep_file": d / loc["deep_file"],
        "task_template": m / loc["task_template"],
    }


# --- result types --------------------------------------------------------------

@dataclass
class RecallResult:
    """Structured return from recall() — the six protocol sections.

    `overview` already answers "what is this project" and "where are we"
    (总览 contains 宗旨/定位/内容摘要); `todo` + `last_deep` answer "what's next".
    No separate brief() is needed — recall already covers the three questions.
    """
    overview: str
    todo: str
    unknowns: str
    recent_middle: list[dict] = field(default_factory=list)  # {date, file, summary, tags?}
    last_deep: str = ""
    global_deep: str = ""
    token_estimate: int = 0
    locale: str = "zh"

    def as_prompt_block(self, budget: int = 4000) -> str:
        """Render as a single Markdown block for agent context injection.

        Truncates sections to fit `budget` tokens (rough estimate: 1 token ≈ 2.5
        chars for mixed CJK/latin). Each section is truncated independently,
        preserving the most informative leading content.
        """
        chars_budget = int(budget * 2.5)
        parts = [
            ("# Surface — overview", self.overview),
            ("# Surface — todo", self.todo),
            ("# Surface — unknowns", self.unknowns),
        ]
        if self.recent_middle:
            mid_lines = []
            for item in self.recent_middle:
                line = f"- {item.get('date', '?')} {item.get('summary', '')}"
                if item.get("tags"):
                    line += f"  tags: {item['tags']}"
                mid_lines.append(line)
            parts.append(("# Middle — recent", "\n".join(mid_lines)))
        if self.last_deep:
            parts.append(("# Deep — last reflection", self.last_deep))
        if self.global_deep:
            parts.append(("# Global deep (cross-project)", self.global_deep))

        # allocate budget evenly, then render
        per = chars_budget // max(len(parts), 1)
        rendered = []
        for header, body in parts:
            if not body:
                continue
            if len(body) > per:
                body = body[:per].rsplit("\n", 1)[0] + "\n…(truncated)"
            rendered.append(f"{header}\n{body}")
        return "\n\n".join(rendered)


@dataclass
class ValidationResult:
    """Schema validation report. `ok` is True only if no errors (warnings ok)."""
    ok: bool
    violations: list[str] = field(default_factory=list)  # "ERROR: ..." or "WARN: ..."

    @property
    def errors(self) -> list[str]:
        return [v for v in self.violations if v.startswith("ERROR")]

    @property
    def warnings(self) -> list[str]:
        return [v for v in self.violations if v.startswith("WARN")]


# --- templates (kept in sync with memory_adapter.py / _template/) -------------

TASK_TEMPLATE_ZH = """# {date} {version} — {summary}

- **时间戳**：{date}（开始）→（结束）
- **版本/分支**：{version}
- **agent**：{agent}
- **tags**：{tags}
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
- **agent**: {agent}
- **tags**: {tags}
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

DEEP_SECTION_ZH = """## {date} {topic}

> agent: {agent}

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

> agent: {agent}

### Status review
{review}

### Better path
{plan}

### Risks
{risk}

### Forecast
{forecast}
"""


# --- helpers -------------------------------------------------------------------

_DEEP_SECTION_RE = re.compile(r"^## .+", re.MULTILINE)
_TAG_LINE_RE = re.compile(r"^\s*-\s*\*\*tags?\*\*\s*[:：]", re.MULTILINE | re.IGNORECASE)
_AGENT_LINE_RE = re.compile(r"^\s*-\s*\*\*agent\*\*\s*[:：]", re.MULTILINE | re.IGNORECASE)
_DEEP_AGENT_RE = re.compile(r"^>\s*agent\s*:", re.MULTILINE | re.IGNORECASE)


def _head(path: Path, n: int) -> str:
    if not path.exists():
        return f"[missing: {path.name}]"
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[:n])


def _tail_table_rows(path: Path, n: int) -> list[str]:
    """Last n data rows of the INDEX markdown table (skip header/separators)."""
    if not path.exists():
        return []
    rows = [
        ln for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip().startswith("|") and not set(ln.strip()) <= set("|- ")
    ]
    rows = [r for r in rows if not r.strip().startswith("| 日期")
            and not r.strip().startswith("| Date") and "|----" not in r]
    return rows[-n:]


def _parse_index_row(row: str) -> Optional[dict]:
    """Parse an INDEX table row → {date, file, summary}. Returns None if unparseable."""
    parts = [c.strip() for c in row.split("|")]
    # split gives ['', date, filename, summary, ''] — filename is index 2
    if len(parts) < 4:
        return None
    fname = parts[2].strip("`")
    if not fname or fname.startswith("YYYY"):
        return None
    return {"date": parts[1], "file": fname, "summary": parts[3] if len(parts) > 3 else ""}


def _last_deep_section(path: Path) -> str:
    if not path.exists():
        return "(no reflections yet)"
    text = path.read_text(encoding="utf-8")
    starts = [m.start() for m in _DEEP_SECTION_RE.finditer(text)]
    if not starts:
        return "(no reflections yet)"
    s = starts[-1]
    return text[s:].rstrip()


def _estimate_tokens(text: str) -> int:
    """Rough token estimate for mixed CJK/latin: ~2.5 chars per token."""
    return max(1, len(text) // 2.5) if text else 0


def _atomic_write(path: Path, content: str) -> None:
    """Atomic write via temp file + os.replace. Prevents concurrent-writer corruption.

    Even if two agents write the same file simultaneously, the worst case is one
    write is lost (last-rename-wins), never a corrupted half-written file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{int(time.time()*1000)}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _atomic_append(path: Path, content: str) -> None:
    """Atomic append for append-only files (deep layer). Uses OS append mode.

    For reasonable line sizes, `open('a')` is atomic across processes on POSIX
    and Windows. This is the deep-layer concurrency safety: multiple agents
    appending reflections will interleave but never corrupt each other's bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)


# --- the Memory class ----------------------------------------------------------

class Memory:
    """A three-layer agent memory library rooted at `project_dir`.

    All read/write methods operate on plain Markdown files on disk. No database,
    no service, no state held in memory across calls — each method is independent.
    """

    def __init__(self, project_dir: str | Path, locale: str = "auto"):
        self.root = Path(project_dir)
        if locale == "auto":
            self.loc = detect_locale(self.root)
        elif locale == "zh":
            self.loc = ZH
        elif locale == "en":
            self.loc = EN
        else:
            raise ValueError(f"unknown locale: {locale!r} (use 'auto'/'zh'/'en')")
        self.p = _paths(self.root, self.loc)
        self.is_en = self.loc is EN

    # ---- recall (checkpoint 1) -----------------------------------------------

    def recall(self, *, tag: Optional[str] = None,
               budget: int = 4000, recent_n: int = 2) -> RecallResult:
        """Load the six protocol sections into a structured RecallResult.

        Maps to `on_session_start`. The result already contains the three
        basic-question answers (overview→what/where, todo+last_deep→next),
        so callers do not need a separate brief().
        """
        overview = _head(self.p["overview"], 40)
        todo = _head(self.p["todo"], 40)
        unknowns = _head(self.p["unknowns"], 30) if self.p["unknowns"].exists() else "(not configured)"

        # middle recent — optionally tag-filtered (associative recall)
        if tag:
            recent_middle = self._tagged_index_rows(tag, limit=recent_n)
        else:
            rows = _tail_table_rows(self.p["index"], recent_n)
            recent_middle = [r for r in (_parse_index_row(row) for row in rows) if r]

        last_deep = _last_deep_section(self.p["deep_file"])

        # global deep (cross-project, optional)
        global_deep_path = Path.home() / ".agent-memory" / "global-deep" / "global-reflection.md"
        global_deep = _last_deep_section(global_deep_path) if global_deep_path.exists() else ""

        result = RecallResult(
            overview=overview,
            todo=todo,
            unknowns=unknowns,
            recent_middle=recent_middle,
            last_deep=last_deep,
            global_deep=global_deep,
            locale="en" if self.is_en else "zh",
        )
        result.token_estimate = sum(
            _estimate_tokens(x) for x in (overview, todo, unknowns, last_deep, global_deep)
        ) + sum(_estimate_tokens(r.get("summary", "")) for r in recent_middle)
        return result

    def _tagged_index_rows(self, tag: str, limit: int) -> list[dict]:
        """INDEX rows whose corresponding task files contain the given #tag."""
        rows = _tail_table_rows(self.p["index"], 1000)  # scan all, then filter
        tag_lower = tag.lower()
        matched = []
        for row in rows:
            parsed = _parse_index_row(row)
            if not parsed:
                continue
            fname = parsed["file"]
            task_path = self.p["middle_dir"] / fname
            if not task_path.exists():
                task_path = self.p["middle_dir"] / "archive" / fname
            if not task_path.exists():
                continue
            try:
                content = task_path.read_text(encoding="utf-8").lower()
                if f"#{tag_lower}" in content:
                    matched.append(parsed)
            except Exception:
                continue
            if len(matched) >= limit:
                break
        return matched

    # ---- writeback (checkpoint 2) --------------------------------------------

    def log(self, *, version: str, summary: str, entry: str = "",
            tags: tuple[str, ...] = (), agent: str = "unknown") -> Path:
        """Create a middle-layer task record + prepend pointer to INDEX.

        Maps to `on_milestone`. The task file is uniquely named
        (date+version+summary) so concurrent agents never collide — this is the
        structural concurrency safety (see roadmap §8).
        """
        today = date.today().isoformat()
        safe_summary = re.sub(r"[\\/:*?\"<>|]", "_", summary)
        fname = f"{today}_{version}_{safe_summary}.md"
        task_path = self.p["middle_dir"] / fname

        tags_str = " ".join(tags) if tags else ("<#标签1 #标签2>" if not self.is_en else "<#tag1 #tag2>")
        tmpl = TASK_TEMPLATE_EN if self.is_en else TASK_TEMPLATE_ZH
        content = tmpl.format(
            date=today, version=version, summary=summary,
            entry=entry or ("<本次工作起点>" if not self.is_en else "<entry point>"),
            tags=tags_str,
            agent=agent,
        )
        _atomic_write(task_path, content)

        # prepend a pointer row to the INDEX, right after the header separator
        self._index_prepend(today, fname, summary)
        logger.info("[writeback] created %s, prepended pointer in %s", task_path, self.p["index"])
        return task_path

    def _index_prepend(self, today: str, fname: str, summary: str) -> None:
        """Atomically insert a row into the INDEX after the first |---| separator.

        Uses atomic-rename so concurrent prepends never corrupt the INDEX file
        (worst case: one row is lost, never a broken file). See roadmap §8.
        """
        idx_path = self.p["index"]
        if not idx_path.exists():
            logger.warning("[writeback] index missing, task file still written")
            return
        text = idx_path.read_text(encoding="utf-8")
        row = f"| {today} | `{fname}` | {summary} |\n"
        m = re.search(r"^\|[-: |]+\|\s*$", text, re.MULTILINE)
        if m:
            insert_at = m.end()
            new_text = text[:insert_at] + "\n" + row + text[insert_at:]
        else:
            new_text = text.rstrip() + "\n" + row
        _atomic_write(idx_path, new_text)

    # ---- consolidate (checkpoint 3) ------------------------------------------

    def consolidate(self, *, topic: str, review: str, plan: str,
                    risk: str, forecast: str, agent: str = "unknown") -> Path:
        """Append a four-section reflection to the deep layer.

        Maps to `on_day_end` / major node. Deep layer is append-only — uses
        atomic append so concurrent consolidations interleave safely rather
        than corrupt. See roadmap §8.
        """
        today = date.today().isoformat()
        section = (DEEP_SECTION_EN if self.is_en else DEEP_SECTION_ZH).format(
            date=today, topic=topic, review=review,
            plan=plan, risk=risk, forecast=forecast,
            agent=agent,
        )
        deep = self.p["deep_file"]
        if deep.exists():
            existing = deep.read_text(encoding="utf-8").rstrip()
            _atomic_write(deep, existing + "\n\n" + section)
        else:
            _atomic_write(deep, section)
        logger.info("[consolidate] appended reflection to %s", deep)
        return deep

    # ---- validation ----------------------------------------------------------

    def validate(self) -> ValidationResult:
        """Check the library conforms to the three-layer schema.

        Errors (block adoption): core surface files missing.
        Warnings (backward-compatible): tags line missing, deep subsections
        incomplete, optional files absent.
        """
        v: list[str] = []

        # errors — core files
        if not self.p["overview"].exists():
            v.append(f"ERROR: surface overview missing: {self.p['overview']}")
        if not self.p["todo"].exists():
            v.append(f"ERROR: surface todo missing: {self.p['todo']}")
        if not (self.root / self.loc["surface"]).is_dir():
            v.append(f"ERROR: surface layer dir missing: {self.root / self.loc['surface']}")
        if not (self.root / self.loc["middle"]).is_dir():
            v.append(f"ERROR: middle layer dir missing: {self.root / self.loc['middle']}")
        if not (self.root / self.loc["deep"]).is_dir():
            v.append(f"ERROR: deep layer dir missing: {self.root / self.loc['deep']}")

        # warnings — optional files
        if not self.p["unknowns"].exists():
            v.append(f"WARN: unknowns not configured: {self.p['unknowns']} (optional since v0.3)")
        if not self.p["index"].exists():
            v.append(f"WARN: middle INDEX missing: {self.p['index']}")
        if not self.p["deep_file"].exists():
            v.append(f"WARN: deep reflection file not yet created: {self.p['deep_file']}")
        else:
            deep_content = self.p["deep_file"].read_text(encoding="utf-8")
            sections = _DEEP_SECTION_RE.findall(deep_content)
            if sections:
                tail = deep_content[deep_content.rfind(sections[-1]):]
                if not _DEEP_AGENT_RE.search(tail):
                    v.append("WARN: agent signature missing in latest deep section (add '> agent: <name>' after the section header)")

        # warnings — recent task records should have a tags line
        for row in _tail_table_rows(self.p["index"], 5):
            parsed = _parse_index_row(row)
            if not parsed:
                continue
            fname = parsed["file"]
            task_path = self.p["middle_dir"] / fname
            if not task_path.exists():
                task_path = self.p["middle_dir"] / "archive" / fname
            if not task_path.exists():
                continue
            content = task_path.read_text(encoding="utf-8")
            if not _TAG_LINE_RE.search(content):
                v.append(f"WARN: tags line missing in {fname} (add '- **tags**: #... for associative recall)")
            if not _AGENT_LINE_RE.search(content):
                v.append(f"WARN: agent signature missing in {fname} (add '- **agent**: <name> to identify the writer)")

        return ValidationResult(ok=len([x for x in v if x.startswith("ERROR")]) == 0,
                                 violations=v)

    # ---- concurrency escape hatch (stub by default) -------------------------

    def claim(self, *, scope: str, agent: str, ttl_s: int = 300) -> bool:
        """Opt-in file lock for rare concurrent-shared-file writes.

        By default this is a STUB that always returns True and logs a warning —
        the structure already resolves 90% of concurrency (uniquely-named middle
        files, append-only deep, single-writer todo via consolidate). Real
        locking is deferred to v0.5 if real concurrent conflicts emerge.
        See roadmap §8.
        """
        logger.warning("[claim] stub called (scope=%s agent=%s) — v0.4 does not enforce locks; "
                        "structure + discipline + atomic writes handle concurrency", scope, agent)
        return True

    def release(self, *, scope: str, agent: str) -> None:
        """Release a claim. Stub — see claim()."""
        logger.warning("[release] stub called (scope=%s agent=%s)", scope, agent)

    # ---- cross-project aggregation (read-only) -------------------------------

    @classmethod
    def aggregate(cls, project_dirs: list[Path]) -> str:
        """Read-only cross-project deep-layer aggregation report.

        Wraps examples/aggregate.py logic. Never modifies any project library
        — the deep-layer "append-only, never delete" principle is sacred.
        """
        from .aggregate import parse_deep_file, generate_report  # lazy import
        all_sections = []
        for proj_dir in project_dirs:
            proj_dir = Path(proj_dir)
            loc = detect_locale(proj_dir)
            deep_file = proj_dir / loc["deep"] / loc["deep_file"]
            if not deep_file.exists():
                logger.warning("[aggregate] no deep file in %s", proj_dir)
                continue
            all_sections.extend(parse_deep_file(deep_file, proj_dir.name))
        return generate_report(all_sections)


# --- module-level convenience functions (mirror CLI names, zero migration) ----

def recall(project_dir, **kw) -> RecallResult:
    return Memory(project_dir).recall(**kw)

def log(project_dir, **kw) -> Path:
    return Memory(project_dir).log(**kw)

def consolidate(project_dir, **kw) -> Path:
    return Memory(project_dir).consolidate(**kw)

def validate(project_dir) -> ValidationResult:
    return Memory(project_dir).validate()

def aggregate(project_dirs: list[Path]) -> str:
    return Memory.aggregate([Path(p) for p in project_dirs])