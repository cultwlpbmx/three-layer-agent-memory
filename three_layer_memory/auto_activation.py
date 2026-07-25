"""
Auto-activation layer — proactively push relevant memories to the agent.

Phase 2 of the cognitive upgrade: the graph is no longer passive (query-only)
but actively surfaces relevant entities, relations, and predictions when the
agent starts working on something.

Usage:
    from three_layer_memory.auto_activation import activate, activation_summary

    # When agent starts working on something
    result = activate(project_dir, context="我要改 report.py 的月报聚合逻辑")
    print(activation_summary(result))

    # Or with file list
    result = activate(project_dir, files=["report.py", "main.py"])
    print(activation_summary(result))

The activation result includes:
  - related_entities: graph entities matching the context/files
  - related_relations: causal chains, migrations involving those entities
  - touched_predictions: deep-layer predictions that may be relevant
  - contradiction_alerts: if the work touches a deep-layer prediction
  - law_applications: which global-deep laws apply to these entities
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .core import Memory
from .graph import (
    CognitiveGraph, load_graph, query_entities, query_relations,
    query_neighbors, query_timeline, detect_contradictions,
)


def activate(
    project_dir: str | Path,
    *,
    context: str = "",
    files: list[str] | None = None,
    max_entities: int = 20,
    max_relations: int = 15,
    max_predictions: int = 5,
) -> dict:
    """Proactively activate relevant memories based on current work context.

    Call when the agent starts working on something (after recall, as an
    additional "graph activation" step). The system matches the context/files
    against the cognitive graph and returns relevant entities, relations,
    predictions, and alerts.

    `context`: natural language description of what the agent is about to do.
    `files`: list of file names the agent will touch (more precise than context).
    """
    project_dir = Path(project_dir)
    g = load_graph(project_dir)
    if not g:
        return {"activated": False, "reason": "no cognitive graph found — run build_graph first"}

    result: dict = {
        "activated": True,
        "project": g.project,
        "context": context,
        "files": files or [],
    }

    # --- 1. Find related entities ---
    related: list[dict] = []
    search_terms: list[str] = list(files or [])

    # Extract file-like tokens from context
    if context:
        # Match file references in context text
        file_matches = re.findall(
            r"([a-zA-Z0-9_/\-]+\.(?:dart|py|md|json|yaml|yml|toml|ts|js))",
            context,
        )
        search_terms.extend(file_matches)
        # Also extract significant words (3+ chars, not stopwords)
        words = re.findall(r"[a-zA-Z_]{4,}|[\u4e00-\u9fff]{2,}", context)
        search_terms.extend(words[:10])  # limit to avoid noise
        # Extract version strings
        versions = re.findall(r"[Vv]\d+\.\d+(?:\.\d+)?(?:\+\d+)?", context)
        search_terms.extend(versions)

    seen_ids: set[str] = set()
    for term in search_terms:
        term_lower = term.lower()
        for eid, e in g.entities.items():
            if eid in seen_ids:
                continue
            if term_lower in e["name"].lower() or e["name"].lower() in term_lower:
                related.append(e)
                seen_ids.add(eid)
                if len(related) >= max_entities:
                    break
        if len(related) >= max_entities:
            break

    result["related_entities"] = related

    # --- 2. Find related relations (causal chains, migrations, law applications) ---
    related_rels: list[dict] = []
    related_ids = {e["id"] for e in related}
    related_names_lower = {e["name"].lower() for e in related}
    # First: direct neighbors in graph
    for e in related:
        eid = e["id"]
        neighbors = query_neighbors(g, eid)
        for r in neighbors["outgoing"][:3] + neighbors["incoming"][:3]:
            if r not in related_rels:
                related_rels.append(r)
                if len(related_rels) >= max_relations:
                    break
        if len(related_rels) >= max_relations:
            break
    # Also: scan all relations for ones whose evidence mentions related entity names
    if len(related_rels) < max_relations:
        for r in g.relations:
            if r in related_rels:
                continue
            evidence = r.get("evidence", "").lower()
            if any(name in evidence for name in related_names_lower):
                related_rels.append(r)
                if len(related_rels) >= max_relations:
                    break
    result["related_relations"] = related_rels

    # --- 3. Find law applications on related entities ---
    law_apps: list[dict] = []
    for e in related:
        eid = e["id"]
        apps = query_relations(g, entity_id=eid, rel_type="applies")
        law_apps.extend(apps[:2])
    result["law_applications"] = law_apps[:5]

    # --- 4. Contradiction alerts ---
    # Check if any related entity appears in touched predictions
    contras = detect_contradictions(project_dir)
    alerts: list[dict] = []
    for c in contras:
        # Check if any related entity name appears in the prediction text
        pred_lower = c["prediction"].lower()
        for e in related:
            if e["name"].lower() in pred_lower:
                alerts.append(c)
                break
        if len(alerts) >= max_predictions:
            break
    result["contradiction_alerts"] = alerts

    # --- 5. Evolution snapshots for top related entities ---
    evolutions: list[dict] = []
    for e in related[:3]:
        evo = query_timeline(g, e["id"])
        if evo:
            evolutions.append({
                "entity": e["name"],
                "type": e["type"],
                "timeline_points": len(evo),
                "first_seen": evo[0].get("date", "") if evo else "",
                "last_seen": evo[-1].get("date", "") if evo else "",
            })
    result["evolution_snapshots"] = evolutions

    return result


def activation_summary(result: dict) -> str:
    """Render activation result as a human/agent-readable summary."""
    if not result.get("activated"):
        return f"[activation] {result.get('reason', 'not activated')}"

    lines = [
        f"# Auto-Activation — {result['project']}",
        f"Context: {result.get('context', '')}",
        f"Files: {', '.join(result.get('files', []))}",
        "",
    ]

    ents = result.get("related_entities", [])
    if ents:
        lines.append(f"## Related entities ({len(ents)})")
        for e in ents[:10]:
            lines.append(f"  {e['type']}: {e['name']} (x{e.get('occurrences',0)})")

    rels = result.get("related_relations", [])
    if rels:
        lines.append(f"\n## Related relations ({len(rels)})")
        for r in rels[:8]:
            lines.append(f"  {r['source']} -{r['type']}-> {r['target']}")
            if r.get("evidence"):
                lines.append(f"    evidence: {r['evidence'][:80]}")

    laws = result.get("law_applications", [])
    if laws:
        lines.append(f"\n## Applicable laws ({len(laws)})")
        for l in laws:
            lines.append(f"  {l['source']} -> {l['target']} [{l.get('date','')}]")

    alerts = result.get("contradiction_alerts", [])
    if alerts:
        lines.append(f"\n## ⚠ Contradiction alerts ({len(alerts)})")
        for a in alerts:
            lines.append(f"  [{a['status']}] deep:{a['deep_date']} -> middle:{a['middle_date']}")
            lines.append(f"    {a['prediction'][:100]}")

    evos = result.get("evolution_snapshots", [])
    if evos:
        lines.append(f"\n## Evolution snapshots ({len(evos)})")
        for ev in evos:
            lines.append(f"  {ev['entity']} ({ev['type']}): {ev['timeline_points']} points, {ev['first_seen']} → {ev['last_seen']}")

    if not ents and not rels and not alerts:
        lines.append("(no relevant memories activated)")

    return "\n".join(lines)
