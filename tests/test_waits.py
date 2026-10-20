"""A change that waits on its `depends-on` reaches the coordinator with its
paths of links where a ticket on them does not move for a cause no
operator's step removes, once per occasion, and not where the usage pace
or a line of the user holds it; the paths give each ticket two paths
share in full once, and the hold of a ticket so held."""

from dataclasses import replace
from pathlib import Path

from tests.conftest import script
from tests.test_own_work import state

FILED = "2026-10-17T02:14:06Z"
LATE = 1_900_000_000.0


def ticket(tickets: Path, number: str, status: str = "approved", depends: str = "",
           more: str = ""):
    from handbook.paths import scripts_importable
    scripts_importable()
    path = tickets / status / f"{number}_change_x-{number}_ticket-analyst.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    field = f"depends-on: {depends}\n" if depends else ""
    path.write_text(f"---\nkind: change\n{field}---\n# x: change {number}\n\n"
                    f"## Log\n{FILED} draft [ticket-analyst]: filed\n{more}")
    return script("ticket_reads").read_ticket(path)


def at(tmp_path: Path, given, now: float = LATE, messages=()):
    return replace(state(tmp_path, given, messages=messages), now=now)


def sent_twice(s) -> tuple[object, object]:
    from operations.alerts import stuck_waits
    from operations.steps import key
    first = stuck_waits(s)
    return first, None if first is None else stuck_waits(replace(s, aside=s.aside | {key(first)}))


def test_a_chain_whose_end_waits_on_the_user_reaches_the_coordinator_once(tmp_path: Path) -> None:
    from operations.constants import COORDINATOR
    from operations.steps import Send
    tickets = tmp_path / "tickets"
    s = at(tmp_path, [ticket(tickets, "9-1", depends="9-2"),
                      ticket(tickets, "9-2", depends="9-3"),
                      ticket(tickets, "9-3", "blocked",
                             more="2026-10-17T03:00:00Z blocked [operator]: user: decide\n")])
    first, again = sent_twice(s)
    assert isinstance(first, Send) and first.to == COORDINATOR and "9-3" in first.message
    assert again is None


def test_a_cycle_reaches_the_coordinator_once_whichever_change_waits(tmp_path: Path) -> None:
    from operations.steps import Send
    tickets = tmp_path / "tickets"
    s = at(tmp_path, [ticket(tickets, "9-1", depends="9-2"), ticket(tickets, "9-2", depends="9-1")])
    first, again = sent_twice(s)
    assert isinstance(first, Send)
    assert "- 9-1 (`tickets/approved/`): it stands on the cycle of links 9-1 → 9-2 → 9-1" in first.message
    assert again is None


def test_a_cycle_that_holds_a_wait_on_the_user_reaches_the_coordinator_once(
        tmp_path: Path) -> None:
    tickets = tmp_path / "tickets"
    s = at(tmp_path, [ticket(tickets, "9-1", depends="9-2"),
                      ticket(tickets, "9-2", "blocked", depends="9-1",
                             more="2026-10-17T03:00:00Z blocked [operator]: user: decide\n"),
                      ticket(tickets, "9-3", depends="9-1"), ticket(tickets, "9-4", depends="9-1")])
    first, again = sent_twice(s)
    assert first is not None and again is None


def test_a_ticket_two_paths_share_is_given_in_full_once(tmp_path: Path) -> None:
    from operations.steps import Send
    tickets = tmp_path / "tickets"
    s = at(tmp_path, [ticket(tickets, "9-1", depends="9-2, 9-3"),
                      ticket(tickets, "9-2", depends="9-4"), ticket(tickets, "9-3", depends="9-4"),
                      ticket(tickets, "9-4", "blocked",
                             more="2026-10-17T03:00:00Z blocked [operator]: user: decide\n")])
    first, _ = sent_twice(s)
    assert isinstance(first, Send)
    assert "\n".join([
        "- 9-1 (`tickets/approved/`)",
        "    - 9-2 (`tickets/approved/`)",
        "        - 9-4 (`tickets/blocked/`): it waits on the user, since 2026-10-17T03:00:00Z",
        "    - 9-3 (`tickets/approved/`)",
        "        - 9-4, given above"]) in first.message


def test_a_chain_held_by_the_pace_or_the_pause_reaches_no_one_and_moves_no_change(
        tmp_path: Path, monkeypatch) -> None:
    from operations import codex_mode
    monkeypatch.setattr(codex_mode, "enabled", lambda: False)
    from operations import change_take, waits
    from operations.state import Message
    from operations.ticket_stall import stall, stalled
    from tests.conftest import script
    tickets = tmp_path / "tickets"
    s = at(tmp_path, [ticket(tickets, "9-1", depends="9-2"), ticket(tickets, "9-2")],
           messages=[Message("op", 1.0, None, "Op scope: all.")])
    path = tickets / "released" / "9-3_ticket_x_coordinator.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"---\nkind: request\n---\n# x: y\n\n## Log\n{FILED} new [coordinator]: filed\n"
                    f"{FILED} released [coordinator]: merged at 98d23618\n")
    paused = at(tmp_path, [ticket(tickets, "9-4", depends="9-3"),
                           script("ticket_reads").read_ticket(path)],
                messages=[Message("op", 1.0, None, "Op pause.")])
    paused = replace(paused, computed=replace(paused.computed, to_settle=("9-3",)))
    for given, change, line in ((s, "9-1", "- 9-2 (`tickets/approved/`): the usage pace holds it"),
                                (paused, "9-4",
                                 "- 9-3 (`tickets/released/`): the `Op pause.` line holds it")):
        assert sent_twice(given) == (None, None)
        assert stall(given) is None
        assert any(n == change for n, _ in change_take.waiting(given))
        assert line in waits.rendered(given, waits.paths(given, change, stalled(given)))


def test_a_change_with_a_log_line_within_the_stall_time_gives_no_message(tmp_path: Path) -> None:
    from operations.alerts import stuck_waits
    from operations.state import Message
    tickets = tmp_path / "tickets"
    given = [ticket(tickets, "9-1", depends="9-2"), ticket(tickets, "9-2")]
    s = at(tmp_path, given, now=given[0].last_time + 60, messages=[Message("op", 1.0, None, "Op pause.")])
    assert stuck_waits(s) is None
