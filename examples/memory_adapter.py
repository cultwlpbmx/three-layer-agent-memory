#!/usr/bin/env python3
"""
Three-Layer Agent Memory — CLI (canonical, thin wrapper over the library).

This CLI is the "readable in 5 minutes" face of the paradigm. It delegates all
logic to the `three_layer_memory` package so there is one source of truth —
the CLI is just argparse wiring + stdout printing.

  recall        <- on_session_start   load recall files into working memory
                  recall --tag 鉴权    filter middle-layer index by tag (associative recall)

  log           <- on_milestone       create a middle-layer task record + index pointer
                  log --tags "#鉴权 #网络"  add tags line to the task record

  consolidate   <- on_day_end         append a deep-layer reflection (the evolution point)

  validate      ad-hoc               check schema conformance
  snapshot      ad-hoc               render a static HTML/MD snapshot
  init          ad-hoc               scaffold a new project memory from template

Locale-aware: auto-detects Chinese layer dirs (表层/中层/深层) or English
(Surface/Middle/Deep). See ../SCHEMA.md "Localization".

Exit codes: 0 success, 1 bad usage, 2 missing memory dir / files.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Make the library importable when running the script directly from a checkout
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from three_layer_memory import Memory, init as init_lib
from three_layer_memory.snapshot import snapshot as snapshot_lib
from three_layer_memory.graph import (
    build_graph as build_graph_lib,
    load_graph as load_graph_lib,
    query_entities, query_relations, query_neighbors, query_timeline,
    graph_summary,
    detect_contradictions as detect_contras,
    query_evolution,
)
from three_layer_memory.auto_activation import activate as activate_lib, activation_summary
from three_layer_memory.deviation_monitor import check_deviation as check_dev, deviation_report
from three_layer_memory.auto_consolidate import discover_patterns as discover_pats, pattern_report
from three_layer_memory.reflection_quality import assess_reflections as assess_refl, quality_report
from three_layer_memory.meta_meta_cognition import discover_blind_spots as discover_bs, blind_spot_report
from three_layer_memory.cross_project import transfer_knowledge as transfer_kn, transfer_report
from three_layer_memory.prediction_tracker import track_predictions as track_preds, prediction_report as pred_report
from three_layer_memory.self_correction import find_stale_laws as find_stale, correction_report
from three_layer_memory.cloud_sync import sync_status as s_status, sync_push as s_push, sync_pull as s_pull, sync_report
from three_layer_memory.oss_sync import OSSSync, oss_sync_report
from three_layer_memory.auto_sync import AutoSync
from three_layer_memory.sync_coordinator import SyncCoordinator

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def cmd_recall(args) -> int:
    m = Memory(args.memory_dir)
    r = m.recall(tag=args.tag, budget=args.budget, recent_n=args.recent_n)
    if args.tag:
        print(f"[recall] tag filter: #{args.tag} — showing only matching middle-layer records",
              file=sys.stderr)
    print(f"# Recall summary — {m.root.name}\n")
    print(r.as_prompt_block(budget=args.budget))
    print(
        "\n[recall] inject the above into working memory, then act. "
        "Retrieval priority: memory → code/git → ask user.",
        file=sys.stderr,
    )
    return 0


def cmd_log(args) -> int:
    m = Memory(args.memory_dir)
    tags = tuple(t.strip() for t in args.tags.split()) if args.tags else ()
    p = m.log(version=args.version, summary=args.summary, entry=args.entry, tags=tags, agent=args.agent)
    print(f"[writeback] created {p}")
    print(f"[writeback] prepended pointer in {m.p['index']}")
    print("[writeback] fill in the task record, then sync leftover todos into surface todo.",
          file=sys.stderr)
    return 0


def cmd_consolidate(args) -> int:
    m = Memory(args.memory_dir)
    p = m.consolidate(topic=args.topic, review=args.review, plan=args.plan,
                       risk=args.risk, forecast=args.forecast, agent=args.agent)
    print(f"[consolidate] appended reflection to {p}")
    print(
        "[consolidate] now update surface todo (check off done, add new, reprioritize) "
        "and overview summary if there was real progress.",
        file=sys.stderr,
    )
    return 0


def cmd_validate(args) -> int:
    v = Memory(args.memory_dir).validate()
    print(f"ok={v.ok}")
    if v.violations:
        print("\n".join(v.violations))
    return 0 if v.ok else 1


def cmd_snapshot(args) -> int:
    p = snapshot_lib(args.memory_dir, args.output, format=args.format)
    print(f"[snapshot] wrote {p} ({p.stat().st_size} bytes, format={args.format})")
    return 0


def cmd_init(args) -> int:
    root = init_lib(args.target_dir, locale=args.locale, with_unknowns=not args.no_unknowns)
    print(f"[init] scaffolded library at {root}")
    files = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    for f in files:
        print(f"  {f}")
    print("[init] fill in 表层/00-项目总览.md (or Surface/00-overview.md), "
          "then start your first middle-layer task record.",
          file=sys.stderr)
    return 0


def cmd_auto_sync(args) -> int:
    """auto-sync <memory_dir> [--device id] [--action status|push|pull]"""
    # Read AccessKey
    key_file = args.key_file or r"C:\Users\cultw\Desktop\AccessKey.csv"
    if not os.path.exists(key_file):
        print(f"[auto-sync] key file not found: {key_file}", file=sys.stderr)
        return 2
    with open(key_file, "r", encoding="gbk") as f:
        lines = f.readlines()
    parts = lines[1].strip().split(",")
    ak_id = parts[0].strip().strip('"')
    ak_secret = parts[1].strip().strip('"')

    from three_layer_memory import Memory as Mem
    m = AutoSync(
        Mem(args.memory_dir),
        bucket=args.bucket or "agent-memory-sync",
        access_key_id=ak_id,
        access_key_secret=ak_secret,
        endpoint=args.endpoint or "oss-cn-hangzhou",
        device_id=args.device or "local",
    )
    action = args.auto_action or "status"
    if action == "status":
        s = m.sync_status()
        print(f"[auto-sync] local=v{s['local_version']} remote=v{s['remote_version']}")
        print(f"  needs_pull={s['needs_pull']} needs_push={s['needs_push']} conflict={s['conflict']}")
    elif action == "push":
        r = m.force_push()
        print(f"[auto-sync] pushed: {len(r.get('uploaded',[]))} uploaded, {len(r.get('skipped',[]))} skipped")
    elif action == "pull":
        r = m.force_pull()
        print(f"[auto-sync] pulled: {len(r.get('downloaded',[]))} downloaded")
    return 0


def cmd_sync_all(args) -> int:
    """sync-all <code_repo> <memory_dirs...> [--device id] [--direction push|pull]"""
    key_file = args.key_file or r"C:\Users\cultw\Desktop\AccessKey.csv"
    if not os.path.exists(key_file):
        print(f"[sync-all] key file not found: {key_file}", file=sys.stderr)
        return 2
    with open(key_file, "r", encoding="gbk") as f:
        lines = f.readlines()
    parts = lines[1].strip().split(",")
    ak_id = parts[0].strip().strip('"')
    ak_secret = parts[1].strip().strip('"')

    coord = SyncCoordinator(
        code_repo=args.code_repo,
        memory_libraries=args.memory_dirs,
        bucket=args.bucket or "agent-memory-sync",
        access_key_id=ak_id,
        access_key_secret=ak_secret,
        endpoint=args.endpoint or "oss-cn-hangzhou",
        device_id=args.device or "local",
    )
    if args.direction == "status":
        s = coord.status_all()
        print(coord.report(s))
    else:
        r = coord.sync_all(direction=args.direction)
        print(f"[sync-all] direction={r['direction']}")
        gh = r.get("github", {})
        print(f"  GitHub: pushed={gh.get('pushed',False)} committed={gh.get('committed',False)}")
        for lib_name, info in r.get("oss", {}).items():
            print(f"  OSS/{lib_name}: {info}")
    return 0


def cmd_oss_sync(args) -> int:
    """oss-sync <action> <memory_dir> [--bucket name] [--prefix p] [--key-file path]"""
    # Read AccessKey from file
    key_file = args.key_file or r"C:\Users\cultw\Desktop\AccessKey.csv"
    if not os.path.exists(key_file):
        print(f"[oss-sync] key file not found: {key_file}", file=sys.stderr)
        return 2
    with open(key_file, "r", encoding="gbk") as f:
        lines = f.readlines()
    parts = lines[1].strip().split(",")
    ak_id = parts[0].strip().strip('"')
    ak_secret = parts[1].strip().strip('"')

    # Determine prefix from memory dir name if not specified
    prefix = args.prefix or os.path.basename(args.memory_dir.rstrip("/\\")) + "/"

    syncer = OSSSync(
        bucket_name=args.bucket or "agent-memory-sync",
        access_key_id=ak_id,
        access_key_secret=ak_secret,
        endpoint=args.endpoint or "oss-cn-hangzhou",
        prefix=prefix,
    )

    action = args.oss_action
    if action == "push":
        r = syncer.push(args.memory_dir, delete_remote_orphans=args.clean)
        print(oss_sync_report(r, "push"))
    elif action == "pull":
        r = syncer.pull(args.memory_dir, overwrite=not args.no_overwrite)
        print(oss_sync_report(r, "pull"))
    elif action == "status" or action == "diff":
        d = syncer.diff(args.memory_dir)
        print(f"# OSS Diff — {args.memory_dir}")
        print(f"  to_upload: {len(d['to_upload'])}")
        print(f"  to_download: {len(d['to_download'])}")
        print(f"  identical: {len(d['identical'])}")
        if d["to_upload"]:
            print("  Files to upload:")
            for k in d["to_upload"][:5]:
                print(f"    + {k}")
        if d["to_download"]:
            print("  Files to download:")
            for k in d["to_download"][:5]:
                print(f"    ↓ {k}")
    elif action == "list":
        remote = syncer.list_remote()
        print(f"# OSS Remote — {len(remote)} files")
        for k in list(remote.keys())[:15]:
            print(f"  {k}")
    return 0


def cmd_sync(args) -> int:
    """sync <memory_dir> [status|push|pull]"""
    action = args.sync_action or "status"
    if action == "status":
        s = s_status(args.memory_dir)
        print(sync_report(s))
    elif action == "push":
        r = s_push(args.memory_dir, auto_commit=True, message=args.message or "")
        print(f"[sync] pushed={r.get('pushed')} committed={r.get('committed')} hash={r.get('commit_hash','')}")
        if r.get("error"):
            print(f"[sync] error: {r['error']}")
    elif action == "pull":
        r = s_pull(args.memory_dir)
        print(f"[sync] pulled={r.get('pulled')} conflicts={len(r.get('conflicts',[]))}")
        if r.get("error"):
            print(f"[sync] error: {r['error']}")
    return 0


def cmd_correct(args) -> int:
    """correct <memory_dir>"""
    r = find_stale(args.memory_dir)
    print(correction_report(r))
    return 0


def cmd_predict(args) -> int:
    """predict <memory_dir>"""
    r = track_preds(args.memory_dir)
    print(pred_report(r))
    return 0


def cmd_transfer(args) -> int:
    """transfer <target_dir> --sources dir1 dir2 [--context '...']"""
    sources = args.sources.split() if args.sources else []
    r = transfer_kn(args.memory_dir, sources, context=args.context or "")
    print(transfer_report(r))
    return 0


def cmd_meta(args) -> int:
    """meta <memory_dir>"""
    r = discover_bs(args.memory_dir)
    print(blind_spot_report(r))
    return 0


def cmd_quality(args) -> int:
    """quality <memory_dir>"""
    r = assess_refl(args.memory_dir)
    print(quality_report(r))
    return 0


def cmd_consolidate_patterns(args) -> int:
    """consolidate-patterns <memory_dir> [--min-n 2] [--threshold 0.35]"""
    r = discover_pats(args.memory_dir, min_n=args.min_n, similarity_threshold=args.threshold)
    print(pattern_report(r))
    return 0


def cmd_check(args) -> int:
    """check <memory_dir> --context '...' [--files f1 f2]"""
    files = args.files.split() if args.files else None
    r = check_dev(args.memory_dir, context=args.context or "", files=files)
    print(deviation_report(r))
    return 0


def cmd_activate(args) -> int:
    """activate <memory_dir> --context '...' [--files f1 f2]"""
    files = args.files.split() if args.files else None
    r = activate_lib(args.memory_dir, context=args.context or "", files=files)
    print(activation_summary(r))
    return 0


def cmd_graph(args) -> int:
    """graph build|summary|query <memory_dir>"""
    if args.graph_cmd == "build":
        g = build_graph_lib(args.memory_dir)
        stats = g.stats()
        print(f"[graph] built: {stats['entities']} entities, {stats['relations']} relations")
        print(f"[graph] entity_types: {stats['entity_types']}")
        print(f"[graph] relation_types: {stats['relation_types']}")
        print(f"[graph] saved to {args.memory_dir}/.cognitive-graph/graph.json")
        return 0
    elif args.graph_cmd == "summary":
        g = load_graph_lib(args.memory_dir)
        if not g:
            print("[graph] no graph found — run 'graph build' first", file=sys.stderr)
            return 2
        print(graph_summary(g))
        return 0
    elif args.graph_cmd == "query":
        g = load_graph_lib(args.memory_dir)
        if not g:
            print("[graph] no graph found — run 'graph build' first", file=sys.stderr)
            return 2
        if args.entity_type or args.name:
            ents = query_entities(g, type=args.entity_type, name_contains=args.name)
            print(f"# entities ({len(ents)})")
            for e in sorted(ents, key=lambda x: x.get("occurrences",0), reverse=True)[:20]:
                print(f"  {e['type']}: {e['name']} (x{e['occurrences']})")
        if args.rel_type:
            rels = query_relations(g, rel_type=args.rel_type)
            print(f"# relations ({len(rels)})")
            for r in rels[:20]:
                print(f"  {r['source']} -{r['type']}-> {r['target']} [{r.get('date','')}]")
                if r.get("evidence"):
                    print(f"    {r['evidence'][:80]}")
        if args.contradictions:
            contras = detect_contras(args.memory_dir)
            print(f"# contradictions / touched predictions ({len(contras)})")
            for c in contras[:20]:
                print(f"  [{c['status']}] deep:{c['deep_date']} -> middle:{c['middle_date']} (hits:{c['keyword_hits']})")
                print(f"    {c['prediction'][:80]}")
        if args.evolution:
            evo = query_evolution(g, args.evolution)
            print(f"# evolution of {args.evolution} ({len(evo)} points)")
            for point in evo:
                sfs = ", ".join(point.get("source_files", [])[:3])
                print(f"  {point['date']}: x{point['occurrences']} files: {sfs}")
        if args.neighbors:
            nb = query_neighbors(g, args.neighbors)
            print(f"# neighbors of {args.neighbors}")
            print(f"  outgoing: {len(nb['outgoing'])}")
            for r in nb["outgoing"][:10]:
                print(f"    -> {r['target']} ({r['type']})")
            print(f"  incoming: {len(nb['incoming'])}")
            for r in nb["incoming"][:10]:
                print(f"    <- {r['source']} ({r['type']})")
        return 0
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="memory_adapter",
        description="Three-Layer Agent Memory CLI (see PROTOCOL.md). "
                    "Thin wrapper over the three_layer_memory library.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("recall", help="on_session_start: load recall files")
    pr.add_argument("memory_dir")
    pr.add_argument("--tag", help="filter middle-layer records by tag (associative recall, e.g. 鉴权)")
    pr.add_argument("--budget", type=int, default=4000, help="token budget for the prompt block")
    pr.add_argument("--recent-n", type=int, default=2, dest="recent_n",
                     help="number of recent middle-layer records to include")
    pr.set_defaults(func=cmd_recall)

    pl = sub.add_parser("log", help="on_milestone: write a middle-layer task record")
    pl.add_argument("memory_dir")
    pl.add_argument("--version", required=True, help="e.g. V5.4.14 or backend")
    pl.add_argument("--summary", required=True, help="short description (filename-safe)")
    pl.add_argument("--entry", default="", help="what triggered this work")
    pl.add_argument("--tags", default=None, help='space-separated tags, e.g. "#鉴权 #网络"')
    pl.add_argument("--agent", default="unknown", help="name of the agent writing this record (e.g. claude-code, codex)")
    pl.set_defaults(func=cmd_log)

    pc = sub.add_parser("consolidate", help="on_day_end: append a deep reflection")
    pc.add_argument("memory_dir")
    pc.add_argument("--topic", required=True)
    pc.add_argument("--review", required=True, help="现状审视 / status review")
    pc.add_argument("--plan", required=True, help="优化方案 / better path")
    pc.add_argument("--risk", required=True, help="隐患 / risks")
    pc.add_argument("--forecast", required=True, help="预期 / forecast")
    pc.add_argument("--agent", default="unknown", help="name of the agent writing this reflection")
    pc.set_defaults(func=cmd_consolidate)

    pv = sub.add_parser("validate", help="check schema conformance")
    pv.add_argument("memory_dir")
    pv.set_defaults(func=cmd_validate)

    ps = sub.add_parser("snapshot", help="render a static HTML/MD snapshot")
    ps.add_argument("memory_dir")
    ps.add_argument("output", help="output path (e.g. snapshot.html)")
    ps.add_argument("--format", choices=["html", "md"], default="html")
    ps.set_defaults(func=cmd_snapshot)

    pi = sub.add_parser("init", help="scaffold a new project memory from template")
    pi.add_argument("target_dir")
    pi.add_argument("--locale", choices=["zh", "en", "auto"], default="auto")
    pi.add_argument("--no-unknowns", action="store_true",
                     help="omit the optional 02-未知与开放问题 / 02-unknowns.md")
    pi.set_defaults(func=cmd_init)

    # auto-sync subcommand
    pas = sub.add_parser("auto-sync", help="transparent auto-sync: recall auto-pulls, log auto-pushes")
    pas.add_argument("memory_dir")
    pas.add_argument("auto_action", nargs="?", default="status", choices=["status", "push", "pull"])
    pas.add_argument("--device", default=None, help="device ID for version tracking")
    pas.add_argument("--bucket", default=None)
    pas.add_argument("--endpoint", default=None)
    pas.add_argument("--key-file", default=None)
    pas.set_defaults(func=cmd_auto_sync)

    # sync-all subcommand
    psa = sub.add_parser("sync-all", help="coordinate GitHub + OSS one-command sync")
    psa.add_argument("code_repo", help="code repository path (git)")
    psa.add_argument("memory_dirs", nargs="+", help="memory library directories")
    psa.add_argument("--direction", default="push", choices=["push", "pull", "status"])
    psa.add_argument("--device", default=None)
    psa.add_argument("--bucket", default=None)
    psa.add_argument("--endpoint", default=None)
    psa.add_argument("--key-file", default=None)
    psa.set_defaults(func=cmd_sync_all)

    # oss-sync subcommand
    pos = sub.add_parser("oss-sync", help="OSS cloud sync: push/pull/status/list memory library")
    pos.add_argument("oss_action", choices=["push", "pull", "status", "diff", "list"])
    pos.add_argument("memory_dir")
    pos.add_argument("--bucket", default=None, help="OSS bucket name (default: agent-memory-sync)")
    pos.add_argument("--prefix", default=None, help="OSS path prefix (default: memory dir name)")
    pos.add_argument("--endpoint", default=None, help="OSS endpoint (default: oss-cn-hangzhou)")
    pos.add_argument("--key-file", default=None, help="AccessKey CSV file path")
    pos.add_argument("--clean", action="store_true", help="delete remote orphans during push")
    pos.add_argument("--no-overwrite", action="store_true", help="skip existing local files during pull")
    pos.set_defaults(func=cmd_oss_sync)

    # sync subcommand
    psync = sub.add_parser("sync", help="cloud sync: status/push/pull memory library")
    psync.add_argument("memory_dir")
    psync.add_argument("sync_action", nargs="?", default="status", choices=["status", "push", "pull"])
    psync.add_argument("--message", default="", help="commit message for push")
    psync.set_defaults(func=cmd_sync)

    # correct subcommand
    pco = sub.add_parser("correct", help="find stale laws and violated constraints for demotion")
    pco.add_argument("memory_dir")
    pco.set_defaults(func=cmd_correct)

    # predict subcommand
    pp = sub.add_parser("predict", help="track deep-layer predictions: confirmed/falsified/unverified")
    pp.add_argument("memory_dir")
    pp.set_defaults(func=cmd_predict)

    # transfer subcommand
    ptr = sub.add_parser("transfer", help="cross-project knowledge transfer")
    ptr.add_argument("memory_dir", help="target project dir")
    ptr.add_argument("--sources", default=None, help="space-separated source project dirs")
    ptr.add_argument("--context", default="", help="what you're about to do")
    ptr.set_defaults(func=cmd_transfer)

    # meta subcommand
    pm = sub.add_parser("meta", help="meta-meta-cognition: discover reflection blind spots")
    pm.add_argument("memory_dir")
    pm.set_defaults(func=cmd_meta)

    # quality subcommand
    pq = sub.add_parser("quality", help="assess deep-layer reflection quality (detect degradation)")
    pq.add_argument("memory_dir")
    pq.set_defaults(func=cmd_quality)

    # consolidate-patterns subcommand
    pcp = sub.add_parser("consolidate-patterns", help="auto-discover recurring patterns (N>=2) from task records")
    pcp.add_argument("memory_dir")
    pcp.add_argument("--min-n", type=int, default=2, dest="min_n", help="minimum recurrence count")
    pcp.add_argument("--threshold", type=float, default=0.35, help="similarity threshold for clustering")
    pcp.set_defaults(func=cmd_consolidate_patterns)

    # check subcommand
    pck = sub.add_parser("check", help="check if current work deviates from project constraints")
    pck.add_argument("memory_dir")
    pck.add_argument("--context", default="", help="what the agent is about to do")
    pck.add_argument("--files", default=None, help="space-separated file names")
    pck.set_defaults(func=cmd_check)

    # activate subcommand
    pa = sub.add_parser("activate", help="auto-activate relevant memories from cognitive graph")
    pa.add_argument("memory_dir")
    pa.add_argument("--context", default="", help="what the agent is about to do (natural language)")
    pa.add_argument("--files", default=None, help="space-separated file names the agent will touch")
    pa.set_defaults(func=cmd_activate)

    # graph subcommands
    pg = sub.add_parser("graph", help="cognitive graph: build/query the entity-relation graph")
    pg_sub = pg.add_subparsers(dest="graph_cmd", required=True)
    pg_build = pg_sub.add_parser("build", help="build graph from Markdown memory files")
    pg_build.add_argument("memory_dir")
    pg_build.set_defaults(func=cmd_graph)
    pg_sum = pg_sub.add_parser("summary", help="print graph summary")
    pg_sum.add_argument("memory_dir")
    pg_sum.set_defaults(func=cmd_graph)
    pg_q = pg_sub.add_parser("query", help="query entities/relations/neighbors")
    pg_q.add_argument("memory_dir")
    pg_q.add_argument("--type", dest="entity_type", default=None, help="entity type filter (file_ref/version/endpoint/law_ref/decision)")
    pg_q.add_argument("--name", default=None, help="entity name contains filter")
    pg_q.add_argument("--rel", dest="rel_type", default=None, help="relation type filter (caused/migrated/applies/references)")
    pg_q.add_argument("--neighbors", default=None, help="entity id to find neighbors for")
    pg_q.add_argument("--contradictions", action="store_true", help="detect deep-layer predictions touched by recent middle-layer records")
    pg_q.add_argument("--evolution", default=None, help="entity id to trace evolution timeline")
    pg_q.set_defaults(func=cmd_graph)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())