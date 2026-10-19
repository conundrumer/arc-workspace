"""An `Op expedite:` line, and an allow line of the operator's session,
each reach from a ticket that is not a `change` each `change` whose
Motivation gives its number, past the chain of links. An allow line holds
through the ticket's later moves, and the allow line of a second session
admits the ticket for that session's operators alone."""

from pathlib import Path

from tests.conftest import script
from tests.test_own_work import state, ticket

FIRST = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"


def allow(session: str) -> str:
    return f"2026-10-17T03:00:00Z new [allow {session}]: allow\n"


def served_tickets(tickets: Path, more: str = ""):
    return [
        ticket(tickets, "9-1_change_x-need_coordinator", "request", "x: a need", more=more),
        ticket(tickets, "9-2_change_x-fix_ticket-analyst", "change", "x: the fix",
               "## Motivation\n- Serves 9-1.\n\n"),
        ticket(tickets, "9-3_change_x-more_ticket-analyst", "change", "x: more",
               "## Motivation\n- Serves 9-1.\n\n"),
        ticket(tickets, "9-4_change_y-other_ticket-analyst", "change", "y: other",
               "## Motivation\n- Serves 9-9.\n\n"),
    ]


def test_an_expedite_line_on_a_request_reaches_each_change_that_serves_it(tmp_path: Path) -> None:
    from operations.state import Message
    from operations.taking import allowed, expedited
    s = state(tmp_path, served_tickets(tmp_path / "tickets"),
              messages=[Message("op", 1.0, None, "Op expedite: 9-1")])
    assert expedited(s) == {"9-1", "9-2", "9-3"}
    assert allowed(s) == set()


def test_an_allow_line_on_a_request_reaches_each_change_that_serves_it(tmp_path: Path) -> None:
    from operations.taking import allowed, expedited
    s = state(tmp_path, served_tickets(tmp_path / "tickets", allow(FIRST)), session=FIRST)
    assert allowed(s) == {"9-1", "9-2", "9-3"}
    assert expedited(s) == set()


def test_an_allow_line_holds_after_a_release_and_for_its_own_session(tmp_path: Path) -> None:
    from operations.taking import allowed
    released = tmp_path / "tickets" / "released" / "9-1_change_x-fix_ticket-analyst.md"
    released.parent.mkdir(parents=True)
    released.write_text("---\nkind: change\n---\n# x: the fix\n\n## Log\n"
                        "2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n"
                        "2026-10-17T02:20:00Z approved [ticket-reviewer]: passed\n"
                        + allow(FIRST).replace(" new ", " approved ")
                        + "2026-10-17T04:00:00Z assigned [operator a0000000000000001]: taking\n"
                        "2026-10-17T05:00:00Z released [operator]: released: holder "
                        "a0000000000000001 is not live\n")
    other = ticket(tmp_path / "tickets", "9-2_agent_a0000000000000002_code-reviewer", "bug",
                   "an agent's run: slow", more=allow(SECOND))
    given = [script("ticket_reads").read_ticket(released), other]
    assert allowed(state(tmp_path, given, session=FIRST)) == {"9-1"}
    assert allowed(state(tmp_path, given, session=SECOND)) == {"9-2"}
