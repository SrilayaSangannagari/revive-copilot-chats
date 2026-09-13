from revive_copilot_chats.merge import merge_folder


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


def test_merge_folder_renames_on_collision_with_different_content(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "a.json").write_text("source version")
    (dst / "a.json").write_text("target version")

    copied = merge_folder(src, dst)

    assert copied == 1
    assert (dst / "a.json").read_text() == "target version"  # original untouched
    renamed = [f for f in dst.iterdir() if f.name != "a.json"]
    assert len(renamed) == 1
    assert renamed[0].read_text() == "source version"


def test_merge_folder_missing_source_returns_zero(tmp_path):
    copied = merge_folder(tmp_path / "nope", tmp_path / "dst")
    assert copied == 0


def test_merge_folder_session_id_filter(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "sid-a.json").write_text("a")
    (src / "sid-b.json").write_text("b")

    copied = merge_folder(src, dst, allowed_session_ids={"sid-a"})

    assert copied == 1
    assert (dst / "sid-a.json").exists()
    assert not (dst / "sid-b.json").exists()
