#!/usr/bin/env python3
"""
Three-Layer Agent Memory — MCP server.

Exposes the three-layer memory paradigm as MCP tools so any MCP client
(Claude Desktop, Cursor, Codex, Windsurf, Cline, any custom MCP agent) can
adopt the paradigm with zero code — one line in the MCP config.

The same Markdown library on disk is shared across all agents that connect.
Agents and models come and go; the memory stays. This is the cross-agent +
cross-model integration point (see roadmap §1.2).

Tools:
  three_layer_recall       on_session_start — load the six protocol sections
  three_layer_log           on_milestone     — write a middle-layer task record
  three_layer_consolidate   on_day_end       — append a deep reflection
  three_layer_snapshot      ad-hoc           — render a static HTML snapshot
  three_layer_init          ad-hoc           — scaffold a new project memory
  three_layer_validate      ad-hoc           — check schema conformance

Run:
  python examples/mcp_server.py            # stdio (default for MCP clients)

Wire into Claude Desktop / Cursor / Codex by adding to their MCP config:
  {
    "mcpServers": {
      "three-layer-agent-memory": {
        "command": "python",
        "args": ["<path-to-repo>/examples/mcp_server.py"]
      }
    }
  }
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the library importable when running the script directly from a checkout
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP

from three_layer_memory import Memory, init as init_lib
from three_layer_memory.snapshot import snapshot as snapshot_lib
from three_layer_memory.graph import (
    build_graph as build_graph_lib,
    load_graph as load_graph_lib,
    query_entities as q_entities,
    query_relations as q_relations,
    query_neighbors as q_neighbors,
    graph_summary as g_summary,
    detect_contradictions as detect_contras,
    query_evolution as q_evolution,
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


mcp = FastMCP("three-layer-agent-memory")


@mcp.tool()
def three_layer_recall(project_dir: str, tag: str | None = None,
                        budget: int = 4000) -> dict:
    """Load the three-layer memory for a project. Call at session start
    (on_session_start).

    The returned dict already answers the three basic questions:
      - overview → "what is this project" + "where are we" (总览含宗旨/定位/内容摘要)
      - todo + last_deep → "what's next"
    No separate brief() call is needed.

    `tag`: optional, filter middle-layer records by #tag (associative recall).
    `budget`: target token budget for the assembled prompt block (default 4000).
    """
    m_ = Memory(project_dir)
    r = m_.recall(tag=tag, budget=budget)
    return {
        "overview": r.overview,
        "todo": r.todo,
        "unknowns": r.unknowns,
        "recent_middle": r.recent_middle,
        "last_deep": r.last_deep,
        "global_deep": r.global_deep,
        "token_estimate": r.token_estimate,
        "locale": r.locale,
        "prompt_block": r.as_prompt_block(budget=budget),
    }


@mcp.tool()
def three_layer_log(project_dir: str, version: str, summary: str,
                     entry: str = "", tags: list[str] | None = None,
                     agent: str = "unknown") -> dict:
    """Write a middle-layer task record + prepend a pointer to the INDEX.
    Call when a verifiable milestone is reached (on_milestone).

    `version`: e.g. "V5.4.14" or "backend" — part of the unique filename.
    `summary`: short filename-safe description.
    `entry`: what triggered this work (optional).
    `tags`: list of hashtags for associative recall, e.g. ["#auth", "#deploy"].
    `agent`: name of the agent writing this record (e.g. "claude-code", "codex") —
             leaves a signature so multi-agent collaboration is traceable.

    The task file is uniquely named (date+version+summary) so concurrent agents
    never collide — structural concurrency safety (roadmap §8).
    """
    m_ = Memory(project_dir)
    p = m_.log(version=version, summary=summary, entry=entry,
                tags=tuple(tags or ()), agent=agent)
    return {"task_file": str(p), "index_updated": True}


@mcp.tool()
def three_layer_consolidate(project_dir: str, topic: str, review: str,
                              plan: str, risk: str, forecast: str,
                              agent: str = "unknown") -> dict:
    """Append a four-section reflection to the deep layer. Call at day end or a
    major node (on_day_end).

    Deep layer is append-only — atomic append means concurrent consolidations
    interleave safely rather than corrupt (roadmap §8).

    The four sections map to the protocol's required reflection structure:
      review  现状审视 / status review
      plan    优化方案 / better path
      risk    隐患 / risks (not-yet-burst-but-will)
      forecast 预期 / falsifiable predictions
    `agent`: name of the agent writing this reflection — leaves a signature in the
             deep layer for multi-agent traceability.
    """
    m_ = Memory(project_dir)
    p = m_.consolidate(topic=topic, review=review, plan=plan,
                        risk=risk, forecast=forecast, agent=agent)
    return {"deep_file": str(p), "section_appended": True}


@mcp.tool()
def three_layer_snapshot(project_dir: str, output_path: str,
                           format: str = "html") -> dict:
    """Render the project memory into a single-page snapshot (visualization).

    `format`: "html" (default — self-contained styled page, opens in any
    browser, no JS) or "md" (plain Markdown, agent-readable).

    Not a web app — zero runtime. Generate once, email/IM to collaborators.
    """
    p = snapshot_lib(project_dir, output_path, format=format)
    return {"snapshot_file": str(p), "bytes": p.stat().st_size}


@mcp.tool()
def three_layer_init(target_dir: str, locale: str = "auto",
                       with_unknowns: bool = True) -> dict:
    """Scaffold a new project memory library from the canonical template.

    `locale`: "zh" (canonical Chinese 表层/中层/深层), "en" (Surface/Middle/Deep),
              or "auto" (defaults to zh).
    `with_unknowns`: include the optional 02-未知与开放问题 / 02-unknowns.md.

    Refuses to clobber a non-empty target dir.
    """
    root = init_lib(target_dir, locale=locale, with_unknowns=with_unknowns)
    files = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    return {"library_root": str(root), "files_created": files}


@mcp.tool()
def three_layer_validate(project_dir: str) -> dict:
    """Validate the memory library conforms to the three-layer schema.

    Returns `ok` (True only if no errors) and `violations` (list of
    "ERROR: ..." / "WARN: ..." strings). Errors block adoption; warnings are
    backward-compatible (e.g. older task records missing a tags line).
    """
    v = Memory(project_dir).validate()
    return {"ok": v.ok, "violations": v.violations,
            "errors": v.errors, "warnings": v.warnings}


@mcp.tool()
def three_layer_aggregate(project_dirs: list[str]) -> dict:
    """Read-only cross-project deep-layer aggregation report.

    Reads deep reflections from multiple project libraries and produces a
    Markdown report clustering findings by date and risk theme. Never
    modifies any project library — deep layer is append-only.
    """
    report = Memory.aggregate([Path(p) for p in project_dirs])
    return {"report": report}


@mcp.tool()
def three_layer_graph(project_dir: str, action: str,
                        entity_type: str = "", name: str = "",
                        rel_type: str = "", neighbors: str = "") -> dict:
    """Build or query the cognitive graph for a project memory library.

    The cognitive graph extracts entities (file refs, versions, endpoints,
    laws, decisions) and relations (causal chains, migrations, law applications)
    from the Markdown memory files. It is a *derivative* layer — rebuildable
    from Markdown with zero data loss.

    `action`:
      "build"  — scan all middle-layer + deep files, extract entities/relations,
                 save to <project_dir>/.cognitive-graph/graph.json
      "summary" — load the graph and return a human-readable summary
      "query"   — query entities/relations/neighbors by filters

    For "query":
      `entity_type` — filter by type (file_ref/version/endpoint/law_ref/decision)
      `name`        — filter by name substring
      `rel_type`    — filter relations by type (caused/migrated/applies/references)
      `neighbors`   — entity id to find connected entities
    """
    if action == "build":
        g = build_graph_lib(project_dir)
        stats = g.stats()
        return {
            "built": True,
            "entities": stats["entities"],
            "relations": stats["relations"],
            "entity_types": stats["entity_types"],
            "relation_types": stats["relation_types"],
            "graph_file": str(Path(project_dir) / ".cognitive-graph" / "graph.json"),
        }
    elif action == "summary":
        g = load_graph_lib(project_dir)
        if not g:
            return {"error": "no graph found — run build first"}
        return {"summary": g_summary(g)}
    elif action == "query":
        g = load_graph_lib(project_dir)
        if not g:
            return {"error": "no graph found — run build first"}
        result: dict = {}
        if entity_type or name:
            ents = q_entities(g, type=entity_type or None, name_contains=name or None)
            result["entities"] = sorted(ents, key=lambda x: x.get("occurrences", 0), reverse=True)[:50]
        if rel_type:
            rels = q_relations(g, rel_type=rel_type)
            result["relations"] = rels[:50]
        if neighbors:
            nb = q_neighbors(g, neighbors)
            result["neighbors"] = nb
        return result
    elif action == "contradictions":
        contras = detect_contras(project_dir)
        return {"touched_predictions": contras[:50]}
    elif action == "evolution":
        g = load_graph_lib(project_dir)
        if not g:
            return {"error": "no graph found"}
        evo = q_evolution(g, neighbors)
        return {"entity_id": neighbors, "evolution": evo}
    else:
        return {"error": f"unknown action: {action}"}


@mcp.tool()
def three_layer_activate(project_dir: str, context: str = "",
                           files: list[str] | None = None) -> dict:
    """Auto-activate relevant memories from the cognitive graph.

    Call after recall when the agent starts working on something. The system
    matches the context/files against the cognitive graph and proactively
    returns related entities, relations, applicable laws, contradiction alerts,
    and evolution snapshots — without the agent needing to manually query.

    `context`: natural language description of what the agent is about to do.
    `files`: list of file names the agent will touch (more precise than context).

    This is the phase-2 "active cognition" entry point — memories are pushed,
    not pulled.
    """
    r = activate_lib(project_dir, context=context, files=files)
    return {
        "activated": r.get("activated", False),
        "summary": activation_summary(r),
        "related_entities": r.get("related_entities", []),
        "related_relations": r.get("related_relations", []),
        "law_applications": r.get("law_applications", []),
        "contradiction_alerts": r.get("contradiction_alerts", []),
        "evolution_snapshots": r.get("evolution_snapshots", []),
    }


@mcp.tool()
def three_layer_check_deviation(project_dir: str, context: str = "",
                                  files: list[str] | None = None) -> dict:
    """Check if the agent's current work deviates from project constraints.

    Reads surface tenets/rules/preferences and recent deep-layer risks/predictions,
    then checks if the current context/files violate any known constraint or
    touch a recent warning. Returns alerts if deviation detected.

    `context`: natural language description of what the agent is about to do.
    `files`: list of file names the agent will touch.

    This is the phase-2 "guardian angel" — the agent's past judgments guard
    its future actions.
    """
    r = check_dev(project_dir, context=context, files=files)
    return {
        "all_clear": r["all_clear"],
        "total_alerts": r.get("total_alerts", 0),
        "surface_alerts": r.get("surface_alerts", []),
        "deep_alerts": r.get("deep_alerts", []),
        "report": deviation_report(r),
    }


@mcp.tool()
def three_layer_consolidate_patterns(project_dir: str, min_n: int = 2,
                                        threshold: float = 0.35) -> dict:
    """Auto-discover recurring patterns across all task records.

    Scans all middle-layer task records, finds difficulties/solutions that
    recur N>=min_n times with similar keywords, and generates candidate
    experience laws for human review.

    `min_n`: minimum recurrence count (default 2, following the paradigm's
             "N>=2 before extracting a law" rule).
    `threshold`: Jaccard similarity threshold for clustering (0.0-1.0).

    Output: candidate laws — NOT final laws. Human reviews and decides which
    to promote to surface rules or global-deep laws.
    """
    r = discover_pats(project_dir, min_n=min_n, similarity_threshold=threshold)
    return {
        "total_records": r["total_records"],
        "total_patterns": r["total_patterns"],
        "patterns": r.get("patterns", []),
        "report": pattern_report(r),
    }


@mcp.tool()
def three_layer_assess_quality(project_dir: str) -> dict:
    """Assess the quality of all deep-layer reflections.

    Scores each reflection section (0-40) on four dimensions:
    completeness, substance, falsifiability, depth.
    Sections scoring <20/40 are marked as degraded (diary entries, not insights).

    This is the meta-quality gate that prevents the evolution loop from
    collapsing into "looks profound but says nothing."
    """
    r = assess_refl(project_dir)
    return {
        "total_sections": r["total_sections"],
        "average_score": r["average_score"],
        "degraded_count": r["degraded_count"],
        "sections": r.get("sections", []),
        "report": quality_report(r),
    }


@mcp.tool()
def three_layer_meta_cognition(project_dir: str) -> dict:
    """Discover meta-cognitive blind spots across all reflections.

    Reads ALL deep-layer reflections and analyzes HOW the agent reflects:
    what risk categories it identifies, what plan levels it thinks at,
    and which dimensions are systematically low. Discovers blind spots like
    "you never reflected on social/ethical risks" or "your plans are never
    at the paradigm level."

    This is phase-3 meta-meta-cognition — "knowing what you don't know you
    don't know." The output is observations about reflection habits, not
    commands to change.
    """
    r = discover_bs(project_dir)
    return {
        "total_sections": r.get("total_sections", 0),
        "total_blind_spots": r.get("total_blind_spots", 0),
        "risk_profile": r.get("risk_profile", {}),
        "plan_profile": r.get("plan_profile", {}),
        "quality_stats": r.get("quality_stats", {}),
        "blind_spots": r.get("blind_spots", []),
        "report": blind_spot_report(r),
    }


@mcp.tool()
def three_layer_transfer(target_project: str, all_projects: list[str],
                           context: str = "") -> dict:
    """Cross-project knowledge transfer — find relevant laws from other projects.

    Scans other project libraries + global-deep for laws relevant to the target
    project's current context. Proactively surfaces cross-project experience so
    the agent inherits ALL projects' lessons, not just the current one.

    `target_project`: the project you're about to work on.
    `all_projects`: list of ALL project library dirs (including target).
    `context`: what you're about to do (natural language).
    """
    r = transfer_kn(target_project, all_projects, context=context)
    return {
        "target": r["target_project"],
        "total_scanned": r["total_scanned"],
        "total_relevant": r["total_relevant"],
        "source_breakdown": r["source_breakdown"],
        "relevant_laws": r["relevant_laws"],
        "report": transfer_report(r),
    }


@mcp.tool()
def three_layer_track_predictions(project_dir: str) -> dict:
    """Track deep-layer predictions against subsequent events.

    Extracts all falsifiable predictions from the deep layer, scans subsequent
    middle-layer records, and reports which predictions were confirmed,
    falsified, or remain unverified. Falsified predictions need meta-reflection.

    This closes the prediction -> verification loop: the agent makes a claim,
    the system tracks whether reality confirmed or contradicted it.
    """
    r = track_preds(project_dir)
    return {
        "total_predictions": r["total_predictions"],
        "confirmed": r["confirmed"],
        "falsified": r["falsified"],
        "touched": r["touched"],
        "unverified": r["unverified"],
        "falsified_predictions": r.get("falsified_predictions", []),
        "report": pred_report(r),
    }


@mcp.tool()
def three_layer_self_correct(project_dir: str) -> dict:
    """Find stale laws and violated constraints for demotion.

    Detects three types of demotion candidates:
    1. Stale laws: law_ref entities not referenced in recent records.
    2. Violated constraints: surface rules violated >=3 times (may be unrealistic).
    3. Falsified predictions: predictions proven wrong by subsequent events.

    Output: candidate demotions for human review — the system proposes, the human disposes.
    """
    r = find_stale(project_dir)
    return {
        "total_candidates": r["total_candidates"],
        "stale_laws": r.get("stale_laws", []),
        "violated_constraints": r.get("violated_constraints", []),
        "report": correction_report(r),
    }


@mcp.tool()
def three_layer_sync(project_dir: str, action: str = "status",
                       message: str = "") -> dict:
    """Cloud sync — keep memory library consistent across devices.

    `action`:
      "status" — check ahead/behind/diverged/uncommitted changes
      "push"   — commit all memory file changes and push to remote
      "pull"   — pull remote changes and merge

    Offline-first: all operations are local. Sync happens when network is available.
    Deep layer is append-only → never conflicts. Surface/middle may need manual merge.
    """
    if action == "status":
        s = s_status(project_dir)
        return {**s, "report": sync_report(s)}
    elif action == "push":
        r = s_push(project_dir, auto_commit=True, message=message)
        return r
    elif action == "pull":
        r = s_pull(project_dir)
        return r
    else:
        return {"error": f"unknown action: {action}"}


if __name__ == "__main__":
    mcp.run()