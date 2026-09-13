import json
import sqlite3
from datetime import datetime

from revive_copilot_chats.dates import parse_date_to_ms, filter_entries_by_date
from revive_copilot_chats.discovery import discover_all_sources, find_new_workspace_hash
from revive_copilot_chats.backup import backup_target_state_db


# ---------- dates ----------

def test_parse_date_to_ms_start_of_day():
    ms = parse_date_to_ms("2026-02-01")
    dt = datetime.fromtimestamp(ms / 1000)
    assert dt.hour == 0 and dt.minute == 0 and dt.second == 0


def test_parse_date_to_ms_end_of_day():
    ms = parse_date_to_ms("2026-02-28", end_of_day=True)
    dt = datetime.fromtimestamp(ms / 1000)
    assert dt.hour == 23 and dt.minute == 59 and dt.second == 59


def test_filter_entries_by_date_range():
    entries = {
        "a": {"lastMessageDate": parse_date_to_ms("2026-01-10")},
        "b": {"lastMessageDate": parse_date_to_ms("2026-02-15")},
        "c": {"lastMessageDate": parse_date_to_ms("2026-03-05")},
    }
    from_ms = parse_date_to_ms("2026-02-01")
    to_ms = parse_date_to_ms("2026-02-28", end_of_day=True)

    filtered = filter_entries_by_date(entries, from_ms, to_ms)

    assert list(filtered.keys()) == ["b"]


def test_filter_entries_by_date_no_filter_returns_all():
    entries = {"a": {"lastMessageDate": 1}, "b": {"lastMessageDate": 2}}
    assert filter_entries_by_date(entries, None, None) == entries


# ---------- discovery ----------

def make_workspace(base, name, has_db=True):
    d = base / name
    d.mkdir()
    if has_db:
        (d / "state.vscdb").write_text("fake")
    return d


def test_discover_all_sources_excludes_target_and_requires_db(tmp_path):
    make_workspace(tmp_path, "ws1")
    make_workspace(tmp_path, "ws2")
    make_workspace(tmp_path, "target")
    make_workspace(tmp_path, "no-db", has_db=False)

    sources = discover_all_sources(tmp_path, exclude_hashes={"target"})
    names = {s.name for s in sources}

    assert names == {"ws1", "ws2"}


def test_find_new_workspace_hash_matches_by_workspace_json(tmp_path):
    target_path = tmp_path / "my-project"
    target_path.mkdir()

    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "workspace.json").write_text(json.dumps({"folder": "file:///somewhere/else"}))

    match = tmp_path / "match"
    match.mkdir()
    (match / "workspace.json").write_text(
        json.dumps({"folder": f"file://{target_path}"})
    )

    found = find_new_workspace_hash(str(target_path), tmp_path)
    assert found == "match"


def test_find_new_workspace_hash_no_match_returns_none(tmp_path):
    target_path = tmp_path / "nonexistent-project"
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "workspace.json").write_text(json.dumps({"folder": "file:///somewhere/else"}))

    found = find_new_workspace_hash(str(target_path), tmp_path)
    assert found is None


# ---------- backup ----------

def test_backup_target_state_db_missing_returns_none(tmp_path):
    result = backup_target_state_db(tmp_path / "no-such-file.vscdb")
    assert result is None


def test_backup_target_state_db_copies_content(tmp_path):
    db_path = tmp_path / "state.vscdb"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE ItemTable (key TEXT, value BLOB)")
    conn.execute("INSERT INTO ItemTable VALUES ('k', 'original')")
    conn.commit()
    conn.close()

    backup_path = backup_target_state_db(db_path)

    assert backup_path is not None
    assert backup_path.name == "state.vscdb.backup"
    conn = sqlite3.connect(backup_path)
    row = conn.execute("SELECT value FROM ItemTable").fetchone()
    assert row[0] == "original"
