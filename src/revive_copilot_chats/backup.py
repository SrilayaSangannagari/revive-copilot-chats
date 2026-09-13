"""Backing up the one file this tool ever writes to."""

import shutil
from pathlib import Path


def backup_target_state_db(target_db: Path) -> Path | None:
    """
    Backs up only the target's own state.vscdb before we write to it —
    that's the only file this script ever modifies. Sources are always
    read-only, so there's nothing to protect there. This keeps the backup
    small (a single SQLite file, typically KB-MB) instead of copying the
    entire workspaceStorage tree (which can be GBs across every project
    you've ever opened). Overwritten each run, same fixed filename.
    """
    if not target_db.exists():
        return None  # brand-new workspace, nothing to back up yet

    backup_path = target_db.with_name("state.vscdb.backup")
    try:
        shutil.copy2(target_db, backup_path)
    except OSError as e:
        raise OSError(f"Failed to back up {target_db} to {backup_path}: {e}") from e
    print(
        f"Backed up target state.vscdb -> {backup_path} "
        f"({backup_path.stat().st_size / 1024:.1f} KB)\n"
    )
    return backup_path
