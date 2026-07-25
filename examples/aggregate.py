#!/usr/bin/env python3
"""
Three-Layer Agent Memory — cross-project deep-layer aggregation CLI.

Thin wrapper over three_layer_memory.Memory.aggregate(). Reads deep-layer
reflections from multiple project libraries and produces a read-only Markdown
report clustering findings by date and risk theme. Never modifies any project
library — the deep-layer "append-only, never delete" principle is sacred.

Usage:
  python aggregate.py <project_dir1> [<project_dir2> ...]

  python aggregate.py --index <library-root>     # read INDEX.md, aggregate all listed projects

  python aggregate.py <dirs...> -o report.md     # write to file instead of stdout

Exit codes: 0 success, 1 bad usage, 2 no projects found.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from three_layer_memory import Memory
from three_layer_memory.aggregate import resolve_projects_from_index  # type: ignore

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


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

    report = Memory.aggregate(unique_paths)
    if report.startswith("# Cross-Project Deep Aggregation\n\nNo deep reflections"):
        print("error: no deep reflections found in any project", file=sys.stderr)
        return 2

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"[aggregate] report written to {args.output}", file=sys.stderr)
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())