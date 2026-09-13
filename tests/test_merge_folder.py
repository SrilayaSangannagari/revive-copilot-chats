from pathlib import Path

from revive_copilot_chats.merge import merge_folder, session_id_in_path


def test_merge_folder_copies_new_files(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "a.json").write_text('{"hello": "world"}')

    copied = merge_folder(src, dst)

    assert copied == 1
    assert (dst / "a.json").read_text() == '{"hello": "world"}'


def test_merge_folder_skips_identical_file(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "a.json").write_text("same content")
    (dst / "a.json").write_text("same content")

    copied = merge_folder(src, dst)

    assert copied == 0  # identical, nothing to do


def test_merge_folder_replaces_on_collision_with_different_content(tmp_path):
    """The source workspace wins: the target's copy is overwritten in place,
    under the same name, so nothing ends up in a file VS Code won't read."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "a.json").write_text("source version")
    (dst / "a.json").write_text("target version")

    copied = merge_folder(src, dst)

    assert copied == 1
    assert (dst / "a.json").read_text() == "source version"
    assert [f.name for f in dst.iterdir()] == ["a.json"], "no extra renamed copy"


def test_merge_folder_missing_source_returns_zero(tmp_path):
    copied = merge_folder(tmp_path / "nope", tmp_path / "dst")
    assert copied == 0


def test_merge_folder_copies_nested_dirs(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    (src / "nested").mkdir(parents=True)
    (src / "top.json").write_text("top")
    (src / "nested" / "inner.json").write_text("inner")

    copied = merge_folder(src, dst)

    assert copied == 2
    assert (dst / "top.json").read_text() == "top"
    assert (dst / "nested" / "inner.json").read_text() == "inner"


# ---------- session-id matching across VS Code's two storage layouts ----------

def test_session_id_in_path_matches_filename_stem():
    # chatSessions/<id>.json and transcripts/<id>.jsonl
    assert session_id_in_path(Path("sid-a.json"), {"sid-a"})
    assert session_id_in_path(Path("transcripts/sid-a.jsonl"), {"sid-a"})


def test_session_id_in_path_matches_directory_component():
    # the nested layouts, whose stems are names like "state" or "models"
    assert session_id_in_path(Path("sid-a/state.json"), {"sid-a"})
    assert session_id_in_path(Path("debug-logs/sid-a/models.json"), {"sid-a"})
    assert session_id_in_path(
        Path("chat-session-resources/sid-a/call_xyz/content.txt"), {"sid-a"}
    )


def test_session_id_in_path_rejects_unrelated_files():
    assert not session_id_in_path(Path("workspace-chunks.db"), {"sid-a"})
    assert not session_id_in_path(Path("memory-tool/memories"), {"sid-a"})
    assert not session_id_in_path(Path("sid-b.json"), {"sid-a"})


def test_merge_folder_filter_keeps_nested_session_dirs(tmp_path):
    """Regression: filtering used to match only the filename stem, so nested
    layouts like chatEditingSessions/<id>/state.json copied zero files."""
    src = tmp_path / "src"
    (src / "sid-a" / "contents").mkdir(parents=True)
    (src / "sid-b").mkdir(parents=True)
    (src / "sid-a" / "state.json").write_text("keep")
    (src / "sid-a" / "contents" / "blob.txt").write_text("keep too")
    (src / "sid-b" / "state.json").write_text("drop")

    copied = merge_folder(src, tmp_path / "dst", allowed_session_ids={"sid-a"})

    assert copied == 2
    assert (tmp_path / "dst" / "sid-a" / "state.json").read_text() == "keep"
    assert (tmp_path / "dst" / "sid-a" / "contents" / "blob.txt").exists()
    assert not (tmp_path / "dst" / "sid-b").exists()


def test_merge_folder_filter_skips_non_session_files(tmp_path):
    src = tmp_path / "src"
    (src / "transcripts").mkdir(parents=True)
    (src / "memory-tool").mkdir(parents=True)
    (src / "transcripts" / "sid-a.jsonl").write_text("session data")
    (src / "workspace-chunks.db").write_text("codebase index")
    (src / "memory-tool" / "memories").write_text("cross-project memory")

    copied = merge_folder(src, tmp_path / "dst", allowed_session_ids={"sid-a"})

    assert copied == 1
    assert (tmp_path / "dst" / "transcripts" / "sid-a.jsonl").exists()
    assert not (tmp_path / "dst" / "workspace-chunks.db").exists()
    assert not (tmp_path / "dst" / "memory-tool" / "memories").exists()


def test_merge_folder_no_filter_copies_everything(tmp_path):
    src = tmp_path / "src"
    (src / "sid-a").mkdir(parents=True)
    (src / "sid-a" / "state.json").write_text("a")
    (src / "workspace-chunks.db").write_text("index")

    copied = merge_folder(src, tmp_path / "dst", allowed_session_ids=None)

    assert copied == 2
    assert (tmp_path / "dst" / "workspace-chunks.db").exists()
