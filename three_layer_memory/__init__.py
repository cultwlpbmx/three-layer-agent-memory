"""
Three-Layer Agent Memory — reference library.

A minimal, dependency-free, importable implementation of the three protocol
checkpoints (see PROTOCOL.md). Storage is plain Markdown on disk: human-readable,
git-diffable, zero infrastructure. This package wraps the read/write/validate
mechanics so any Python agent can adopt the paradigm with one import.

    from three_layer_memory import Memory, recall, log, consolidate, validate, init

    # on_session_start
    r = Memory("/path/to/project-memory").recall()
    print(r.as_prompt_block())        # inject into model context

    # on_milestone
    Memory("/path/...").log(version="V0.1", summary="first task",
                              tags=("#auth", "#deploy"))

    # on_day_end
    Memory("/path/...").consolidate(topic="kickoff", review="...",
                                      plan="...", risk="...", forecast="...")

The three basic questions (what is this project / where are we / what's next)
are already answered by recall()'s `overview` + `todo` + `last_deep` fields —
no separate brief() is needed.

Concurrency (see roadmap §8): the structure resolves most concurrent writes —
middle-layer task records are uniquely named (zero collision), deep layer is
append-only (atomic append), surface todo is by design single-writer (only
consolidate touches it). An opt-in claim() is provided as a stub escape hatch.

Locale-aware: auto-detects Chinese (表层/中层/深层) or English (Surface/Middle/Deep).
"""
from .core import (
    Memory,
    RecallResult,
    ValidationResult,
    ZH,
    EN,
    detect_locale,
    recall,
    log,
    consolidate,
    validate,
    aggregate,
)
from .init import init
from .snapshot import snapshot
from .graph import (
    build_graph,
    load_graph,
    query_entities,
    query_relations,
    query_neighbors,
    query_timeline,
    graph_summary,
    CognitiveGraph,
    detect_contradictions,
    query_evolution,
)
from .auto_activation import activate, activation_summary
from .deviation_monitor import check_deviation, deviation_report
from .auto_consolidate import discover_patterns, pattern_report
from .reflection_quality import assess_reflections, quality_report
from .meta_meta_cognition import discover_blind_spots, blind_spot_report
from .cross_project import transfer_knowledge, transfer_report
from .prediction_tracker import track_predictions, prediction_report
from .self_correction import find_stale_laws, correction_report
from .revisit import find_unrevisited, revisit_report
from .cloud_sync import sync_status, sync_push, sync_pull, sync_report
from .oss_sync import OSSSync, oss_sync_report
from .auto_sync import AutoSync, SyncVersion
from .sync_coordinator import SyncCoordinator
from .checkpoint import (
    create_checkpoint,
    heartbeat,
    complete_step,
    finish_checkpoint,
    restore_checkpoint,
    restore_summary,
)

__version__ = "0.8.3"

__all__ = [
    "Memory",
    "RecallResult",
    "ValidationResult",
    "ZH",
    "EN",
    "detect_locale",
    "recall",
    "log",
    "consolidate",
    "validate",
    "aggregate",
    "init",
    "snapshot",
    "create_checkpoint",
    "heartbeat",
    "complete_step",
    "finish_checkpoint",
    "restore_checkpoint",
    "restore_summary",
    "build_graph",
    "load_graph",
    "query_entities",
    "query_relations",
    "query_neighbors",
    "query_timeline",
    "graph_summary",
    "CognitiveGraph",
    "detect_contradictions",
    "query_evolution",
    "activate",
    "activation_summary",
    "check_deviation",
    "deviation_report",
    "discover_patterns",
    "pattern_report",
    "assess_reflections",
    "quality_report",
    "discover_blind_spots",
    "blind_spot_report",
    "transfer_knowledge",
    "transfer_report",
    "track_predictions",
    "prediction_report",
    "find_stale_laws",
    "correction_report",
    "find_unrevisited",
    "revisit_report",
    "sync_status",
    "sync_push",
    "sync_pull",
    "sync_report",
    "OSSSync",
    "oss_sync_report",
    "AutoSync",
    "SyncVersion",
    "SyncCoordinator",
    "__version__",
]