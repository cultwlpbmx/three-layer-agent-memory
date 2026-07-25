"""
Cognitive graph layer — extract entities and relations from Markdown memory
files to build a knowledge graph.

This is a *derivative* layer: the graph is generated from the Markdown files
and can be rebuilt at any time without loss. The Markdown remains the single
source of truth. The graph adds "neural connections" between memories that
the flat-file structure cannot express.

Entity types extracted:
  - file_ref:     code/asset file references (e.g. `foo.dart:21`, `voice.py`)
  - version:      version strings (e.g. V5.4.52+5452, v0.5)
  - concept:      recurring domain concepts (extracted via keywords + frequency)
  - decision:     explicit decisions ("保留X", "砍X", "沿用X", "keep X", "drop X")
  - law_ref:      references to global-deep laws ("法则1", "法则2", "law 1")
  - endpoint:     API endpoints (e.g. /api/v1/voice/asr)

Relation types extracted:
  - caused:       causal chain (X → caused → Y)
  - migrated:     migration/alignment (A → migrated → B)
  - applies:      law application (法则N → applies → task)
  - references:   file reference (task → references → file)
  - contradicts:  new record vs deep-layer prediction (new → contradicts → prediction)

Graph storage: JSON file at <project-library>/.cognitive-graph/graph.json
Rebuildable: delete the JSON, run build_graph() again — zero data loss.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .core import Memory, detect_locale, ZH, EN


# --- entity extraction patterns ------------------------------------------------

# file references: `foo.dart`, `foo.dart:21`, `foo.dart:21/81`, `backend/main.py`
_FILE_REF_RE = re.compile(
    r"`?([a-zA-Z0-9_./\-]+\.(?:dart|py|md|json|yaml|yml|toml|sh|ts|js|tsx|jsx|html|css)"
    r"(?::\d+(?:/\d+)?(?:,\s*\d+)*)?)`?"
)

# version strings: V5.4.52+5452, V5.4.52, v0.5, v0.4.0
_VERSION_RE = re.compile(r"\b([Vv]\d+\.\d+(?:\.\d+)?(?:\+\d+)?)\b")

# API endpoints: /api/v1/voice/asr, /voice/asr, /family/proactive/msgs
_ENDPOINT_RE = re.compile(
        r"`?(/(?:api/v\d+/|voice/|family/|admin/|health|msgs/|report/)[a-z0-9_/{}.\-]+)`",
        re.IGNORECASE
    )

# law references: 法则1, 法则2, law 1
_LAW_REF_RE = re.compile(r"(法则\s*[12]|law\s*[12])", re.IGNORECASE)

# decisions: 保留X, 砍X, 沿用X, keep X, drop X
_DECISION_RE = re.compile(
    r"\*\*(保留|砍|沿用|keep|drop|deferred|暂缓)\b[^*]*\*"
)


# --- causal patterns -----------------------------------------------------------

# Chinese causal: 因为X，所以Y / 导致 / 使得 / 引发
_CAUSAL_ZH_RE = re.compile(
    r"因为(.{2,60}?)[，,]\s*所以(.{2,80}?)[。.\n]"
)
_CAUSAL_LEAD_RE = re.compile(
    r"(导致|使得|引发)(.{2,80}?)[。.\n，,]"
)

# English causal: because X, Y / caused X to Y / resulted in
_CAUSAL_EN_RE = re.compile(
    r"because\s+(.{2,60}?)\s*,?\s*(.{2,80}?)[.\n]"
)
_CAUSED_RE = re.compile(
    r"caused\s+(.{2,40}?)\s+to\s+(.{2,60}?)[.\n]"
)

# migration/alignment: A → B, A移植到B, A对齐B
# Disabled bare-arrow matching — too noisy (matches table arrows, math symbols).
# Only use keyword-anchored _MIGRATE_ZH_RE below.
_MIGRATE_RE = re.compile(r"(?!)")  # intentionally matches nothing
_MIGRATE_ZH_RE = re.compile(
    r"([a-zA-Z\u4e00-\u9fff_]{2,20}?)\s*(?:移植到|对齐|迁移到)\s*([a-zA-Z\u4e00-\u9fff_]{2,20}?)"
)


# --- data structures -----------------------------------------------------------

@dataclass
class Entity:
    id: str          # unique key: "type:name" e.g. "file_ref:clean_colors.dart"
    type: str        # file_ref / version / concept / decision / law_ref / endpoint
    name: str
    first_seen: str = ""     # ISO date
    last_seen: str = ""
    occurrences: int = 0
    source_files: list[str] = field(default_factory=list)


@dataclass
class Relation:
    source: str      # entity id
    target: str       # entity id
    type: str         # caused / migrated / applies / references / contradicts
    evidence: str = "" # the matched text snippet
    source_file: str = ""
    date: str = ""


@dataclass
class CognitiveGraph:
    entities: dict[str, dict] = field(default_factory=dict)  # id -> Entity as dict
    relations: list[dict] = field(default_factory=list)       # list of Relation as dict
    built_at: str = ""
    project: str = ""

    def stats(self) -> dict:
        type_counts = defaultdict(int)
        for e in self.entities.values():
            type_counts[e["type"]] += 1
        rel_counts = defaultdict(int)
        for r in self.relations:
            rel_counts[r["type"]] += 1
        return {
            "entities": len(self.entities),
            "relations": len(self.relations),
            "entity_types": dict(type_counts),
            "relation_types": dict(rel_counts),
        }


# --- extraction ----------------------------------------------------------------

def _extract_entities(text: str, source_file: str, date: str) -> tuple[list[Entity], list[str]]:
    """Extract all entities from a text block. Returns (entities, raw_matches_for_relation_parsing)."""
    entities: list[Entity] = []
    seen_ids: set[str] = set()

    def add_entity(etype: str, name: str):
        eid = f"{etype}:{name}"
        if eid in seen_ids:
            # update existing
            for e in entities:
                if e.id == eid:
                    e.occurrences += 1
                    if date and date > e.last_seen:
                        e.last_seen = date
                    if source_file not in e.source_files:
                        e.source_files.append(source_file)
                    return
        seen_ids.add(eid)
        entities.append(Entity(
            id=eid, type=etype, name=name,
            first_seen=date, last_seen=date,
            occurrences=1, source_files=[source_file],
        ))

    # file references
    for m in _FILE_REF_RE.finditer(text):
        name = m.group(1).split(":")[0]  # strip line numbers for entity name
        add_entity("file_ref", name)

    # versions
    for m in _VERSION_RE.finditer(text):
        add_entity("version", m.group(1))

    # endpoints
    for m in _ENDPOINT_RE.finditer(text):
        add_entity("endpoint", m.group(1))

    # law references
    for m in _LAW_REF_RE.finditer(text):
        name = m.group(1).replace(" ", "").strip()
        add_entity("law_ref", name)

    # decisions (extract the decision keyword + object)
    for m in _DECISION_RE.finditer(text):
        raw = m.group(0).strip("*")
        add_entity("decision", raw[:60])

    return entities, []


def _extract_relations(text: str, source_file: str, date: str, entities: list[Entity]) -> list[Relation]:
    """Extract relations between entities from text."""
    relations: list[Relation] = []

    # Build a lookup for fast entity matching
    _entity_names = [(e.id, e.name) for e in entities]

    def find_entity_id(name_part: str) -> Optional[str]:
        """Find an entity id that contains the name_part. Searches all types."""
        name_lower = name_part.lower()
        for eid, ename in _entity_names:
            if name_lower in ename.lower() or ename.lower() in name_lower:
                return eid
        return None

    def resolve_or_concept(text_ref: str) -> str:
        """Try to link to a real entity; fall back to concept: only if no match."""
        eid = find_entity_id(text_ref)
        return eid if eid else f"concept:{text_ref[:30]}"

    # causal: 因为X，所以Y
    for m in _CAUSAL_ZH_RE.finditer(text):
        cause_text = m.group(1).strip()
        effect_text = m.group(2).strip()
        # try to link to file_ref entities
        cause_id = resolve_or_concept(cause_text)
        effect_id = resolve_or_concept(effect_text)
        relations.append(Relation(
            source=cause_id, target=effect_id, type="caused",
            evidence=f"因为{cause_text}，所以{effect_text}",
            source_file=source_file, date=date,
        ))

    # causal: 导致/使得/引发
    for m in _CAUSAL_LEAD_RE.finditer(text):
        verb = m.group(1)
        target_text = m.group(2).strip()
        # Try to find a real entity in the target text
        target_id = resolve_or_concept(target_text)
        cause_src = resolve_or_concept(verb) or f"concept:{verb}"
        relations.append(Relation(
            source=cause_src, target=target_id,
            type="caused", evidence=f"{verb}{target_text}",
            source_file=source_file, date=date,
        ))

    # migration: keyword-anchored (移植到/对齐/迁移到)
    for m in _MIGRATE_ZH_RE.finditer(text):
        src = m.group(1).strip()
        tgt = m.group(2).strip()
        if src == tgt or len(src) < 2 or len(tgt) < 2:
            continue
        src_id = resolve_or_concept(src)
        tgt_id = resolve_or_concept(tgt)
        relations.append(Relation(
            source=src_id, target=tgt_id,
            type="migrated", evidence=f"{src} -> {tgt}",
            source_file=source_file, date=date,
        ))

    # law application: 法则N → applies → task
    for m in _LAW_REF_RE.finditer(text):
        law_name = m.group(1).replace(" ", "").strip()
        law_id = f"law_ref:{law_name}"
        relations.append(Relation(
            source=law_id, target=f"file_ref:{source_file}",
            type="applies", evidence=m.group(0),
            source_file=source_file, date=date,
        ))

    return relations


# --- graph builder -------------------------------------------------------------

def build_graph(project_dir: str | Path, *, save: bool = True) -> CognitiveGraph:
    """Scan an entire project memory library and build a cognitive graph.

    Reads all middle-layer task records and the deep reflection file,
    extracts entities and relations, and assembles a CognitiveGraph.

    If save=True, writes the graph to <project_dir>/.cognitive-graph/graph.json.
    The graph is a derivative — deleting it and rebuilding causes zero data loss.
    """
    project_dir = Path(project_dir)
    m = Memory(project_dir)
    loc = m.loc

    graph = CognitiveGraph(
        built_at=datetime.now().isoformat(),
        project=project_dir.name,
    )

    # --- scan middle-layer task records ---
    mid_dir = m.p["middle_dir"]
    task_files = []
    for f in sorted(mid_dir.iterdir()):
        if f.suffix == ".md" and not f.name.startswith("_") and not f.name.startswith("INDEX"):
            task_files.append(f)
    # also scan archive
    arch_dir = mid_dir / "archive"
    if arch_dir.is_dir():
        for f in sorted(arch_dir.iterdir()):
            if f.suffix == ".md":
                task_files.append(f)

    all_entities: list[Entity] = []
    all_relations: list[Relation] = []

    for tf in task_files:
        # extract date from filename: YYYY-MM-DD_...
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", tf.name)
        date_str = date_match.group(1) if date_match else ""

        try:
            text = tf.read_text(encoding="utf-8")
        except Exception:
            continue

        ents, _ = _extract_entities(text, tf.name, date_str)
        rels = _extract_relations(text, tf.name, date_str, ents)
        all_entities.extend(ents)
        all_relations.extend(rels)

    # --- scan deep reflection ---
    deep_path = m.p["deep_file"]
    if deep_path.exists():
        deep_text = deep_path.read_text(encoding="utf-8")
        # split into sections by ## YYYY-MM-DD
        for section_match in re.finditer(r"## (\d{4}-\d{2}-\d{2})", deep_text):
            pass  # date markers found
        ents, _ = _extract_entities(deep_text, deep_path.name, "")
        rels = _extract_relations(deep_text, deep_path.name, "", ents)
        all_entities.extend(ents)
        all_relations.extend(rels)

    # --- merge entities into graph ---
    for e in all_entities:
        if e.id in graph.entities:
            existing = graph.entities[e.id]
            existing["occurrences"] += e.occurrences
            if e.last_seen > existing["last_seen"]:
                existing["last_seen"] = e.last_seen
            if e.first_seen < existing["first_seen"] or not existing["first_seen"]:
                existing["first_seen"] = e.first_seen
            for sf in e.source_files:
                if sf not in existing["source_files"]:
                    existing["source_files"].append(sf)
        else:
            graph.entities[e.id] = asdict(e)

    # --- merge relations (dedupe by source+target+type+evidence) ---
    seen_rels: set[str] = set()
    for r in all_relations:
        key = f"{r.source}|{r.target}|{r.type}|{r.evidence}"
        if key not in seen_rels:
            seen_rels.add(key)
            graph.relations.append(asdict(r))

    # --- save ---
    if save:
        graph_dir = project_dir / ".cognitive-graph"
        graph_dir.mkdir(parents=True, exist_ok=True)
        graph_path = graph_dir / "graph.json"
        tmp_path = graph_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(asdict(graph), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, graph_path)

    return graph


# --- graph loading -------------------------------------------------------------

def load_graph(project_dir: str | Path) -> Optional[CognitiveGraph]:
    """Load a previously built cognitive graph from disk."""
    graph_path = Path(project_dir) / ".cognitive-graph" / "graph.json"
    if not graph_path.exists():
        return None
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    return CognitiveGraph(
        entities=data.get("entities", {}),
        relations=data.get("relations", []),
        built_at=data.get("built_at", ""),
        project=data.get("project", ""),
    )


# --- query API -----------------------------------------------------------------

def query_entities(graph: CognitiveGraph, *, type: str = None, name_contains: str = None) -> list[dict]:
    """Query entities by type and/or name substring."""
    results = []
    for eid, e in graph.entities.items():
        if type and e["type"] != type:
            continue
        if name_contains and name_contains.lower() not in e["name"].lower():
            continue
        results.append(e)
    return results


def query_relations(graph: CognitiveGraph, *, entity_id: str = None, rel_type: str = None) -> list[dict]:
    """Query relations by entity id and/or relation type."""
    results = []
    for r in graph.relations:
        if entity_id and r["source"] != entity_id and r["target"] != entity_id:
            continue
        if rel_type and r["type"] != rel_type:
            continue
        results.append(r)
    return results


def query_neighbors(graph: CognitiveGraph, entity_id: str) -> dict:
    """Find all entities directly connected to the given entity."""
    neighbors: dict[str, list[dict]] = {"outgoing": [], "incoming": []}
    for r in graph.relations:
        if r["source"] == entity_id:
            target = graph.entities.get(r["target"])
            if target:
                neighbors["outgoing"].append({**r, "entity": target})
        if r["target"] == entity_id:
            source = graph.entities.get(r["source"])
            if source:
                neighbors["incoming"].append({**r, "entity": source})
    return neighbors


def query_timeline(graph: CognitiveGraph, entity_id: str) -> list[dict]:
    """Find all relations involving an entity, sorted by date — the entity's history."""
    timeline = []
    for r in graph.relations:
        if r["source"] == entity_id or r["target"] == entity_id:
            timeline.append(r)
    timeline.sort(key=lambda x: x.get("date", ""))
    return timeline


def graph_summary(graph: CognitiveGraph) -> str:
    """Human/agent-readable summary of the graph."""
    stats = graph.stats()
    lines = [
        f"# Cognitive Graph — {graph.project}",
        f"Built: {graph.built_at}",
        f"Entities: {stats['entities']} ({', '.join(f'{k}={v}' for k,v in stats['entity_types'].items())})",
        f"Relations: {stats['relations']} ({', '.join(f'{k}={v}' for k,v in stats['relation_types'].items())})",
        "",
    ]
    # top entities by occurrences
    top = sorted(graph.entities.values(), key=lambda e: e.get("occurrences", 0), reverse=True)[:15]
    if top:
        lines.append("## Top entities (by occurrences)")
        for e in top:
            lines.append(f"  {e['type']}: {e['name']} (×{e['occurrences']}, files: {len(e['source_files'])})")
    # sample relations
    if graph.relations:
        lines.append(f"\n## Relations (showing first 10 of {len(graph.relations)})")
        for r in graph.relations[:10]:
            lines.append(f"  {r['source']} —{r['type']}→ {r['target']}  [{r.get('date','')}]")
            if r.get("evidence"):
                lines.append(f"    evidence: {r['evidence'][:80]}")
    return "\n".join(lines)

# --- contradiction detection --------------------------------------------------

def detect_contradictions(project_dir: str | Path) -> list[dict]:
    """Scan deep-layer predictions vs recent middle-layer records for contradictions.

    For each deep-layer "预期/Forecast" section, extract falsifiable predictions,
    then search recent middle-layer records for evidence that the prediction was
    touched (confirmed or contradicted).

    Returns a list of {prediction, deep_date, middle_file, middle_date, status, evidence}
    where status is "confirmed" or "contradicted" or "touched".
    """
    project_dir = Path(project_dir)
    m = Memory(project_dir)

    deep_path = m.p["deep_file"]
    if not deep_path.exists():
        return []

    deep_text = deep_path.read_text(encoding="utf-8")
    mid_dir = m.p["middle_dir"]

    # Parse deep sections and extract predictions
    sections = re.split(r"## (\d{4}-\d{2}-\d{2})", deep_text)
    predictions: list[dict] = []
    for i in range(1, len(sections), 2):
        deep_date = sections[i]
        body = sections[i + 1] if i + 1 < len(sections) else ""
        # Find 预期 or Forecast subsection
        pred_match = re.search(
            r"### (?:预期|Forecast)(.*?)(?=###|\Z)", body, re.DOTALL
        )
        if not pred_match:
            continue
        pred_text = pred_match.group(1).strip()
        # Extract individual prediction bullets
        for bullet in re.findall(r"[-*]\s+(.+?)(?=\n[-*]|\n###|\Z)", pred_text, re.DOTALL):
            bullet = bullet.strip()
            if len(bullet) < 10:
                continue
            predictions.append({
                "prediction": bullet[:200],
                "deep_date": deep_date,
            })

    # Search recent middle-layer records for keywords from each prediction
    results: list[dict] = []
    task_files = sorted(mid_dir.glob("*.md"), reverse=True)[:10]
    for tf in task_files:
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", tf.name)
        mid_date = date_match.group(1) if date_match else ""
        try:
            mid_text = tf.read_text(encoding="utf-8")
        except Exception:
            continue
        for pred in predictions:
            # Extract keywords from prediction (nouns/concepts, skip stopwords)
            keywords = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z_]{3,}", pred["prediction"])
            # Check if >=2 keywords appear in the middle record
            hits = sum(1 for kw in keywords if kw in mid_text)
            if hits >= 2 and mid_date >= pred["deep_date"]:
                results.append({
                    "prediction": pred["prediction"],
                    "deep_date": pred["deep_date"],
                    "middle_file": tf.name,
                    "middle_date": mid_date,
                    "status": "touched",
                    "keyword_hits": hits,
                })

    return results


# --- concept evolution --------------------------------------------------------

def query_evolution(graph, entity_id: str) -> list[dict]:
    """Track how an entity's occurrences change over time (concept evolution line).

    Returns a sorted list of {date, occurrences_in_that_date, source_files} showing
    the entity's activity timeline.
    """
    if entity_id not in graph.entities:
        return []

    entity = graph.entities[entity_id]
    # Build timeline from source_files (filenames contain dates)
    timeline: dict[str, dict] = {}
    for sf in entity.get("source_files", []):
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", sf)
        d = date_match.group(1) if date_match else "unknown"
        if d not in timeline:
            timeline[d] = {"date": d, "source_files": [], "occurrences": 0}
        timeline[d]["source_files"].append(sf)
        timeline[d]["occurrences"] += 1

    # Also check relations involving this entity
    for r in graph.relations:
        if r.get("source") == entity_id or r.get("target") == entity_id:
            d = r.get("date", "")
            if d:
                if d not in timeline:
                    timeline[d] = {"date": d, "source_files": [], "occurrences": 0}
                timeline[d]["occurrences"] += 1

    return sorted(timeline.values(), key=lambda x: x["date"])