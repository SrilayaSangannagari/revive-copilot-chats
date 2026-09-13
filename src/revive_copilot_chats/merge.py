"""Core merge logic: the state.vscdb chat index, session folder contents,
and the top-level orchestration that ties a whole revive run together."""

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from .constants import CHAT_INDEX_KEY, FOLDERS_TO_MERGE
from .dates import filter_entries_by_date


# ---------- state.vscdb index merge ----------

def read_chat_index(db_path: Path) -> dict:
    if not db_path.exists():
        return {"version": 1, "entries": {}}
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM ItemTable WHERE key = ?", (CHAT_INDEX_KEY,))
        row = cur.fetchone()
        if not row:
            return {"version": 1, "entries": {}}
        return json.loads(row[0])
    finally:
        conn.close()


def merge_indexes(target_index: dict, source_index: dict, source_label: str) -> dict:
    merged = {
        "version": target_index.get("version", 1),
        "entries": dict(target_index.get("entries", {})),
    }
    for session_id, entry in source_index.get("entries", {}).items():
        entry = dict(entry)
        existing = merged["entries"].get(session_id)
        if existing is None:
            entry.setdefault("_recoveredFrom", source_label)
            merged["entries"][session_id] = entry
        else:
            existing_ts = existing.get("lastMessageDate", 0)
            new_ts = entry.get("lastMessageDate", 0)
            if new_ts > existing_ts:
                entry.setdefault("_recoveredFrom", source_label)
                merged["entries"][session_id] = entry
    return merged


def write_chat_index(db_path: Path, merged_index: dict):
    tmp_path = db_path.with_suffix(db_path.suffix + ".tmp")
    if db_path.exists():
        shutil.copy2(db_path, tmp_path)
    else:
        conn = sqlite3.connect(str(tmp_path))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)"
        )
        conn.commit()
        conn.close()

    conn = sqlite3.connect(str(tmp_path))
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
            (CHAT_INDEX_KEY, json.dumps(merged_index)),
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        conn.close()
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Could not write to {db_path}: {e}\n"
            "Is VS Code currently open with this workspace? Close it and retry."
        ) from e
    finally:
        conn.close()

    tmp_path.replace(db_path)


# ---------- folder content merge ----------

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:8]


def merge_folder(
    source_dir: Path, target_dir: Path, allowed_session_ids: set[str] | None = None
) -> int:
    """
    Copy every file from source_dir into target_dir. If a same-named file
    already exists and differs in content, rename the incoming file with
    a short content-hash suffix instead of overwriting. Returns count of
    files copied (new or renamed).

    If allowed_session_ids is given, only files whose stem (filename
    without extension) is in that set are copied — this keeps chatSessions/
    and chatEditingSessions/ file copies in sync with a date-filtered index,
    so you never end up with a file on disk whose session wasn't included.
    """
    if not source_dir.exists():
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    copied = 0

    for src_file in source_dir.rglob("*"):
        if src_file.is_dir():
            continue
        if allowed_session_ids is not None and src_file.stem not in allowed_session_ids:
            continue
        rel = src_file.relative_to(source_dir)
        dest = target_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists():
            if file_hash(dest) == file_hash(src_file):
                continue  # identical, skip
            # differing content under same name: disambiguate
            suffix = file_hash(src_file)
            dest = dest.with_name(f"{dest.stem}.{suffix}{dest.suffix}")
            if dest.exists():
                continue

        shutil.copy2(src_file, dest)
        copied += 1

    return copied


# ---------- orchestration ----------

def revive(
    target_dir: str,
    source_dirs: list[str],
    date_from_ms: int | None = None,
    date_to_ms: int | None = None,
):
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_db = target_dir / "state.vscdb"

    target_index = read_chat_index(target_db)
    print(f"Target starts with {len(target_index.get('entries', {}))} indexed session(s).")

    if date_from_ms is not None or date_to_ms is not None:
        print(
            f"Date filter active: "
            f"{datetime.fromtimestamp(date_from_ms/1000).date() if date_from_ms else 'any'} "
            f"to "
            f"{datetime.fromtimestamp(date_to_ms/1000).date() if date_to_ms else 'any'} "
            f"(local time)"
        )

    for src in source_dirs:
        src_dir = Path(src)

        if not src_dir.exists():
            print(f"\nERROR: source path does not exist: {src_dir}")
            print("  Check for unquoted spaces in the path, or a typo.")
            continue
        if not src_dir.is_dir():
            print(f"\nERROR: source path is not a directory: {src_dir}")
            continue

        src_db = src_dir / "state.vscdb"
        if not src_db.exists():
            print(f"\nWARNING: no state.vscdb found directly inside {src_dir}")
            print("  This folder may not be the workspaceStorage/<hash>/ folder itself.")
            print(f"  Contents found: {[p.name for p in src_dir.iterdir()]}")

        src_index = read_chat_index(src_db)
        raw_entries = src_index.get("entries", {})
        filtered_entries = filter_entries_by_date(raw_entries, date_from_ms, date_to_ms)
        n_total = len(raw_entries)
        n_kept = len(filtered_entries)

        print(f"\nSource: {src_dir}")
        if date_from_ms is not None or date_to_ms is not None:
            print(f"  Index: {n_kept}/{n_total} session(s) within date range")
        else:
            print(f"  Index: merging {n_kept} session(s)")

        if n_kept == 0:
            print("  (nothing in range, skipping folder copies for this source)")
            continue

        filtered_src_index = {"version": src_index.get("version", 1), "entries": filtered_entries}
        target_index = merge_indexes(target_index, filtered_src_index, source_label=str(src_dir))
        allowed_ids = set(filtered_entries.keys())

        for folder_name in FOLDERS_TO_MERGE:
            folder_path = src_dir / folder_name
            if not folder_path.exists():
                print(f"  {folder_name}/: NOT FOUND at {folder_path}")
                continue

            if folder_name == "GitHub.copilot-chat" and (
                date_from_ms is not None or date_to_ms is not None
            ):
                # Not session-scoped, so it can't be attributed to a date range.
                # Skip it when a date filter is active to avoid pulling in
                # unrelated extension state.
                print(f"  {folder_name}/: skipped (not session-scoped, date filter active)")
                continue

            id_filter = allowed_ids if folder_name in ("chatSessions", "chatEditingSessions") else None
            copied = merge_folder(folder_path, target_dir / folder_name, allowed_session_ids=id_filter)
            print(f"  {folder_name}/: copied {copied} file(s)")

    write_chat_index(target_db, target_index)
    print(f"\nDone. Target now has {len(target_index['entries'])} indexed session(s) total.")
    print(f"Target workspace folder: {target_dir}")
