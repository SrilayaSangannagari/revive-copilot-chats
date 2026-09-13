"""Core merge logic: the state.vscdb chat index, session folder contents,
and the top-level orchestration that ties a whole revive run together."""

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from .constants import CHAT_INDEX_KEY, FOLDERS_TO_MERGE
from .dates import filter_entries_by_date, count_missing_timestamps


# ---------- state.vscdb index merge ----------

def read_chat_index(db_path: Path) -> dict:
    if not db_path.exists():
        return {"version": 1, "entries": {}}
    try:
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
    except sqlite3.DatabaseError as e:
        raise sqlite3.DatabaseError(f"{db_path} appears corrupted or is not a valid SQLite file: {e}") from e
    except json.JSONDecodeError as e:
        raise ValueError(
            f"{db_path}: chat index value is not valid JSON ({e}). "
            "The extension's storage format may have changed."
        ) from e


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
    """Full SHA-256 of the file's bytes, used only to skip rewriting a file
    that is already byte-identical."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def session_id_in_path(rel: Path, session_ids: set[str]) -> bool:
    """
    Whether a session-storage file belongs to one of session_ids.

    VS Code identifies a session's files two different ways, so we accept
    either. As the filename stem:

        chatSessions/<id>.json
        GitHub.copilot-chat/transcripts/<id>.jsonl

    ...or as a directory component, with arbitrary names beneath it:

        chatEditingSessions/<id>/state.json
        GitHub.copilot-chat/debug-logs/<id>/models.json
        GitHub.copilot-chat/chat-session-resources/<id>/call_.../content.txt

    Matching only the stem (the earlier behaviour) silently copied nothing
    from the nested layouts, since their stems are names like "state".
    """
    if rel.stem in session_ids:
        return True
    return any(part in session_ids for part in rel.parts)


def merge_folder(
    source_dir: Path, target_dir: Path, allowed_session_ids: set[str] | None = None
) -> int:
    """
    Copy every file from source_dir into target_dir, replacing any
    same-named file already there — the source is treated as the source of
    truth. Files that are already byte-identical are left alone. Returns
    count of files written.

    If allowed_session_ids is given, a file is copied only when one of those
    session ids appears in its relative path (see session_id_in_path). Files
    belonging to no session at all — codebase indexes like
    workspace-chunks.db, or memory-tool/ — are therefore skipped, since no
    date range can vouch for them. Pass None to copy everything.
    """
    if not source_dir.exists():
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    copied = 0

    for src_file in source_dir.rglob("*"):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(source_dir)
        if allowed_session_ids is not None and not session_id_in_path(
            rel, allowed_session_ids
        ):
            continue
        dest = target_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        # The source workspace is authoritative: an existing file in the
        # target is replaced under the same name. That way a chat continued in
        # its original workspace is picked up by the next recovery, instead of
        # staying frozen at whatever the first recovery copied.
        if dest.exists() and file_hash(dest) == file_hash(src_file):
            continue  # already identical, nothing to write

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

    date_filter_active = date_from_ms is not None or date_to_ms is not None

    if date_filter_active:
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
        if date_filter_active:
            print(f"  Index: {n_kept}/{n_total} session(s) within date range")
            missing = count_missing_timestamps(raw_entries)
            if missing:
                print(
                    f"  NOTE: {missing} session(s) have no timestamp at all and were "
                    "excluded by the date filter — re-run without --from/--to to include them."
                )
        else:
            print(f"  Index: merging {n_kept} session(s)")

        if n_kept == 0:
            print("  (nothing in range, skipping folder copies for this source)")
            continue

        filtered_src_index = {"version": src_index.get("version", 1), "entries": filtered_entries}
        target_index = merge_indexes(target_index, filtered_src_index, source_label=str(src_dir))

        # With no date range, copy each folder wholesale. With one, copy only
        # the files belonging to the sessions whose lastMessageDate landed in
        # range, so the files and the index always agree.
        allowed_ids = set(filtered_entries) if date_filter_active else None

        for folder_name in FOLDERS_TO_MERGE:
            folder_path = src_dir / folder_name
            if not folder_path.exists():
                print(f"  {folder_name}/: NOT FOUND at {folder_path}")
                continue
            copied = merge_folder(
                folder_path, target_dir / folder_name, allowed_session_ids=allowed_ids
            )
            print(f"  {folder_name}/: copied {copied} file(s)")

    write_chat_index(target_db, target_index)
    print(f"\nDone. Target now has {len(target_index['entries'])} indexed session(s) total.")
    print(f"Target workspace folder: {target_dir}")
