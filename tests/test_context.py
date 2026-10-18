"""The solver docs and the lib as a session reads them."""


from engine import checkout
from handbook.agents import write_agent
from tests.conftest import script


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


def test_a_filing_clause_of_a_kind_the_agent_does_not_file_is_a_finding(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(checkout.scripts()))
    findings = script("ticket_vocabulary").document_findings
    path = tmp_path / "item-checker.md"
    text = "\n".join([
        "- Where your instructions ask you to file a ticket, file it with `uv run python scripts/file_ticket.py`.",
        "- Read a ticket the coordinator filed from the user's words, a `request` in its spans.",
        "- File a `bug` ticket on each fault you notice.",
        "- File a `question` ticket on each case your rules do not cover.",
        "- Read the rule and file a `question` ticket on it.",
        "- Read the rule or file a `question` ticket on it.",
        "- When done file a `question` ticket.",
        "- Each agent that files a `question` ticket waits.",
    ])
    lines = [4, 5, 6, 7]
    assert [f.split(": ")[0].endswith(f"item-checker.md:{n}")
            for f, n in zip(findings("item-checker", path, text), lines, strict=True)] == [True] * len(lines)
    assert len(findings("no-such-agent", path, "- File a `bug` ticket on each fault.")) == 1
