"""Finding workspaceStorage/<hash> folders — both for auto-discovering a
newly created workspace's hash, and for enumerating every source
workspace available for merging."""

import json
import urllib.parse
from pathlib import Path


def find_new_workspace_hash(
    target_folder_path: str, storage_base: Path, max_candidates: int = 5
) -> str | None:
    """
    Find the workspaceStorage/<hash> folder VS Code just created for
    target_folder_path, by scanning candidates newest-first (by mtime)
    and verifying against workspace.json content. Stops at first match,
    so in the common case (you just opened it) this checks only 1-2
    folders instead of the entire workspaceStorage directory.
    """
    target_norm = str(Path(target_folder_path).resolve()).rstrip("/")

    candidates = sorted(
        (d for d in storage_base.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

    checked = 0
    for hash_dir in candidates:
        if checked >= max_candidates:
            break
        wj = hash_dir / "workspace.json"
        if not wj.exists():
            continue
        checked += 1
        try:
            data = json.loads(wj.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        folder_uri = data.get("folder", "")
        if not folder_uri.startswith("file://"):
            continue
        decoded = urllib.parse.unquote(folder_uri[len("file://"):]).rstrip("/")
        if decoded == target_norm:
            return hash_dir.name

    return None


def discover_all_sources(storage_base: Path, exclude_hashes: set[str]) -> list[Path]:
    """
    Find every workspaceStorage/<hash> folder that has a state.vscdb,
    excluding the target(s) so we never merge a workspace into itself.
    """
    if not storage_base.exists():
        raise RuntimeError(
            f"--storage-base does not exist: {storage_base}\n"
            "Check the path, or omit --storage-base to use the default VS Code location."
        )
    if not storage_base.is_dir():
        raise RuntimeError(f"--storage-base is not a directory: {storage_base}")

    sources = []
    for d in sorted(storage_base.iterdir()):
        if not d.is_dir() or d.name in exclude_hashes:
            continue
        if (d / "state.vscdb").exists():
            sources.append(d)
    return sources
