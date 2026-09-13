import sqlite3

from revive_copilot_chats.cli import build_parser, main
from revive_copilot_chats.dates import filter_entries_by_date, count_missing_timestamps
from revive_copilot_chats.discovery import discover_all_sources


# ---------- the critical positional-parsing bug, now fixed ----------

def test_name_with_explicit_source_is_not_swallowed():
    """Regression test: --name combined with an explicit source path must
    treat that path as a source, not silently discard it into an unused
    'target' slot (the bug this test guards against produced 0 merged
    sessions with no error)."""
    parser = build_parser()
    args = parser.parse_args(["--name", "revived chats", "/path/to/source/hash"])
    assert args.paths == ["/path/to/source/hash"]


def test_target_and_sources_split_correctly_without_name():
    parser = build_parser()
    args = parser.parse_args(["/path/to/target", "/path/to/source1", "/path/to/source2"])
    assert args.paths == ["/path/to/target", "/path/to/source1", "/path/to/source2"]


# ---------- date validation ----------

def test_invalid_date_format_gives_clean_error(capsys):
    exit_code = main(["/tmp/target", "/tmp/source", "--from", "not-a-date"])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "not a valid date" in captured.err or "not a valid date" in captured.out


def test_from_after_to_gives_clean_error(capsys):
    exit_code = main([
        "/tmp/target", "/tmp/source",
        "--from", "2026-06-01", "--to", "2026-01-01",
    ])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "after --to" in captured.err or "after --to" in captured.out


def test_count_missing_timestamps():
    entries = {
        "a": {"lastMessageDate": 100},
        "b": {},  # no timestamp at all
        "c": {"lastMessageDate": 200},
    }
    assert count_missing_timestamps(entries) == 1


# ---------- missing/invalid paths give clean errors, not tracebacks ----------

def test_no_target_no_name_gives_clean_error(capsys):
    exit_code = main([])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "Provide" in captured.err or "Provide" in captured.out


def test_scan_all_with_missing_storage_base_gives_clean_error(tmp_path, capsys):
    missing = tmp_path / "does-not-exist"
    exit_code = main([
        str(tmp_path / "target"), "--scan-all", "--storage-base", str(missing),
    ])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "does not exist" in captured.err or "does not exist" in captured.out


def test_discover_all_sources_missing_base_raises_clear_error(tmp_path):
    missing = tmp_path / "nope"
    try:
        discover_all_sources(missing, exclude_hashes=set())
        assert False, "should have raised"
    except RuntimeError as e:
        assert "does not exist" in str(e)


# ---------- source-equals-target is skipped, not merged into itself ----------

def test_source_same_as_target_is_skipped(tmp_path, capsys):
    target = tmp_path / "ws"
    target.mkdir()
    conn = sqlite3.connect(target / "state.vscdb")
    conn.execute("CREATE TABLE ItemTable (key TEXT, value BLOB)")
    conn.commit()
    conn.close()

    exit_code = main([str(target), str(target), "--no-backup"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "skipping source" in captured.out.lower()
    assert "Nothing to do" in captured.out


# ---------- corrupted state.vscdb gives a clean error, not a traceback ----------

def test_corrupted_target_db_gives_clean_error(tmp_path, capsys):
    target = tmp_path / "target"
    target.mkdir()
    (target / "state.vscdb").write_bytes(b"not a real sqlite file at all")

    source = tmp_path / "source"
    source.mkdir()
    conn = sqlite3.connect(source / "state.vscdb")
    conn.execute("CREATE TABLE ItemTable (key TEXT, value BLOB)")
    conn.commit()
    conn.close()

    exit_code = main([str(target), str(source), "--no-backup"])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "corrupted" in captured.out.lower() or "corrupted" in captured.err.lower()
