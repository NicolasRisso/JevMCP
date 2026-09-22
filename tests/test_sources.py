from jev_mcp.sources import chunk, expand_paths, iter_items


def test_chunk_short_text_is_single_piece():
    assert chunk("abc", 10) == ["abc"]


def test_chunk_prefers_newlines_and_preserves_text():
    text = "line one\nline two\nline three\n"
    parts = chunk(text, 12)
    assert "".join(parts) == text
    assert all(len(p) <= 12 for p in parts)
    assert parts[0] == "line one\n"


def test_expand_paths_glob_dir_and_skip_binary(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("print(1)")
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01")

    assert len(expand_paths([str(tmp_path)])) == 3
    assert len(expand_paths([str(tmp_path / "**" / "*.py")])) == 1

    ids = [i for i, _ in iter_items([str(tmp_path)], None, 1000)]
    assert len(ids) == 2  # binary skipped


def test_iter_items_labels_chunks():
    items = list(iter_items(None, {"note": "a\nb\nc\n"}, 2))
    assert [i for i, _ in items] == ["note#0", "note#1", "note#2"]


def test_ids_use_forward_slashes(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text("x")
    (path,) = expand_paths([str(tmp_path)])
    assert "\\" not in path and path.endswith("sub/a.txt")
