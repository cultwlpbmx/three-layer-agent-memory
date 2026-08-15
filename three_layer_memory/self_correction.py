"""
Self-correction layer — detect when laws/rules become stale and propose
reclassification as boundary memory.

Phase 3-4 of the cognitive upgrade: laws and application rules are not permanent.
A law that has never been applied in recent work, or has been repeatedly violated,
may be stale. Per the author-ratified L2 principle (2026-08-15): **there is no
forgetting, only classification** — a stale or falsified rule is NOT removed or
silenced; it is *transferred* from "directing behavior" to "guarding behavior".
It becomes a boundary: actively recalled when the path approaches the old
mistake, so time never dilutes the lesson ("好了伤疤忘了痛" is the human
failure mode this exists to prevent).

Demotion triggers:
  1. Law never referenced: a law_ref entity in the cognitive graph has 0 occurrences
     in recent (last N) middle-layer records.
  2. Law repeatedly violated: deviation_monitor surface alerts for the same
     constraint appear repeatedly (N>=3) — the constraint may be unrealistic.
  3. Prediction falsified: a deep-layer prediction was falsified, and the law
     that generated it may need revision.

The output is *candidate* reclassifications, not final actions. Human reviews
and decides. Demotion = transfer (指导→守护), never deletion.

Usage:
    from three_layer_memory.self_correction import find_stale_laws, correction_report

    result = find_stale_laws(project_dir)
    print(correction_report(result))
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .core import Memory
from .graph import load_graph, query_entities, query_relations


def find_stale_laws(
    project_dir: str | Path,
    *,
    recent_threshold: int = 10,
    min_violations: int = 3,
) -> dict:
    """Find laws/rules that may be stale and should be demoted.

    `recent_threshold`: number of recent middle-layer records to check for usage.
    `min_violations`: minimum repeated violations to flag a constraint as unrealistic.

    Returns {stale_laws: [...], violated_constraints: [...], total_candidates: N}.
    """
    project_dir = Path(project_dir)
    m = Memory(project_dir)

    result: dict = {
        "stale_laws": [],
        "violated_constraints": [],
        "total_candidates": 0,
    }

    # --- 1. Check law_ref entities in cognitive graph ---
    g = load_graph(project_dir)
    if g:
        law_entities = query_entities(g, type="law_ref")
        # Get recent middle-layer records
        mid_dir = m.p["middle_dir"]
        recent_files: list[Path] = []
        for f in sorted(mid_dir.iterdir(), reverse=True):
            if f.suffix == ".md" and not f.name.startswith("_") and not f.name.startswith("INDEX"):
                recent_files.append(f)
                if len(recent_files) >= recent_threshold:
                    break

        recent_text = ""
        for f in recent_files:
            try:
                recent_text += f.read_text(encoding="utf-8").lower() + "\n"
            except Exception:
                continue

        for law in law_entities:
            law_name = law["name"]
            # Check if law appears in recent records
            if law_name.lower() not in recent_text:
                # Check applies relations
                applies = query_relations(g, entity_id=law["id"], rel_type="applies")
                recent_applies = [
                    r for r in applies
                    if any(r.get("date", "") >= "2026-07-14" for _ in [1])  # recent check
                ]
                if not recent_applies:
                    result["stale_laws"].append({
                        "law": law_name,
                        "total_occurrences": law.get("occurrences", 0),
                        "source_files": law.get("source_files", []),
                        "reason": f"not referenced in recent {len(recent_files)} records",
                        "suggestion": "transfer to boundary memory: stop directing, start guarding (demote != delete)",
                    })

    # --- 2. Check application rules for repeated violations ---
    # Read surface rules
    overview_path = m.p["overview"]
    if overview_path.exists():
        overview_text = overview_path.read_text(encoding="utf-8")
        rules_match = re.search(r"## 应用准则.*?(?=\n##|\Z)", overview_text, re.DOTALL)
        if rules_match:
            for line in rules_match.group(0).split("\n"):
                line = line.strip()
                if line.startswith("- ") and len(line) > 10:
                    rule = line.lstrip("- ")
                    # Check how many recent records mention violating this rule
                    # (simplified: check if rule keywords appear with "新功能" etc.)
                    violation_keywords = ["新功能", "新增", "添加", "新增功能"]
                    if any(kw in rule for kw in ["不增加", "不再", "只做"]):
                        # This is a "don't add" rule — check for violations in recent records
                        mid_dir = m.p["middle_dir"]
                        violation_count = 0
                        for f in sorted(mid_dir.iterdir(), reverse=True):
                            if f.suffix == ".md" and not f.name.startswith("_") and not f.name.startswith("INDEX"):
                                try:
                                    text = f.read_text(encoding="utf-8").lower()
                                    if any(kw in text for kw in violation_keywords):
                                        violation_count += 1
                                except Exception:
                                    continue
                                if violation_count >= min_violations:
                                    break
                        if violation_count >= min_violations:
                            result["violated_constraints"].append({
                                "rule": rule[:150],
                                "violation_count": violation_count,
                                "reason": f"violated {violation_count} times — may be unrealistic or ignored",
                                "suggestion": "consider revising this rule or enforcing it differently",
                            })

    # --- 3. Check for falsified predictions (from prediction_tracker) ---
    try:
        from .prediction_tracker import track_predictions
        pred_result = track_predictions(project_dir)
        for pred in pred_result.get("falsified_predictions", []):
            result["stale_laws"].append({
                "law": f"prediction from {pred['date']}",
                "total_occurrences": 0,
                "source_files": [],
                "reason": f"falsified prediction: {pred['text'][:100]}",
                "suggestion": "revise the assumption, then keep the falsified version as a boundary marker",
            })
    except Exception:
        pass

    result["total_candidates"] = len(result["stale_laws"]) + len(result["violated_constraints"])
    return result


def correction_report(result: dict) -> str:
    """Render self-correction candidates as a human/agent-readable report."""
    lines = [
        f"# Self-Correction — Stale Law Detection (boundary-transfer semantics, L2)",
        f"Total boundary-transfer candidates: {result['total_candidates']}",
        "",
    ]

    if result["stale_laws"]:
        lines.append(f"## Stale laws ({len(result['stale_laws'])})")
        for law in result["stale_laws"]:
            lines.append(f"  - {law['law']}")
            lines.append(f"    reason: {law['reason']}")
            lines.append(f"    suggestion: {law['suggestion']}")
            if law.get("total_occurrences"):
                lines.append(f"    historical usage: x{law['total_occurrences']}")
            lines.append("")

    if result["violated_constraints"]:
        lines.append(f"## Repeatedly violated constraints ({len(result['violated_constraints'])})")
        for vc in result["violated_constraints"]:
            lines.append(f"  - rule: {vc['rule'][:80]}")
            lines.append(f"    violations: {vc['violation_count']}")
            lines.append(f"    reason: {vc['reason']}")
            lines.append(f"    suggestion: {vc['suggestion']}")
            lines.append("")

    if not result["stale_laws"] and not result["violated_constraints"]:
        lines.append("✅ No stale laws or violated constraints detected — all laws appear active.")

    lines.append("→ These are CANDIDATE boundary transfers for human review. Demotion = transfer (directing→guarding), never deletion.")
    return "\n".join(lines)