"""python -m three_layer_memory — CLI entry point.

Makes the package directly usable after
`pip install git+https://github.com/cultwlpbmx/three-layer-agent-memory.git`
without cloning the repo for examples/. Mirrors the core commands of
examples/memory_adapter.py (which keeps the full advanced command set).

    python -m three_layer_memory init /path/to/project-memory
    python -m three_layer_memory recall /path/to/project-memory
    python -m three_layer_memory log /path/to/project-memory \
        --version v0.1 --summary "first task" --agent my-agent
    python -m three_layer_memory consolidate /path/to/project-memory \
        --topic "day 1" --review ... --plan ... --risk ... --forecast ...
    python -m three_layer_memory validate /path/to/project-memory
    python -m three_layer_memory snapshot /path/to/project-memory out.html
"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .core import Memory
from .init import init as init_lib
from .snapshot import snapshot as snapshot_lib


def _cmd_init(args: argparse.Namespace) -> int:
    path = init_lib(args.dir, locale=args.locale)
    print(f"initialized: {path}")
    return 0


def _cmd_recall(args: argparse.Namespace) -> int:
    result = Memory(args.dir).recall(tag=args.tag)
    print(result.as_prompt_block())
    print(f"\n[token estimate: {result.token_estimate}]", file=sys.stderr)
    return 0


def _cmd_log(args: argparse.Namespace) -> int:
    path = Memory(args.dir).log(
        version=args.version, summary=args.summary, agent=args.agent,
        tags=args.tags or None)
    print(f"written: {path.name}")
    return 0


def _cmd_consolidate(args: argparse.Namespace) -> int:
    path = Memory(args.dir).consolidate(
        topic=args.topic, review=args.review, plan=args.plan,
        risk=args.risk, forecast=args.forecast, agent=args.agent)
    print(f"appended to: {path.name}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    result = Memory(args.dir).validate()
    print(f"ok: {result.ok}")
    for v in result.violations:
        print(f"  {v}")
    return 0 if result.ok else 1


def _cmd_snapshot(args: argparse.Namespace) -> int:
    out = snapshot_lib(args.dir, args.output)
    print(f"snapshot: {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m three_layer_memory",
        description="Three-layer agent memory — core CLI (see examples/memory_adapter.py for the full set)")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="scaffold a new memory library from template")
    p.add_argument("dir")
    p.add_argument("--locale", default="auto", choices=["auto", "zh", "en"])
    p.set_defaults(func=_cmd_init)

    p = sub.add_parser("recall", help="checkpoint 1: load the six protocol sections")
    p.add_argument("dir")
    p.add_argument("--tag", help="associative recall filter")
    p.set_defaults(func=_cmd_recall)

    p = sub.add_parser("log", help="checkpoint 2: write a middle-layer task record")
    p.add_argument("dir")
    p.add_argument("--version", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--agent", default="unknown")
    p.add_argument("--tags", nargs="*", help="e.g. --tags #setup #cli")
    p.set_defaults(func=_cmd_log)

    p = sub.add_parser("consolidate", help="checkpoint 3: append a deep reflection")
    p.add_argument("dir")
    p.add_argument("--topic", required=True)
    p.add_argument("--review", required=True, help="现状审视")
    p.add_argument("--plan", required=True, help="优化方案")
    p.add_argument("--risk", required=True, help="隐患")
    p.add_argument("--forecast", required=True, help="预期/预测（可证伪）")
    p.add_argument("--agent", default="unknown")
    p.set_defaults(func=_cmd_consolidate)

    p = sub.add_parser("validate", help="check schema conformance")
    p.add_argument("dir")
    p.set_defaults(func=_cmd_validate)

    p = sub.add_parser("snapshot", help="render a static HTML snapshot")
    p.add_argument("dir")
    p.add_argument("output")
    p.set_defaults(func=_cmd_snapshot)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
