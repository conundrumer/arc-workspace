"""The solver docs and the lib as a session reads them."""


from handbook.agents import write_agent


def test_the_agent_file_is_written_whole_and_left_alone_when_unchanged(tmp_path):
    lib = tmp_path / "lib.dl"
    lib.write_text(".decl out(p: Position)\n")
    wrappers = tmp_path / "components.py"
    out = tmp_path / "agents"
    path = write_agent(out, lib=lib, wrappers=wrappers)
    assert not list((tmp_path / "agents").glob("*.tmp"))
    stamp = path.stat().st_mtime_ns
    assert write_agent(out, lib=lib, wrappers=wrappers) == path
    assert path.stat().st_mtime_ns == stamp    # the same definition is left alone
    lib.write_text("/// The output.\n.decl out(p: Position, col: Color)\n")
    write_agent(out, lib=lib, wrappers=wrappers)
    assert "- **out** — The output." in path.read_text()
