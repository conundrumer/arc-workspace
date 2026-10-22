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
