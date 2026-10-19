"""A pending agent of another operator whose work ended ends with the text
of its report file, written after its launch, whichever agent its final
reply went to, whose fault would lose that report with no sign."""

from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
agent_ends = script("agent_ends")


def test_an_agent_that_ended_elsewhere_ends_with_its_report_file(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from operations.roles import Role
    from operations.state import Agent, Report, Waits
    report = tmp_path / "e89a91729211-reply.txt"
    report.write_text("- decision: decline: x\n")
    a = Agent("a0000000000000a12", "a00000000000000f2", Role.CODE_EDITOR, "9-1", "", 10.0, 10.0,
              Waits.AT_WORK, (), False, report_file=report)
    monkeypatch.setattr(agent_ends, "launched_find", lambda agent: tmp_path / "t.jsonl")
    monkeypatch.setattr(agent_ends, "work_open", lambda path, open_: False)
    monkeypatch.setattr(agent_ends, "reply_since", lambda agent, since: Report(20.0, "Done."))
    ended = agent_ends.ended_elsewhere([a], "a00000000000000f1", [])
    reply = ended[a.agent_id]
    assert reply is not None and reply.text == "- decision: decline: x"
