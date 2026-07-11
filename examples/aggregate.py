#!/usr/bin/env python3
"""
Three-Layer Agent Memory — cross-project deep-layer aggregation.

Reads the deep-layer reflection file from multiple project libraries,
parses each ## YYYY-MM-DD section (with its four subsections), and produces
a read-only Markdown report that clusters findings by date and by risk theme.

This is NOT a write-back tool. It never modifies any project library.
The deep-layer "append-only, never delete" principle is sacred.

Locale-aware: auto-detects Chinese (深层/AI深度思考.md) or English
(Deep/AI-deep-reflection.md) layouts. See ../SCHEMA.md "Localization".

Usage:
  python aggregate.py <project_dir1> [<project_dir2> ...]

  python aggregate.py --index <library-root>     # read INDEX.md, aggregate all listed projects

  python aggregate.py <dirs...> -o report.md     # write to file instead of stdout

Exit codes: 0 success, 1 bad usage, 2 no projects found.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# --- locale mapping (same as memory_adapter.py) --------------------------------

ZH = {"deep": "深层", "deep_file": "AI深度思考.md"}
EN = {"deep": "Deep", "deep_file": "AI-deep-reflection.md"}


def detect_deep_file(project_dir: Path) -> Path | None:
    """Find the deep reflection file in a project library, regardless of locale."""
    for loc in (ZH, EN):
        p = project_dir / loc["deep"] / loc["deep_file"]
        if p.exists():
            return p
    return None


# --- parsing -------------------------------------------------------------------

SECTION_RE = re.compile(r"^## .+", re.MULTILINE)
SUBSECTION_RE = re.compile(r"^### (.+)", re.MULTILINE)

# Map Chinese subsection names to canonical keys
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

        # extract date from header
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", header)
        date = date_match.group(1) if date_match else "????-??-??"
        topic = re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", header).strip()

        # parse subsections
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


# --- report generation ---------------------------------------------------------

def generate_report(sections: list[dict]) -> str:
    """Generate a read-only Markdown report from parsed sections."""
    if not sections:
        return "# Cross-Project Deep Aggregation\n\nNo deep reflections found in the given project libraries.\n"

    # sort by date
    sections.sort(key=lambda s: s["date"])

    projects = sorted(set(s["project"] for s in sections))
    date_range = f"{sections[0]['date']} — {sections[-1]['date']}"

    lines = [
        f"# Cross-Project Deep Aggregation",
        f"",
        f"> Read-only report. Generated from {len(sections)} deep reflection section(s)",
        f"> across {len(projects)} project(s): {', '.join(projects)}",
        f"> Date range: {date_range}",
        f"> This report never modifies source files. Deep layer is append-only.",
        f"",
        f"---",
        f"",
    ]

    # timeline view
    lines.append("## Timeline\n")
    lines.append("| Date | Project | Topic | Key Risk |")
    lines.append("|------|---------|-------|----------|")
    for s in sections:
        # take first line of risks as summary
        risk_summary = s["risks"].split("\n")[0].strip() if s["risks"] else "—"
        # truncate for table
        if len(risk_summary) > 80:
            risk_summary = risk_summary[:77] + "..."
        lines.append(f"| {s['date']} | {s['project']} | {s['topic']} | {risk_summary} |")
    lines.append("")

    # cluster by risk themes (simple keyword clustering)
    lines.append("## Risk Clusters\n")
    risk_sections = [s for s in sections if s["risks"]]
    if risk_sections:
        # group by project
        by_project: dict[str, list[dict]] = {}
        for s in risk_sections:
            by_project.setdefault(s["project"], []).append(s)

        for proj in sorted(by_project):
            lines.append(f"### {proj}\n")
            for s in by_project[proj]:
                lines.append(f"#### {s['date']} — {s['topic']}\n")
                if s["risks"]:
                    lines.append(f"**Risks:**\n")
                    lines.append(s["risks"])
                    lines.append("")
                if s["plan"]:
                    lines.append(f"**Better path:**\n")
                    lines.append(s["plan"])
                    lines.append("")
                lines.append("")
    else:
        lines.append("No risk subsections found.\n")

    # cross-project recurring themes
    lines.append("## Cross-Project Recurring Themes\n")
    # simple heuristic: find keywords that appear in risks across multiple projects
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
        lines.append("Keywords appearing across multiple reflections (potential structural issues):\n")
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
        lines.append("No cross-project recurring themes detected yet.\n")

    return "\n".join(lines)


# --- CLI -----------------------------------------------------------------------

def resolve_projects_from_index(index_path: Path) -> list[Path]:
    """Parse a library-root INDEX.md and return project directory paths."""
    if not index_path.exists():
        return []
    text = index_path.read_text(encoding="utf-8")
    projects = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "----" in line or line.startswith("| 项目") or line.startswith("| Project"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            # path is in the second column (index 1 after leading |)
            path_str = parts[1].strip("`")
            if path_str:
                p = index_path.parent / path_str
                if p.is_dir():
                    projects.append(p)
    return projects


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="aggregate",
        description="Cross-project deep-layer aggregation (read-only). See ../INTEGRATION.md.",
    )
    ap.add_argument("project_dirs", nargs="*", help="project library directories")
    ap.add_argument("--index", help="library root containing INDEX.md")
    ap.add_argument("-o", "--output", help="write report to file instead of stdout")
    args = ap.parse_args(argv)

    project_paths: list[Path] = []

    if args.index:
        index_path = Path(args.index) / "INDEX.md"
        project_paths = resolve_projects_from_index(index_path)
        if not project_paths:
            # try index path itself as the INDEX.md file
            index_path = Path(args.index)
            if index_path.is_file() and index_path.name == "INDEX.md":
                project_paths = resolve_projects_from_index(index_path)

    for d in args.project_dirs:
        p = Path(d)
        if p.is_dir():
            project_paths.append(p)

    if not project_paths:
        print("error: no project directories found", file=sys.stderr)
        ap.print_help(sys.stderr)
        return 2

    # deduplicate while preserving order
    seen = set()
    unique_paths = []
    for p in project_paths:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            unique_paths.append(p)

    all_sections = []
    for proj_dir in unique_paths:
        deep_file = detect_deep_file(proj_dir)
        if deep_file is None:
            print(f"warn: no deep reflection file found in {proj_dir}", file=sys.stderr)
            continue
        sections = parse_deep_file(deep_file, proj_dir.name)
        all_sections.extend(sections)
        print(f"[aggregate] parsed {len(sections)} section(s) from {proj_dir.name}", file=sys.stderr)

    if not all_sections:
        print("error: no deep reflections found in any project", file=sys.stderr)
        return 2

    report = generate_report(all_sections)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"[aggregate] report written to {args.output}", file=sys.stderr)
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
