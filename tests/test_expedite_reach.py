"""An `Op expedite:` line reaches the tickets an `Op allow:` line with the
same numbers reaches: from a ticket that is not a `change`, each `change`
whose Motivation gives its number, past the chain of links."""

from pathlib import Path

import pytest

from tests.test_own_work import state, ticket


@pytest.mark.parametrize("directive", ["Op expedite", "Op allow"])
def test_a_line_on_a_request_reaches_each_change_that_serves_it(
        tmp_path: Path, directive: str) -> None:
    from operations.state import Message
    from operations.taking import allowed, expedited
    tickets = tmp_path / "tickets"
    given = [
        ticket(tickets, "9-1_change_x-need_coordinator", "request", "x: a need"),
        ticket(tickets, "9-2_change_x-fix_ticket-analyst", "change", "x: the fix",
               "## Motivation\n- Serves 9-1.\n\n"),
        ticket(tickets, "9-3_change_x-more_ticket-analyst", "change", "x: more",
               "## Motivation\n- Serves 9-1.\n\n"),
        ticket(tickets, "9-4_change_y-other_ticket-analyst", "change", "y: other",
               "## Motivation\n- Serves 9-9.\n\n"),
    ]
    s = state(tmp_path, given, messages=[Message("op", 1.0, None, f"{directive}: 9-1")])
    assert allowed(s) == {"9-1", "9-2", "9-3"}
    assert expedited(s) == ({"9-1", "9-2", "9-3"} if directive == "Op expedite" else set())
