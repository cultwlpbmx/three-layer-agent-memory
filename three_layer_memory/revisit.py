"""
Periodic revisit mechanism — the carrier of L2 criterion #3 (2026-08-15).

记忆没有遗忘，只有分类——但边界若不被定期回访，等同于被遗忘。
("好了伤疤忘了痛" is exactly a boundary that stopped being revisited.)

This module scans the deep reflection file for watchpoints — 观察哨
(observation posts), 预测 (predictions), 证伪 (falsifications) — and flags
those older than `min_age_days` that have never been mentioned in any LATER
deep section. Read-only: it produces a report for the agent/human and never
modifies anything.

Recommended cadence: monthly. The 2026-08-15 external-agent audit found the
day-one observation posts unvisited for 46+ days — precisely the failure
mode this module exists to surface.

Usage:
    from three_layer_memory.revisit import find_unrevisited, revisit_report

    report = revisit_report(project_dir)
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .core import Memory

_SECTION_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})", re.MULTILINE)
_WATCHPOINT_RE = re.compile(r"(观察哨|预测|证伪)")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _parse_sections(deep_file: Path) -> list[tuple[str, str]]:
    """Split the deep file into (date, text) sections by '## YYYY-MM-DD' headers."""
    if not deep_file.exists():
        return []
    text = deep_file.read_text(encoding="utf-8")
    sections: list[tuple[str, str]] = []
    matches = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((m.group(1), text[m.start():end]))
    return sections


def _watchpoint_lines(section_text: str) -> list[str]:
    """Lines in a section that carry 观察哨/预测/证伪 markers."""
    out = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", ">", "*", "1.", "2.", "3.", "4.")) and _WATCHPOINT_RE.search(stripped):
            out.append(stripped)
    return out


def _fragment(line: str, size: int = 15) -> str:
    """A distinctive fragment of a watchpoint line for later-mention matching."""
    core = re.sub(r"^[->*\d.\s]+", "", line)
    return core[:size]


def find_unrevisited(
    project_dir: str | Path,
    *,
    min_age_days: int = 30,
    today: date | None = None,
) -> dict:
    """Find watchpoints (观察哨/预测/证伪) that time has silently buried.

    A watchpoint counts as *revisited* when a distinctive fragment of its line
    appears in a strictly later deep section. Heuristic by design — consistent
    with the other cognitive modules — and read-only.
    """
    today = today or date.today()
    m = Memory(project_dir)
    sections = _parse_sections(m.p["deep_file"])

    result = {
        "unrevisited": [],
        "total_watchpoints": 0,
        "sections_scanned": len(sections),
        "min_age_days": min_age_days,
    }

    for sec_date, sec_text in sections:
        later_text = "".join(t for d, t in sections if d > sec_date)
        try:
            age = (today - date.fromisoformat(sec_date)).days
        except ValueError:
            continue
        for line in _watchpoint_lines(sec_text):
            result["total_watchpoints"] += 1
            if age < min_age_days:
                continue
            frag = _fragment(line)
            if frag and frag in later_text:
                continue  # mentioned later — boundary still alive
            result["unrevisited"].append({
                "date": sec_date,
                "age_days": age,
                "watchpoint": line[:160],
                "kind": (_WATCHPOINT_RE.search(line) or [None, "watchpoint"])[0]
                        if _WATCHPOINT_RE.search(line) else "watchpoint",
            })

    result["unrevisited"].sort(key=lambda w: -w["age_days"])
    return result


def revisit_report(project_dir: str | Path, *, min_age_days: int = 30) -> str:
    """Render the revisit report: boundaries that time is burying."""
    r = find_unrevisited(project_dir, min_age_days=min_age_days)
    lines = [
        "# Revisit Report — boundaries that time is burying",
        f"sections scanned: {r['sections_scanned']} | watchpoints: {r['total_watchpoints']} | "
        f"unrevisited (>= {r['min_age_days']} days, no later mention): {len(r['unrevisited'])}",
        "",
        "> 记忆没有遗忘，只有分类——但边界若不被回访，等同于被遗忘。",
        "",
    ]
    if not r["unrevisited"]:
        lines.append("✅ All aged watchpoints have been mentioned in later sections — boundaries alive.")
        return "\n".join(lines)
    for w in r["unrevisited"]:
        lines.append(f"- [{w['date']}] ({w['age_days']} days old) {w['watchpoint']}")
    lines.append("")
    lines.append("→ Action: revisit each item above — confirm, falsify, or reclassify as boundary. ")
    lines.append("  An unvisited watchpoint is a scar that healed while the pain was forgotten.")
    return "\n".join(lines)
