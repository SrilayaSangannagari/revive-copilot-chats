import json
import sqlite3

from revive_copilot_chats.merge import read_chat_index, merge_indexes, write_chat_index


def make_state_db(path, entries):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
    conn.execute(
        "INSERT INTO ItemTable VALUES (?, ?)",
        ("chat.ChatSessionStore.index", json.dumps({"version": 1, "entries": entries})),
    )
    conn.commit()
    conn.close()


def test_read_chat_index_missing_file_returns_empty(tmp_path):
    result = read_chat_index(tmp_path / "does-not-exist.vscdb")
    assert result == {"version": 1, "entries": {}}


def test_merge_indexes_dedup_keep_newest():
    target = {"version": 1, "entries": {
        "s1": {"sessionId": "s1", "lastMessageDate": 100, "title": "old"}
    }}
    source = {"version": 1, "entries": {
        "s1": {"sessionId": "s1", "lastMessageDate": 200, "title": "new"},
        "s2": {"sessionId": "s2", "lastMessageDate": 50, "title": "unique"},
    }}
    merged = merge_indexes(target, source, source_label="src")

    assert merged["entries"]["s1"]["title"] == "new"  # newer wins
    assert merged["entries"]["s1"]["_recoveredFrom"] == "src"
    assert merged["entries"]["s2"]["title"] == "unique"


def test_merge_indexes_keeps_existing_when_source_is_older():
    target = {"version": 1, "entries": {
        "s1": {"sessionId": "s1", "lastMessageDate": 999, "title": "keep-me"}
    }}
    source = {"version": 1, "entries": {
        "s1": {"sessionId": "s1", "lastMessageDate": 1, "title": "stale"}
    }}
    merged = merge_indexes(target, source, source_label="src")
    assert merged["entries"]["s1"]["title"] == "keep-me"


def test_write_chat_index_roundtrip(tmp_path):
    db_path = tmp_path / "state.vscdb"
    make_state_db(db_path, {})

    new_index = {"version": 1, "entries": {"s1": {"sessionId": "s1", "title": "hi"}}}
    write_chat_index(db_path, new_index)

    result = read_chat_index(db_path)
    assert result == new_index


def test_write_chat_index_creates_db_if_missing(tmp_path):
    db_path = tmp_path / "brand-new.vscdb"
    new_index = {"version": 1, "entries": {"s1": {"sessionId": "s1"}}}
    write_chat_index(db_path, new_index)

    assert db_path.exists()
    assert read_chat_index(db_path) == new_index
