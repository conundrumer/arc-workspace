"""A change under `tickets/waiting/` whose wait line gives a change that
stands under `tickets/closed/` reaches the coordinator once it has waited
on nothing across reads spanning `AGAIN_SECONDS`, and one whose wait line
gives an open change does not."""

from dataclasses import replace
from pathlib import Path

from tests.test_ticket_stall import FILED, state

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
