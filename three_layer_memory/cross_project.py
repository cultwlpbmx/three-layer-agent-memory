"""
Cross-project knowledge transfer — automatically inject relevant laws from
other projects when starting work on a new project.

Phase 3-2 of the cognitive upgrade: humans don't have a separate brain for
each project — lessons from project A should automatically apply to project B.
The global-deep layer (~/.agent-memory/global-deep/) holds cross-project laws,
but they are only read if the agent remembers to read them.

This module makes cross-project transfer ACTIVE: given a new project's context,
it scans all other project libraries + global-deep for relevant laws and
proactively surfaces them. The agent doesn't need to remember to read global-deep
— the system pushes relevant cross-project experience automatically.

Usage:
    from three_layer_memory.cross_project import transfer_knowledge, transfer_report

    # When starting a new project
    result = transfer_knowledge(new_project_dir, all_project_dirs, context="部署后端到两机")
    print(transfer_report(result))
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .core import Memory, detect_locale


# --- global deep law extraction ------------------------------------------------

def _extract_global_laws(global_deep_path: Path) -> list[dict]:
    """Extract laws from the global-deep reflection file.

    Returns list of {title, text, keywords, date}.
    """
    if not global_deep_path.exists():
        return []

    text = global_deep_path.read_text(encoding="utf-8")
    laws: list[dict] = []

    # Split by ## sections
    parts = re.split(r"## (\d{4}-\d{2}-\d{2})", text)
    for i in range(1, len(parts), 2):
        date = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""

        # Find law entries (### 法则 N or ### Law N patterns)
        for law_match in re.finditer(r"###\s+(.+?)(?:\n|$)", body):
            title = law_match.group(1).strip()
            # Get the following content until next ### or end
            after = body[law_match.end():]
            next_h = re.search(r"###|\Z", after)
            law_text = after[:next_h.start()] if next_h else after
            law_text = law_text.strip()

            if len(law_text) < 20:
                continue

            keywords = re.findall(r"[\u4e00-\u9fff]{2,6}|[a-zA-Z_]{3,}", title + " " + law_text)
            laws.append({
                "title": title[:100],
                "text": law_text[:500],
                "keywords": keywords[:15],
                "date": date,
                "source": "global-deep",
            })

    return laws


# --- project law extraction ----------------------------------------------------

def _extract_project_laws(project_dir: Path) -> list[dict]:
    """Extract experience laws from a project's deep reflection.

    Looks for patterns like '法则', '经验', '教训', 'law', 'lesson' in deep sections.
    """
    m = Memory(project_dir)
    deep_path = m.p["deep_file"]
    if not deep_path.exists():
        return []

    text = deep_path.read_text(encoding="utf-8")
    laws: list[dict] = []

    parts = re.split(r"## (\d{4}-\d{2}-\d{2})", text)
    for i in range(1, len(parts), 2):
        date = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""

        # Find "关键真因" patterns (from archive summary rows)
        for m in re.finditer(r"关键真因[：:]\s*(.+?)(?=\n|$)", body):
            lesson = m.group(1).strip()
            if len(lesson) > 10:
                keywords = re.findall(r"[\u4e00-\u9fff]{2,6}|[a-zA-Z_]{3,}", lesson)
                laws.append({
                    "title": f"关键真因 from {date}",
                    "text": lesson[:300],
                    "keywords": keywords[:10],
                    "date": date,
                    "source": f"project:{project_dir.name}",
                })

        # Find "法则" references
        for m in re.finditer(r"法则\s*\d*[：:]\s*(.+?)(?=\n|$)", body):
            law = m.group(1).strip()
            if len(law) > 10:
                keywords = re.findall(r"[\u4e00-\u9fff]{2,6}|[a-zA-Z_]{3,}", law)
                laws.append({
                    "title": f"法则 from {date}",
                    "text": law[:300],
                    "keywords": keywords[:10],
                    "date": date,
                    "source": f"project:{project_dir.name}",
                })

    return laws


# --- knowledge transfer --------------------------------------------------------

def transfer_knowledge(
    target_project_dir: str | Path,
    all_project_dirs: list[str | Path],
    *,
    context: str = "",
    relevance_threshold: int = 1,
    max_laws: int = 10,
) -> dict:
    """Find relevant laws from other projects + global-deep for the target project.

    `target_project_dir`: the project you're about to work on.
    `all_project_dirs`: list of ALL project library dirs (including target).
    `context`: what you're about to do (natural language).
    `relevance_threshold`: min keyword matches to consider a law relevant.

    Returns {relevant_laws: [...], total_scanned: N, source_breakdown: {...}}.
    """
    target = Path(target_project_dir)

    # Extract context keywords
    context_keywords = set()
    if context:
        context_keywords = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z_]{3,}", context.lower()))

    # 1. Extract global-deep laws
    global_deep = Path.home() / ".agent-memory" / "global-deep" / "global-reflection.md"
    global_laws = _extract_global_laws(global_deep)

    # 2. Extract laws from all other projects
    project_laws: list[dict] = []
    for pd in all_project_dirs:
        pd = Path(pd)
        if pd.resolve() == target.resolve():
            continue  # skip self
        project_laws.extend(_extract_project_laws(pd))

    all_laws = global_laws + project_laws

    # 3. Score relevance
    relevant: list[dict] = []
    for law in all_laws:
        law_keywords = set(kw.lower() for kw in law.get("keywords", []))
        if not context_keywords:
            # No context: include all laws (general transfer)
            relevant.append({**law, "relevance_score": 0, "matched_keywords": []})
            continue

        matched = context_keywords & law_keywords
        if len(matched) >= relevance_threshold:
            relevant.append({
                **law,
                "relevance_score": len(matched),
                "matched_keywords": list(matched),
            })

    # Sort by relevance
    relevant.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    # Source breakdown
    source_counts: dict[str, int] = {}
    for law in relevant[:max_laws]:
        src = law.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    return {
        "target_project": target.name,
        "context": context,
        "relevant_laws": relevant[:max_laws],
        "total_scanned": len(all_laws),
        "total_relevant": len(relevant),
        "source_breakdown": source_counts,
    }


def transfer_report(result: dict) -> str:
    """Render cross-project knowledge transfer as a human/agent-readable report."""
    lines = [
        f"# Cross-Project Knowledge Transfer — {result['target_project']}",
        f"Context: {result.get('context', '')}",
        f"Scanned {result['total_scanned']} laws from other projects + global-deep",
        f"Found {result['total_relevant']} relevant laws",
        "",
    ]

    if result.get("source_breakdown"):
        lines.append("## Source breakdown")
        for src, cnt in result["source_breakdown"].items():
            lines.append(f"  {src}: {cnt}")
        lines.append("")

    laws = result.get("relevant_laws", [])
    if laws:
        lines.append(f"## Relevant laws ({len(laws)})")
        for i, law in enumerate(laws, 1):
            lines.append(f"### Law {i}: {law['title']}")
            lines.append(f"  source: {law.get('source', '?')}")
            lines.append(f"  date: {law.get('date', '?')}")
            if law.get("matched_keywords"):
                lines.append(f"  matched: {', '.join(law['matched_keywords'][:5])}")
            lines.append(f"  text: {law['text'][:200]}")
            lines.append("")
    else:
        lines.append("(no relevant cross-project laws found)")

    lines.append("→ These laws come from OTHER projects. They may or may not apply — review with human.")
    return "\n".join(lines)