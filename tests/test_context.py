"""The solver docs and the lib as a session reads them."""

from handbook.context import write_agent


def test_the_agent_file_is_written_whole_and_left_alone_when_unchanged(tmp_path):
    lib = tmp_path / "lib.dl"
    lib.write_text(".decl out(p: Position)\n")
    path = write_agent(tmp_path / "agents" / "handbook.md", lib=lib)
    assert not list((tmp_path / "agents").glob("*.tmp"))
    stamp = path.stat().st_mtime_ns
    assert write_agent(path, lib=lib) == path
    assert path.stat().st_mtime_ns == stamp    # the same definition is left alone
    lib.write_text("/// The output.\n.decl out(p: Position, col: Color)\n")
    write_agent(path, lib=lib)
    assert "- **out** — The output." in path.read_text()
