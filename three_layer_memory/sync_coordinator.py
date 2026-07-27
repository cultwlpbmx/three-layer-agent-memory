"""
Sync coordinator — one-command full sync of code (GitHub) + memory (OSS).

Coordinates two sync backends:
  - GitHub (git push/pull) for code repository
  - OSS (oss_sync) for memory libraries

Usage:
    from three_layer_memory.sync_coordinator import SyncCoordinator

    coord = SyncCoordinator(
        code_repo="/path/to/three-layer-agent-memory",
        memory_libraries=["/path/to/lib1", "/path/to/lib2"],
        oss_config={...},
    )
    coord.sync_all()  # push code to GitHub + push memory to OSS
    coord.status_all()  # check both
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from .cloud_sync import sync_status, sync_push, sync_pull, sync_report
from .oss_sync import OSSSync, oss_sync_report


class SyncCoordinator:
    """Coordinate GitHub (code) + OSS (memory) sync."""

    def __init__(
        self,
        code_repo: str | Path,
        memory_libraries: list[str | Path],
        *,
        bucket: str = "agent-memory-sync",
        access_key_id: str = "",
        access_key_secret: str = "",
        endpoint: str = "oss-cn-hangzhou",
        device_id: str = "unknown",
    ):
        self.code_repo = Path(code_repo)
        self.memory_libraries = [Path(lib) for lib in memory_libraries]
        self.device_id = device_id

        self.oss_config = {
            "bucket": bucket,
            "access_key_id": access_key_id,
            "access_key_secret": access_key_secret,
            "endpoint": endpoint,
        }

    def sync_all(self, *, direction: str = "push") -> dict:
        """Sync everything: code to GitHub + memory to OSS.

        direction: "push" (local→remote) or "pull" (remote→local).
        """
        result: dict = {"direction": direction, "github": {}, "oss": {}}

        # --- GitHub sync (code repo) ---
        if direction == "push":
            r = sync_push(self.code_repo, auto_commit=True,
                          message=f"sync: {self.device_id} auto-sync")
            result["github"] = r
        elif direction == "pull":
            r = sync_pull(self.code_repo)
            result["github"] = r

        # --- OSS sync (memory libraries) ---
        for lib in self.memory_libraries:
            lib_name = lib.name
            syncer = OSSSync(
                bucket_name=self.oss_config["bucket"],
                access_key_id=self.oss_config["access_key_id"],
                access_key_secret=self.oss_config["access_key_secret"],
                endpoint=self.oss_config["endpoint"],
                prefix=lib_name + "/",
            )
            if direction == "push":
                r = syncer.push(lib, delete_remote_orphans=True)
                result["oss"][lib_name] = {
                    "uploaded": len(r.get("uploaded", [])),
                    "skipped": len(r.get("skipped", [])),
                    "errors": len(r.get("errors", [])),
                }
            elif direction == "pull":
                r = syncer.pull(lib)
                result["oss"][lib_name] = {
                    "downloaded": len(r.get("downloaded", [])),
                    "skipped": len(r.get("skipped", [])),
                }

        return result

    def status_all(self) -> dict:
        """Check sync status of both GitHub and OSS."""
        result: dict = {"github": {}, "oss": {}}

        # GitHub status
        gh = sync_status(self.code_repo)
        result["github"] = {
            "has_remote": gh.get("has_remote", False),
            "ahead": gh.get("ahead", 0),
            "behind": gh.get("behind", 0),
            "uncommitted": gh.get("uncommitted_count", 0),
        }

        # OSS status per library
        for lib in self.memory_libraries:
            lib_name = lib.name
            syncer = OSSSync(
                bucket_name=self.oss_config["bucket"],
                access_key_id=self.oss_config["access_key_id"],
                access_key_secret=self.oss_config["access_key_secret"],
                endpoint=self.oss_config["endpoint"],
                prefix=lib_name + "/",
            )
            remote = syncer.list_remote()
            local_count = 0
            if lib.exists():
                local_count = sum(1 for f in lib.rglob("*.md")
                                  if ".git" not in str(f) and ".cognitive-graph" not in str(f))
            result["oss"][lib_name] = {
                "remote_files": len(remote),
                "local_files": local_count,
            }

        return result

    def report(self, status: dict) -> str:
        """Render status as human-readable."""
        lines = ["# Sync Coordinator — Status"]

        gh = status.get("github", {})
        lines.append(f"\n## GitHub (code)")
        lines.append(f"  remote: {gh.get('has_remote', False)}")
        lines.append(f"  ahead: {gh.get('ahead', 0)} | behind: {gh.get('behind', 0)}")
        lines.append(f"  uncommitted: {gh.get('uncommitted', 0)}")

        lines.append(f"\n## OSS (memory)")
        for lib_name, info in status.get("oss", {}).items():
            lines.append(f"  {lib_name}: remote={info['remote_files']} local={info['local_files']}")

        return "\n".join(lines)