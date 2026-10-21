"""Assigned holders without Claude transcripts do not block holder state reads."""

from dataclasses import replace
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from operations.final_reply import live_holder
from ticketing.vocabulary import Status
from tests.conftest import script
from tests.test_own_work import state, ticket

scripts_importable()
holders = script("holder_reads")
transcripts = script("transcripts")

MISSING = "01a15e9f-df0a-7dd2-bbfe-061a66a8b2aa"
AGENT = "a0000000000000001"


@pytest.mark.parametrize("sessions_running", [None, frozenset({"session", MISSING})])
def test_missing_holder_is_not_live_and_other_holders_are_still_read(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        sessions_running: frozenset[str] | None) -> None:
    main = tmp_path / "project/session.jsonl"
    agent = tmp_path / "project/session/subagents" / f"agent-{AGENT}.jsonl"
    other = tmp_path / "project/other.jsonl"
    for path in (main, agent, other):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    monkeypatch.setattr(transcripts, "project_dirs", lambda: [tmp_path])
    monkeypatch.setattr(holders, "work_open", lambda path, undecided: True)
    transcripts.new_state()
    base = ticket(tmp_path / "tickets", "9-1_agent_x_coordinator", "bug", "x: failure")
    tickets = {str(i): replace(base, number=str(i), status=Status.ASSIGNED, holder=h)
               for i, h in enumerate((MISSING, "session", AGENT, "other"))}

    read = holders.holders_read(tickets, "session", main, sessions_running)

    assert read.found == {"session": main, AGENT: agent, "other": other}
    expected_open = {"session", AGENT} | ({"other"} if sessions_running is None else set())
    assert read.open == expected_open
    assert read.session == {"session", AGENT}
    assembled = replace(state(tmp_path, tickets.values(), session="session"),
                        open_holders=read.open, session_holders=read.session)
    assert not live_holder(assembled, MISSING)
    assert live_holder(assembled, AGENT)
    assert holders.with_quiet_holders(assembled, read.found, [], {}) == assembled
