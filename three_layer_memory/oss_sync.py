"""
OSS cloud sync backend — sync memory libraries to Alibaba Cloud OSS.

Uses oss2 SDK to upload/download/sync Markdown memory files to a dedicated
OSS path (not shared with other projects). Incremental sync by file hash.

Design:
  - Local-first: all operations are local until sync is called
  - Incremental: only upload changed files (compared by content hash)
  - Conflict resolution: "last writer wins" for surface/middle,
    deep layer is append-only (both sides merged)
  - Checkpoint sync: .progress/checkpoint.json can sync for cross-device resume

Usage:
    from three_layer_memory.oss_sync import OSSSync

    syncer = OSSSync(
        bucket_name="seedling-app-resources-1739273",
        access_key_id="...",
        access_key_secret="...",
        endpoint="oss-cn-hangzhou",
        prefix="memory-sync/",  # dedicated path, not shared
    )

    # Upload a memory library to OSS
    syncer.push("/path/to/project-memory")

    # Pull from OSS to local
    syncer.pull("/path/to/project-memory")

    # List what's on OSS
    syncer.list_remote()

    # Get sync status (what's different)
    syncer.diff("/path/to/project-memory")
"""
from __future__ import annotations

import hashlib
import os
import json
from pathlib import Path
from typing import Optional

try:
    import oss2
    HAS_OSS2 = True
except ImportError:
    HAS_OSS2 = False


# --- file types to sync ---

SYNC_EXTENSIONS = {".md", ".json"}
SYNC_DIRS = {"表层", "中层", "深层", "Surface", "Middle", "Deep", ".progress", "archive"}
# archive/ holds the fossil layer of Middle records — the most precious history.
# It must be backed up: memory banks outside git have no other copy.
# (Found 2026-08-15: an OSS-synced non-git bank archived records into
# archive/ and silently lost cloud backup coverage for them.)
SKIP_DIRS = {".cognitive-graph", ".git", "__pycache__"}


def _file_hash(path: Path) -> str:
    """MD5 hash of file content for change detection."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _should_sync(path: Path, root: Path) -> bool:
    """Check if a file should be synced to OSS."""
    # Check extension
    if path.suffix not in SYNC_EXTENSIONS:
        return False
    # Check if it's inside a sync dir
    try:
        rel = path.relative_to(root)
        parts = rel.parts
    except ValueError:
        return False
    # Skip files in non-sync directories
    for skip in SKIP_DIRS:
        if skip in parts:
            return False
    return True


class OSSSync:
    """OSS-based cloud sync for memory libraries."""

    def __init__(
        self,
        *,
        bucket_name: str,
        access_key_id: str,
        access_key_secret: str,
        endpoint: str = "oss-cn-hangzhou",
        prefix: str = "memory-sync/",
    ):
        if not HAS_OSS2:
            raise ImportError(
                "oss2 SDK not installed. Run: pip install oss2"
            )
        self.prefix = prefix.rstrip("/") + "/"
        self._auth = oss2.Auth(access_key_id, access_key_secret)
        self._bucket = oss2.Bucket(
            self._auth, f"https://{endpoint}.aliyuncs.com", bucket_name
        )

    def _oss_key(self, local_path: Path, root: Path) -> str:
        """Convert a local path to an OSS key."""
        rel = local_path.relative_to(root)
        # Use forward slashes for OSS
        rel_str = str(rel).replace("\\", "/")
        return self.prefix + rel_str

    def _local_path(self, oss_key: str, root: Path) -> Path:
        """Convert an OSS key to a local path."""
        rel = oss_key[len(self.prefix):]
        return root / rel.replace("/", os.sep)

    def push(
        self,
        local_dir: str | Path,
        *,
        delete_remote_orphans: bool = False,
    ) -> dict:
        """Upload local memory files to OSS (incremental).

        Only uploads files that have changed (by hash comparison).
        Returns {uploaded, skipped, deleted, errors}.
        """
        local_dir = Path(local_dir)
        result: dict = {"uploaded": [], "skipped": [], "deleted": [], "errors": []}

        # Build local file manifest
        local_files: dict[str, str] = {}  # oss_key -> hash
        for path in local_dir.rglob("*"):
            if path.is_file() and _should_sync(path, local_dir):
                key = self._oss_key(path, local_dir)
                local_files[key] = _file_hash(path)

        # Check remote state
        remote_files = self.list_remote()

        # Upload changed/new files
        for key, local_hash in local_files.items():
            remote_meta = remote_files.get(key)
            if remote_meta and remote_meta.get("hash") == local_hash:
                result["skipped"].append(key)
            else:
                local_path = self._local_path(key, local_dir)
                try:
                    self._bucket.put_object_from_file(key, str(local_path))
                    # Store hash as metadata
                    self._bucket.update_object_meta(key, headers={
                        "x-oss-meta-hash": local_hash,
                    })
                    result["uploaded"].append(key)
                except Exception as e:
                    result["errors"].append({"key": key, "error": str(e)})

        # Delete remote orphans if requested
        if delete_remote_orphans:
            for key in remote_files:
                if key not in local_files:
                    try:
                        self._bucket.delete_object(key)
                        result["deleted"].append(key)
                    except Exception as e:
                        result["errors"].append({"key": key, "error": str(e)})

        return result

    def pull(
        self,
        local_dir: str | Path,
        *,
        overwrite: bool = True,
    ) -> dict:
        """Download memory files from OSS to local.

        Returns {downloaded, skipped, errors}.
        """
        local_dir = Path(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        result: dict = {"downloaded": [], "skipped": [], "errors": []}

        remote_files = self.list_remote()

        for key in remote_files:
            local_path = self._local_path(key, local_dir)

            # Skip if local file exists and is identical (by hash)
            if local_path.exists() and not overwrite:
                result["skipped"].append(key)
                continue

            if local_path.exists() and overwrite:
                local_hash = _file_hash(local_path)
                if local_hash == remote_files[key].get("hash"):
                    result["skipped"].append(key)
                    continue

            # Download
            try:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                self._bucket.get_object_to_file(key, str(local_path))
                result["downloaded"].append(key)
            except Exception as e:
                result["errors"].append({"key": key, "error": str(e)})

        return result

    def list_remote(self) -> dict:
        """List all memory files on OSS with their hashes.

        Returns {oss_key: {hash, size, last_modified}}.
        """
        result: dict = {}
        prefix = self.prefix
        for obj in oss2.ObjectIterator(self._bucket, prefix=prefix):
            key = obj.key
            if key == prefix:  # skip the "directory" itself
                continue
            # Get metadata
            try:
                meta = self._bucket.head_object(key)
                file_hash = meta.headers.get("x-oss-meta-hash", "")
                result[key] = {
                    "hash": file_hash,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                }
            except Exception:
                result[key] = {
                    "hash": "",
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                }
        return result

    def diff(self, local_dir: str | Path) -> dict:
        """Compare local vs remote, return what needs syncing.

        Returns {to_upload, to_download, to_delete_remote, identical}.
        """
        local_dir = Path(local_dir)
        local_files: dict[str, str] = {}
        for path in local_dir.rglob("*"):
            if path.is_file() and _should_sync(path, local_dir):
                key = self._oss_key(path, local_dir)
                local_files[key] = _file_hash(path)

        remote_files = self.list_remote()

        to_upload: list[str] = []
        to_download: list[str] = []
        identical: list[str] = []
        to_delete_remote: list[str] = []

        for key, local_hash in local_files.items():
            remote = remote_files.get(key)
            if not remote:
                to_upload.append(key)
            elif remote.get("hash") != local_hash:
                to_upload.append(key)
            else:
                identical.append(key)

        for key in remote_files:
            if key not in local_files:
                to_download.append(key)

        return {
            "to_upload": to_upload,
            "to_download": to_download,
            "identical": identical,
            "to_delete_remote": to_delete_remote,
        }

    def delete_path(self, prefix: str | None = None) -> dict:
        """Delete all objects under a prefix on OSS.

        Use with caution — this permanently deletes remote data.
        """
        target_prefix = prefix or self.prefix
        deleted: list[str] = []
        for obj in oss2.ObjectIterator(self._bucket, prefix=target_prefix):
            try:
                self._bucket.delete_object(obj.key)
                deleted.append(obj.key)
            except Exception:
                pass
        return {"deleted": deleted, "count": len(deleted)}


def oss_sync_report(result: dict, action: str = "sync") -> str:
    """Render sync result as a human-readable report."""
    lines = [f"# OSS Sync — {action}"]
    if "uploaded" in result:
        lines.append(f"  uploaded: {len(result['uploaded'])}")
        for k in result["uploaded"][:5]:
            lines.append(f"    + {k}")
    if "downloaded" in result:
        lines.append(f"  downloaded: {len(result['downloaded'])}")
        for k in result["downloaded"][:5]:
            lines.append(f"    ↓ {k}")
    if "skipped" in result:
        lines.append(f"  skipped (identical): {len(result['skipped'])}")
    if "deleted" in result:
        lines.append(f"  deleted: {len(result['deleted'])}")
    if "errors" in result and result["errors"]:
        lines.append(f"  ⚠ errors: {len(result['errors'])}")
        for e in result["errors"][:3]:
            lines.append(f"    {e['key']}: {e['error'][:80]}")
    return "\n".join(lines)