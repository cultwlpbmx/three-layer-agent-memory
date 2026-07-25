"""
Cross-project deep-layer aggregation logic (read-only).

Extracted from examples/aggregate.py so the library can offer
Memory.aggregate() without duplicating parsing logic. The CLI in
examples/aggregate.py now calls into this module.

Never modifies any project library — the deep-layer "append-only, never
delete" principle is sacred.
"""
from __future__ import annotations

import re
from pathlib import Path

SECTION_RE = re.compile(r"^## .+", re.MULTILINE)
SUBSECTION_RE = re.compile(r"^### (.+)", re.MULTILINE)

SUBSECTION_MAP_ZH = {
    "现状审视": "review",
    "优化方案": "plan",
    "隐患": "risks",
    "预期": "forecast",
}
SUBSECTION_MAP_EN = {
    "Status review": "review",
    "Better path": "plan",
    "Risks": "risks",
    "Forecast": "forecast",
}


def resolve_projects_from_index(index_path: Path) -> list[Path]:
    """Parse a library-root INDEX.md and return project directory paths."""
    if not index_path.exists():
        return []
    text = index_path.read_text(encoding="utf-8")
    projects = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "----" in line:
            continue
        if line.startswith("| 项目") or line.startswith("| Project"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            path_str = parts[1].strip("`")
            if path_str:
                p = index_path.parent / path_str
                if p.is_dir():
                    projects.append(p)
    return projects


def parse_deep_file(path: Path, project_name: str) -> list[dict]:
    """Parse a deep reflection file into a list of section dicts."""
    text = path.read_text(encoding="utf-8")
    starts = [m.start() for m in SECTION_RE.finditer(text)]
    if not starts:
        return []

    sections = []
    for i, s in enumerate(starts):
        chunk = text[s : starts[i + 1] if i + 1 < len(starts) else len(text)]
        header_line = chunk.split("\n", 1)[0]  # ## YYYY-MM-DD <topic>
        header = header_line.replace("## ", "").strip()

        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", header)
        date = date_match.group(1) if date_match else "????-??-??"
        topic = re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", header).strip()

        body = {}
        sub_matches = list(SUBSECTION_RE.finditer(chunk))
        for j, sm in enumerate(sub_matches):
            sub_name = sm.group(1).strip()
            sub_start = sm.end()
            sub_end = sub_matches[j + 1].start() if j + 1 < len(sub_matches) else len(chunk)
            sub_content = chunk[sub_start:sub_end].strip()
            key = SUBSECTION_MAP_ZH.get(sub_name) or SUBSECTION_MAP_EN.get(sub_name)
            if key:
                body[key] = sub_content

        sections.append({
            "project": project_name,
            "date": date,
            "topic": topic,
            "review": body.get("review", ""),
            "plan": body.get("plan", ""),
            "risks": body.get("risks", ""),
            "forecast": body.get("forecast", ""),
        })
    return sections


def generate_report(sections: list[dict]) -> str:
    """Generate a read-only Markdown report from parsed sections."""
    if not sections:
        return "# Cross-Project Deep Aggregation\n\nNo deep reflections found.\n"

    sections.sort(key=lambda s: s["date"])
    projects = sorted(set(s["project"] for s in sections))
    date_range = f"{sections[0]['date']} — {sections[-1]['date']}"

    lines = [
        "# Cross-Project Deep Aggregation",
        "",
        f"> Read-only report. Generated from {len(sections)} deep reflection section(s)",
        f"> across {len(projects)} project(s): {', '.join(projects)}",
        f"> Date range: {date_range}",
        "> This report never modifies source files. Deep layer is append-only.",
        "",
        "---",
        "",
        "## Timeline",
        "",
        "| Date | Project | Topic | Key Risk |",
        "|------|---------|-------|----------|",
    ]
    for s in sections:
        risk_summary = s["risks"].split("\n")[0].strip() if s["risks"] else "—"
        if len(risk_summary) > 80:
            risk_summary = risk_summary[:77] + "..."
        lines.append(f"| {s['date']} | {s['project']} | {s['topic']} | {risk_summary} |")
    lines.append("")

    lines.append("## Risk Clusters")
    lines.append("")
    risk_sections = [s for s in sections if s["risks"]]
    if risk_sections:
        by_project: dict[str, list[dict]] = {}
        for s in risk_sections:
            by_project.setdefault(s["project"], []).append(s)
        for proj in sorted(by_project):
            lines.append(f"### {proj}")
            lines.append("")
            for s in by_project[proj]:
                lines.append(f"#### {s['date']} — {s['topic']}")
                lines.append("")
                if s["risks"]:
                    lines.append("**Risks:**")
                    lines.append(s["risks"])
                    lines.append("")
                if s["plan"]:
                    lines.append("**Better path:**")
                    lines.append(s["plan"])
                    lines.append("")
            lines.append("")
    else:
        lines.append("No risk subsections found.")
        lines.append("")

    lines.append("## Cross-Project Recurring Themes")
    lines.append("")
    all_risks = [(s["project"], s["risks"]) for s in sections if s["risks"]]
    keyword_buckets: dict[str, list[str]] = {}
    keywords = ["鉴权", "auth", "密钥", "secret", "网络", "network", "代理", "proxy",
                "安全", "security", "隐私", "privacy", "部署", "deploy", "性能", "performance",
                "架构", "architecture", "依赖", "dependency"]
    for kw in keywords:
        for proj, risk_text in all_risks:
            if kw.lower() in risk_text.lower():
                keyword_buckets.setdefault(kw, []).append(proj)
    recurring = {kw: projs for kw, projs in keyword_buckets.items()
                 if len(set(projs)) >= 2 or len(projs) >= 3}
    if recurring:
        lines.append("Keywords appearing across multiple reflections (potential structural issues):")
        lines.append("")
        lines.append("| Keyword | Appearances | Projects |")
        lines.append("|---------|------------|----------|")
        for kw in sorted(recurring, key=lambda k: len(recurring[k]), reverse=True):
            projs = recurring[kw]
            unique_projs = sorted(set(projs))
            lines.append(f"| {kw} | {len(projs)} | {', '.join(unique_projs)} |")
        lines.append("")
        lines.append("> Keywords appearing ≥3 times or across ≥2 projects may indicate")
        lines.append("> cross-project structural issues. Consider promoting to global deep layer.")
    else:
        lines.append("No cross-project recurring themes detected yet.")
        lines.append("")

    return "\n".join(lines)