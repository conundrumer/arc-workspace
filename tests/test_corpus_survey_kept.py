"""A slow section's kept intermediate is computed again once a file it is
keyed by changes, and read back while none does."""

from study.corpus_survey import kept


def test_a_changed_file_computes_the_intermediate_again(tmp_path, monkeypatch):
    monkeypatch.setattr(kept, "kept_dir", lambda section: tmp_path / section)
    source = tmp_path / "solver.dl"
    source.write_text("a")
    made: list[str] = []

    def make() -> str:
        made.append(source.read_text())
        return source.read_text()

    def run() -> str:
        return kept.kept("rows", {"files": kept.files_key([source])}, make)

    assert run() == "a"
    assert run() == "a"
    source.write_text("b")
    assert run() == "b"
    assert made == ["a", "b"]


def test_an_edit_under_src_or_engine_lib_changes_the_solver_key(tmp_path, monkeypatch):
    for top in ("src", "engine/lib"):
        (tmp_path / top).mkdir(parents=True)
        (tmp_path / top / "f").write_text("a")
    (tmp_path / "src" / "__pycache__").mkdir()
    monkeypatch.setattr(kept, "ROOT", tmp_path)
    monkeypatch.setattr(kept, "record_key", lambda stem: stem)

    def key() -> str:
        kept.tree_key.cache_clear()
        return kept.solver_key("s")["code"]

    before = key()
    (tmp_path / "src" / "__pycache__" / "x.pyc").write_text("c")
    assert key() == before
    (tmp_path / "src" / "f").write_text("b")
    after_src = key()
    assert after_src != before
    (tmp_path / "engine/lib" / "f").write_text("b")
    assert key() != after_src
