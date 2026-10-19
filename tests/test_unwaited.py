"""A change under `tickets/waiting/` whose wait line gives a change that
stands under `tickets/closed/` reaches the coordinator once it has waited
on nothing across reads spanning `AGAIN_SECONDS`, and one whose wait line
gives an open change does not; nor does a ticket that a running ticket
analyst, the usage pace or the `Op pause.` line holds."""

from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_ticket_stall import FILED, ME, state

WAIT = f"{FILED} waiting [operator]: change 9-2: x\n"


def test_a_waiting_change_on_a_closed_change_reaches_the_coordinator(tmp_path: Path) -> None:
    from operations import unwaited
    from operations.constants import AGAIN_SECONDS, COORDINATOR
    from operations.steps import Send
    for status, reaches in (("closed", True), ("approved", False)):
        here = tmp_path / status
        s = state(here, {"waiting/9-1_change_x_ticket-analyst.md": WAIT,
                         f"{status}/9-2_change_y_ticket-analyst.md": f"{FILED} {status} [operator]: x\n"})
        first = replace(s, unwaited_since=unwaited.times(s))
        assert unwaited.step(first) is None
        later = replace(s, now=s.now + AGAIN_SECONDS, unwaited_since=unwaited.times(first))
        sent = unwaited.step(later)
        if reaches:
            assert isinstance(sent, Send) and sent.to == COORDINATOR and "9-1" in sent.message
        else:
            assert sent is None


def reaches(s) -> bool:
    """Whether `unwaited.step` gives a step at a read `AGAIN_SECONDS` after
    the read of `s`."""
    from operations import unwaited
    from operations.constants import AGAIN_SECONDS
    first = replace(s, unwaited_since=unwaited.times(s))
    later = replace(s, now=s.now + AGAIN_SECONDS, unwaited_since=unwaited.times(first))
    return unwaited.step(later) is not None


@pytest.mark.parametrize("agent_id", ["a00000000000000a1", None])
def test_a_draft_a_running_ticket_analyst_may_have_filed_does_not_reach_the_coordinator(
        tmp_path: Path, agent_id: str | None) -> None:
    from operations.roles import Purpose, Role, analyst_subject
    from operations.state import Agent, Waits
    s = state(tmp_path, {"draft/9-1_change_x_ticket-analyst.md": ""})
    filed = s.tracker.tickets["9-1"].filed
    analyst = Agent(agent_id, ME, Role.TICKET_ANALYST,
                    analyst_subject(Purpose.TRIAGE, "9-5"), "", filed - 10, filed - 10,
                    Waits.AT_WORK, (), True)
    assert not reaches(replace(s, transcripts=replace(s.transcripts, agents=(analyst,))))


def test_a_ticket_the_pace_or_the_pause_holds_does_not_reach_the_coordinator(
        tmp_path: Path) -> None:
    from operations.pacing import Until
    from operations.state import Message
    from tests.conftest import script
    s = state(tmp_path / "pace", {"approved/9-1_change_x_ticket-analyst.md": ""})
    scope_all = (Message(ME, 1.0, None, "Op scope: all."),)
    assert not reaches(replace(s, computed=replace(s.computed, pace=Until(s.now + 1e9)),
                               transcripts=replace(s.transcripts, messages=scope_all)))
    path = tmp_path / "pause" / "tickets" / "released" / "9-2_ticket_x_coordinator.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"---\nkind: request\n---\n# x: y\n\n## Log\n{FILED} new [coordinator]: filed\n"
                    f"{FILED} released [coordinator]: merged at 98d23618\n")
    request = script("ticket_reads").held_ticket(path)
    s = state(tmp_path / "pause",
              {"closed/9-3_change_y_ticket-analyst.md": f"{FILED} closed [operator]: x\n"})
    paused = replace(s, tracker=replace(s.tracker, tickets={"9-2": request}),
                     computed=replace(s.computed, to_settle=("9-2",)),
                     transcripts=replace(s.transcripts,
                                         messages=(Message(ME, 1.0, None, "Op pause."),)))
    assert not reaches(paused)
    assert reaches(replace(paused, computed=s.computed))
