"""
Auto-sync layer — transparent OSS sync for agent memory operations.

The agent uses Memory as normal (recall/log/consolidate). AutoSync wraps it
and handles OSS pull/push transparently:
  - recall() → pull from OSS first, then read local
  - log() → write local, then push to OSS
  - consolidate() → write local, then push to OSS
  - checkpoint heartbeat → push checkpoint to OSS

The agent never needs to know OSS exists. It just calls recall/log/consolidate.

Usage:
    from three_layer_memory import Memory
    from three_layer_memory.auto_sync import AutoSync

    m = AutoSync(
        Memory("/path/to/project-memory"),
        bucket="agent-memory-sync",
        access_key_id="...",
        access_key_secret="...",
        endpoint="oss-cn-hangzhou",
        device_id="my-laptop",
    )
    r = m.recall()    # auto pull → read
    m.log(...)        # write → auto push
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .core import Memory
from .oss_sync import OSSSync


class SyncVersion:
    """Version tracking for multi-device sync.

    Stores .sync-version.json in the memory library root.
    Version increments on every push. Device ID distinguishes sources.
    """

    def __init__(self, library_dir: Path, device_id: str = "unknown"):
        self.path = library_dir / ".sync-version.json"
        self.device_id = device_id

    def read_local(self) -> dict:
        if not self.path.exists():
            return {"version": 0, "last_sync": "", "device_id": self.device_id, "files_hash": ""}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def write_local(self, version: int, files_hash: str = ""):
        data = {
            "version": version,
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "device_id": self.device_id,
            "files_hash": files_hash,
        }
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
        return data

    def read_remote(self, syncer: OSSSync) -> dict:
        """Read version from OSS (if exists)."""
        import oss2
        key = syncer.prefix + ".sync-version.json"
        try:
            result = syncer._bucket.get_object(key)
            return json.loads(result.read().decode("utf-8"))
        except Exception:
            return {"version": 0, "last_sync": "", "device_id": "", "files_hash": ""}

    def write_remote(self, syncer: OSSSync, version: int, files_hash: str = ""):
        """Write version to OSS."""
        data = self.write_local(version, files_hash)
        key = syncer.prefix + ".sync-version.json"
        syncer._bucket.put_object(key, json.dumps(data, ensure_ascii=False))

    @staticmethod
    def compute_hash(library_dir: Path) -> str:
        """Compute a hash of all memory files for change detection."""
        import hashlib
        h = hashlib.md5()
        for path in sorted(library_dir.rglob("*.md")):
            if any(skip in str(path) for skip in [".git", ".cognitive-graph", ".sync-version"]):
                continue
            h.update(path.name.encode())
            h.update(path.read_bytes())
        return h.hexdigest()


class AutoSync:
    """Wraps Memory with transparent OSS sync.

    All Memory methods are proxied. recall() pulls first, log/consolidate push after.
    """

    def __init__(
        self,
        memory: Memory,
        *,
        bucket: str = "agent-memory-sync",
        access_key_id: str = "",
        access_key_secret: str = "",
        endpoint: str = "oss-cn-hangzhou",
        device_id: str = "unknown",
        auto_pull: bool = True,
        auto_push: bool = True,
    ):
        self.memory = memory
        self.device_id = device_id
        self.auto_pull = auto_pull
        self.auto_push = auto_push

        if access_key_id and access_key_secret:
            project_name = memory.root.name
            self.syncer = OSSSync(
                bucket_name=bucket,
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                endpoint=endpoint,
                prefix=project_name + "/",
            )
            self.version = SyncVersion(memory.root, device_id)
        else:
            self.syncer = None
            self.version = None

    def _maybe_pull(self):
        """Pull from OSS if remote version > local."""
        if not self.syncer or not self.auto_pull:
            return
        local_v = self.version.read_local()
        remote_v = self.version.read_remote(self.syncer)
        if remote_v.get("version", 0) > local_v.get("version", 0):
            self.syncer.pull(self.memory.root)

    def _maybe_push(self):
        """Push to OSS after local write."""
        if not self.syncer or not self.auto_push:
            return
        local_v = self.version.read_local()
        new_version = local_v.get("version", 0) + 1
        files_hash = SyncVersion.compute_hash(self.memory.root)
        self.syncer.push(self.memory.root, delete_remote_orphans=True)
        self.version.write_remote(self.syncer, new_version, files_hash)

    # === proxied Memory methods ===

    def recall(self, **kw):
        self._maybe_pull()
        return self.memory.recall(**kw)

    def log(self, **kw):
        result = self.memory.log(**kw)
        self._maybe_push()
        return result

    def consolidate(self, **kw):
        result = self.memory.consolidate(**kw)
        self._maybe_push()
        return result

    def validate(self):
        return self.memory.validate()

    def snapshot(self, output_path, **kw):
        return self.memory.snapshot(output_path, **kw)

    def claim(self, **kw):
        return self.memory.claim(**kw)

    def release(self, **kw):
        return self.memory.release(**kw)

    # === sync-specific methods ===

    def force_pull(self):
        """Manually pull from OSS regardless of version."""
        if self.syncer:
            return self.syncer.pull(self.memory.root)
        return {"error": "no syncer configured"}

    def force_push(self):
        """Manually push to OSS."""
        if self.syncer:
            result = self.syncer.push(self.memory.root, delete_remote_orphans=True)
            local_v = self.version.read_local()
            new_version = local_v.get("version", 0) + 1
            files_hash = SyncVersion.compute_hash(self.memory.root)
            self.version.write_remote(self.syncer, new_version, files_hash)
            return result
        return {"error": "no syncer configured"}

    def sync_status(self) -> dict:
        """Check local vs remote version."""
        if not self.syncer:
            return {"error": "no syncer configured"}
        local_v = self.version.read_local()
        remote_v = self.version.read_remote(self.syncer)
        return {
            "local_version": local_v.get("version", 0),
            "remote_version": remote_v.get("version", 0),
            "local_device": local_v.get("device_id", ""),
            "remote_device": remote_v.get("device_id", ""),
            "needs_pull": remote_v.get("version", 0) > local_v.get("version", 0),
            "needs_push": local_v.get("version", 0) > remote_v.get("version", 0),
            "conflict": (
                remote_v.get("version", 0) > local_v.get("version", 0)
                and local_v.get("version", 0) > 0
                and remote_v.get("device_id", "") != local_v.get("device_id", "")
            ),
        }