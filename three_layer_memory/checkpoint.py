"""
Checkpoint layer — real-time working-progress memory.

Solves the "agent loses progress on interruption" problem. The three formal
layers (Surface/Middle/Deep) only record *completed* work. This layer records
*in-progress* work, atomically, so that on power loss / network drop / compute
exhaustion, the next session can resume from the last checkpoint.

Design:
  <project-library>/.progress/
    checkpoint.json         # current session (atomically written)
    archive/                # completed sessions (moved here on writeback)

This is NOT a fourth formal layer — it is a temporary working area. Completed
work still goes through the normal writeback (middle-layer record). Checkpoint
only prevents loss of in-flight progress.

Offline-first: local file, no network dependency.
Idempotent: checkpoint is a *clue*, not a state machine — resume can continue
from the interrupted point or restart from scratch.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _progress_dir(project_dir: str | Path) -> Path:
    """Return the .progress directory, creating it if needed."""
    d = Path(project_dir) / ".progress"
    d.mkdir(parents=True, exist_ok=True)
    (d / "archive").mkdir(exist_ok=True)
    return d


def _atomic_write_json(path: Path, data: dict) -> None:
    """Atomically write JSON to avoid corruption on power loss mid-write."""
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # os.replace is atomic on the same filesystem
    os.replace(tmp, path)


def create_checkpoint(
    project_dir: str | Path,
    *,
    task: str,
    agent: str = "unknown",
    steps: list[str] | None = None,
) -> dict:
    """Start a new working session checkpoint.

    Returns the checkpoint dict (also written to disk).
    """
    d = _progress_dir(project_dir)
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    cp = {
        "session_id": session_id,
        "agent": agent,
        "task": task,
        "started_at": now,
        "last_heartbeat": now,
        "status": "in_progress",
        "completed_steps": [],
        "current_step": steps[0] if steps else "",
        "pending_steps": steps[1:] if steps and len(steps) > 1 else [],
        "artifacts": {},
        "context_notes": "",
        "reasoning_snapshot": "",
        "parent_checkpoint": None,
    }
    _atomic_write_json(d / "checkpoint.json", cp)
    return cp


def heartbeat(
    project_dir: str | Path,
    *,
    current_step: str = "",
    completed_steps: list[str] | None = None,
    pending_steps: list[str] | None = None,
    context_notes: str = "",
    artifacts: dict | None = None,
    reasoning_snapshot: str = "",
) -> Optional[dict]:
    """Update the checkpoint with current progress. Call every 30s or per step.

    Only updates fields that are provided (non-empty/non-None). Returns the
    updated checkpoint, or None if no checkpoint exists.
    """
    d = _progress_dir(project_dir)
    cp_path = d / "checkpoint.json"
    if not cp_path.exists():
        return None
    cp = json.loads(cp_path.read_text(encoding="utf-8"))
    cp["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
    if current_step:
        cp["current_step"] = current_step
    if completed_steps is not None:
        cp["completed_steps"] = completed_steps
    if pending_steps is not None:
        cp["pending_steps"] = pending_steps
    if context_notes:
        cp["context_notes"] = context_notes
    if artifacts:
        cp["artifacts"].update(artifacts)
    if reasoning_snapshot:
        cp["reasoning_snapshot"] = reasoning_snapshot
    _atomic_write_json(cp_path, cp)
    return cp


def complete_step(
    project_dir: str | Path,
    step: str,
    *,
    context_notes: str = "",
    artifacts: dict | None = None,
) -> Optional[dict]:
    """Mark a step as completed and advance to the next pending step."""
    d = _progress_dir(project_dir)
    cp_path = d / "checkpoint.json"
    if not cp_path.exists():
        return None
    cp = json.loads(cp_path.read_text(encoding="utf-8"))
    if step not in cp["completed_steps"]:
        cp["completed_steps"].append(step)
    # advance current step
    if cp["pending_steps"]:
        cp["current_step"] = cp["pending_steps"].pop(0)
    else:
        cp["current_step"] = ""
    cp["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
    if context_notes:
        cp["context_notes"] = context_notes
    if artifacts:
        cp["artifacts"].update(artifacts)
    _atomic_write_json(cp_path, cp)
    return cp


def finish_checkpoint(project_dir: str | Path) -> Optional[dict]:
    """Mark the checkpoint as completed and move it to archive.

    Call after writeback (middle-layer record) is done.
    """
    d = _progress_dir(project_dir)
    cp_path = d / "checkpoint.json"
    if not cp_path.exists():
        return None
    cp = json.loads(cp_path.read_text(encoding="utf-8"))
    cp["status"] = "completed"
    cp["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
    # move to archive
    archive_name = f"checkpoint_{cp['session_id'][:8]}.json"
    archive_path = d / "archive" / archive_name
    _atomic_write_json(archive_path, cp)
    cp_path.unlink()
    return cp


def restore_checkpoint(project_dir: str | Path, *, stale_threshold_min: int = 5) -> Optional[dict]:
    """Read the current checkpoint for session recovery.

    Returns the checkpoint if:
      - it exists
      - status is "in_progress"
      - last_heartbeat is older than stale_threshold_min (likely interrupted)

    Returns None if no checkpoint, already completed, or still active (not stale).
    The caller should inject the returned dict into context as "last session
    was interrupted while doing X, completed Y, remaining Z".
    """
    d = _progress_dir(project_dir)
    cp_path = d / "checkpoint.json"
    if not cp_path.exists():
        return None
    cp = json.loads(cp_path.read_text(encoding="utf-8"))
    if cp["status"] != "in_progress":
        return None
    # check staleness
    last = datetime.fromisoformat(cp["last_heartbeat"])
    now = datetime.now(timezone.utc)
    age_min = (now - last).total_seconds() / 60
    if age_min < stale_threshold_min:
        return None  # still active, not interrupted
    cp["_age_minutes"] = round(age_min, 1)
    return cp


def restore_summary(cp: dict) -> str:
    """Render a checkpoint as a human/agent-readable recovery summary."""
    lines = [
        f"[INTERRUPTED SESSION] task: {cp['task']}",
        f"  agent: {cp['agent']}, interrupted ~{cp.get('_age_minutes', '?')} min ago",
        f"  completed: {', '.join(cp['completed_steps']) or '(none)'}",
        f"  was working on: {cp['current_step']}",
        f"  remaining: {', '.join(cp['pending_steps']) or '(none)'}",
    ]
    if cp.get("context_notes"):
        lines.append(f"  notes: {cp['context_notes']}")
    if cp.get("reasoning_snapshot"):
        lines.append(f"  reasoning: {cp['reasoning_snapshot'][:200]}...")
    if cp.get("artifacts"):
        lines.append(f"  artifacts: {json.dumps(cp['artifacts'], ensure_ascii=False)}")
    lines.append("  → Resume from interrupted point, or restart if artifacts are invalid.")
    return "\n".join(lines)