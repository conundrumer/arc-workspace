"""A ticket of another session that only a chain of links reaches from the
tickets of the reading session is in the operators' purview only where that
session is idle, so the operators release no change of a live session."""

from pathlib import Path

import pytest

from tests.test_own_work import state as read_state

ASSIGNED = "## Log\n2026-10-17T02:14:06Z assigned [operator a00000000000000a1]: taking\n"


def write(tickets: Path, status: str, name: str, front: str, log: str) -> object:
    from handbook.paths import scripts_importable
    scripts_importable()
    from tests.conftest import script
    path = tickets / status / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nkind: change\n{front}---\n# x: y\n\n{log}")
    return script("ticket_reads").read_ticket(path)


@pytest.mark.parametrize("idle", [False, True])
def test_a_ticket_of_another_live_session_that_a_link_reaches_is_left_alone(
        tmp_path: Path, idle: bool) -> None:
    from dataclasses import replace
    from operations.state import SessionsRead
    from operations.steps import Bash
    from operations.taking import purview, release
    tickets = tmp_path / "tickets"
    mine = write(tickets, "assigned", "9-1_change_x-a_ticket-analyst", "depends-on: 11-2\n",
                 ASSIGNED.replace("a00000000000000a1", "a00000000000000b2"))
    other = write(tickets, "assigned", "11-2_change_x-b_ticket-analyst", "", ASSIGNED)
    st = read_state(tmp_path, [mine, other])
    st = replace(st, sessions=SessionsRead(frozenset({11}) if idle else frozenset(),
                                           frozenset(), False, False, None))
    assert ("11-2" in purview(st)) is idle
    step = release(st)
    assert (isinstance(step, Bash) and "11-2" in step.command) is idle
