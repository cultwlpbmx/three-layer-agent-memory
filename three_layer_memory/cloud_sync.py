"""
Cloud sync layer — keep memory libraries consistent across devices.

The paradigm's storage is plain Markdown, git-friendly. Cloud sync builds on
this: instead of inventing a sync protocol, it wraps git operations with
memory-library-specific logic.

Design:
  - Offline-first: all operations are local. Sync happens when network is available.
  - Incremental: git diff is the natural increment — only changed files transfer.
  - Conflict resolution: 
    - Surface/middle files: "last writer wins" (git merge, manual resolve if needed)
    - Deep layer: append-only → never conflicts (both sides' new sections coexist)
    - Cognitive graph: derivative → rebuild after sync, no merge needed
  - Checkpoint sync: .progress/checkpoint.json can sync to enable cross-device resume

Usage:
    from three_layer_memory.cloud_sync import sync_status, sync_push, sync_pull, sync_report

    # Check what needs syncing
    status = sync_status(project_dir)
    print(sync_report(status))

    # Push local changes to remote
    sync_push(project_dir, remote="origin")

    # Pull remote changes
    sync_pull(project_dir, remote="origin")
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from .core import Memory


def _git(project_dir: Path, *args: str) -> tuple[int, str, str]:
    """Run a git command in the project directory. Returns (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            ["git"] + list(args),
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def sync_status(project_dir: str | Path, *, remote: str = "origin") -> dict:
    """Check sync status — what's ahead/behind/diverged.

    Returns {has_remote, ahead, behind, diverged, uncommitted_changes,
             remote_url, last_sync, conflicts}.
    """
    project_dir = Path(project_dir)

    # Check if it's a git repo
    rc, out, err = _git(project_dir, "rev-parse", "--is-inside-work-tree")
    if rc != 0:
        return {"has_git": False, "error": "not a git repository"}

    result: dict = {"has_git": True}

    # Remote URL
    rc, out, _ = _git(project_dir, "remote", "get-url", remote)
    result["remote_url"] = out.strip() if rc == 0 else "(no remote)"
    result["has_remote"] = rc == 0

    # Uncommitted changes
    rc, out, _ = _git(project_dir, "status", "--porcelain")
    changes = [line.strip() for line in out.strip().split("\n") if line.strip()]
    result["uncommitted_changes"] = changes
    result["uncommitted_count"] = len(changes)

    # Ahead/behind (fetch first)
    if result["has_remote"]:
        _git(project_dir, "fetch", remote, "--quiet")
        rc, out, _ = _git(project_dir, "rev-list", "--left-right", "--count",
                          f"{remote}/main...HEAD")
        if rc == 0:
            parts = out.strip().split("\t")
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])
                result["behind"] = behind
                result["ahead"] = ahead
                result["diverged"] = behind > 0 and ahead > 0
            else:
                result["behind"] = 0
                result["ahead"] = 0
                result["diverged"] = False
        else:
            result["behind"] = 0
            result["ahead"] = 0
            result["diverged"] = False
    else:
        result["behind"] = 0
        result["ahead"] = 0
        result["diverged"] = False

    # Last sync (last commit date)
    rc, out, _ = _git(project_dir, "log", "-1", "--format=%ci")
    result["last_commit"] = out.strip() if rc == 0 else "unknown"

    # Conflicts
    rc, out, _ = _git(project_dir, "diff", "--name-only", "--diff-filter=U")
    conflicts = [f for f in out.strip().split("\n") if f.strip()]
    result["conflicts"] = conflicts

    # Memory-specific info
    m = Memory(project_dir)
    result["memory_files"] = _count_memory_files(m)

    return result


def sync_push(project_dir: str | Path, *, remote: str = "origin",
              auto_commit: bool = True, message: str = "") -> dict:
    """Push local memory changes to remote.

    `auto_commit`: if True, stage and commit all memory file changes before push.
    `message`: commit message (auto-generated if empty).

    Returns {pushed, committed, commit_hash, error}.
    """
    project_dir = Path(project_dir)

    # Check if git repo with remote
    rc, _, _ = _git(project_dir, "rev-parse", "--is-inside-work-tree")
    if rc != 0:
        return {"pushed": False, "error": "not a git repository"}

    result: dict = {"pushed": False}

    # Auto-commit if requested
    if auto_commit:
        # Stage all memory files (but not .cognitive-graph or .progress)
        m = Memory(project_dir)
        files_to_stage = []
        for layer_dir in [m.p["overview"].parent, m.p["middle_dir"], m.p["deep_file"].parent]:
            for f in layer_dir.rglob("*.md"):
                files_to_stage.append(str(f))

        if files_to_stage:
            rc, out, err = _git(project_dir, "add", *files_to_stage)
            if rc != 0:
                result["error"] = f"git add failed: {err}"
                return result

        # Commit
        msg = message or f"sync: memory update {os.path.basename(str(project_dir))}"
        rc, out, err = _git(project_dir, "commit", "-m", msg, "--allow-empty")
        result["committed"] = rc == 0
        if rc == 0:
            rc2, hash_out, _ = _git(project_dir, "rev-parse", "HEAD")
            result["commit_hash"] = hash_out.strip()[:8]
        elif "nothing to commit" in err or "nothing to commit" in out:
            result["committed"] = False
            result["nothing_to_commit"] = True

    # Push
    rc, out, err = _git(project_dir, "push", remote, "HEAD")
    result["pushed"] = rc == 0
    if rc != 0:
        result["error"] = err.strip() or out.strip()
    else:
        result["push_output"] = out.strip()

    return result


def sync_pull(project_dir: str | Path, *, remote: str = "origin") -> dict:
    """Pull remote changes and merge.

    Deep layer is append-only → merges cleanly (both sides' new sections coexist).
    Surface/middle may conflict → returns conflict info for manual resolution.

    Returns {pulled, conflicts, error}.
    """
    project_dir = Path(project_dir)

    rc, _, _ = _git(project_dir, "rev-parse", "--is-inside-work-tree")
    if rc != 0:
        return {"pulled": False, "error": "not a git repository"}

    # Fetch
    _git(project_dir, "fetch", remote, "--quiet")

    # Pull with merge
    rc, out, err = _git(project_dir, "pull", remote, "main", "--no-edit")
    result: dict = {"pulled": rc == 0}

    if rc != 0:
        # Check for conflicts
        rc2, conflict_out, _ = _git(project_dir, "diff", "--name-only", "--diff-filter=U")
        conflicts = [f for f in conflict_out.strip().split("\n") if f.strip()]
        result["conflicts"] = conflicts
        result["error"] = err.strip() or out.strip()
    else:
        result["conflicts"] = []
        result["pull_output"] = out.strip()

    return result


def _count_memory_files(m: Memory) -> dict:
    """Count memory files by layer."""
    counts: dict[str, int] = {"surface": 0, "middle": 0, "deep": 0, "graph": 0, "progress": 0}

    surf_dir = m.p["overview"].parent
    counts["surface"] = len(list(surf_dir.glob("*.md")))

    mid_dir = m.p["middle_dir"]
    counts["middle"] = len([f for f in mid_dir.glob("*.md") if not f.name.startswith("_") and not f.name.startswith("INDEX")])

    deep_dir = m.p["deep_file"].parent
    counts["deep"] = len(list(deep_dir.glob("*.md")))

    graph_dir = Path(m.root) / ".cognitive-graph"
    if graph_dir.exists():
        counts["graph"] = len(list(graph_dir.glob("*")))

    progress_dir = Path(m.root) / ".progress"
    if progress_dir.exists():
        counts["progress"] = len(list(progress_dir.glob("*.json")))

    return counts


def sync_report(status: dict) -> str:
    """Render sync status as a human/agent-readable report."""
    if not status.get("has_git", True):
        return f"[sync] {status.get('error', 'not a git repo')}"

    lines = [
        f"# Cloud Sync Status",
        f"Remote: {status.get('remote_url', '(none)')}",
        f"Last commit: {status.get('last_commit', 'unknown')}",
        f"Ahead: {status.get('ahead', 0)} | Behind: {status.get('behind', 0)} | Diverged: {status.get('diverged', False)}",
        f"Uncommitted changes: {status.get('uncommitted_count', 0)}",
    ]

    if status.get("uncommitted_changes"):
        lines.append("  Changed files:")
        for f in status["uncommitted_changes"][:10]:
            lines.append(f"    {f}")

    if status.get("conflicts"):
        lines.append(f"\n⚠ Conflicts ({len(status['conflicts'])})")
        for c in status["conflicts"]:
            lines.append(f"    {c}")

    mem = status.get("memory_files", {})
    if mem:
        lines.append(f"\nMemory files: surface={mem.get('surface',0)} middle={mem.get('middle',0)} "
                      f"deep={mem.get('deep',0)} graph={mem.get('graph',0)} progress={mem.get('progress',0)}")

    if status.get("diverged"):
        lines.append("\n⚠ Diverged — pull first, resolve conflicts, then push.")
    elif status.get("ahead", 0) > 0:
        lines.append("\n→ Local is ahead — push to sync.")
    elif status.get("behind", 0) > 0:
        lines.append("\n→ Local is behind — pull to sync.")
    elif status.get("uncommitted_count", 0) > 0:
        lines.append("\n→ Uncommitted changes — commit and push to sync.")
    else:
        lines.append("\n✅ In sync with remote.")

    return "\n".join(lines)