"""run_determine: the task id comes from the stem's last path segment."""

from dl import determine, solve


def test_stem_path_segment_names_the_task(tmp_path, monkeypatch):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "9385bd28_alt.dl").write_text("// solver\n")
    seen = []
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(determine, "load_task", lambda tid: seen.append(tid))
    monkeypatch.setattr(determine, "determine_check", lambda source, task: None)

    assert determine.run_determine("sub/9385bd28_alt") is None
    assert seen == ["9385bd28"]
