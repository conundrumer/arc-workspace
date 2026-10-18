"""A ticket's stall time runs from the later of its last progress and the
read from which an operator's step has been due on it, and a missing or
unreadable record of those reads makes each due ticket due from the read
at hand."""

from dataclasses import replace
from pathlib import Path

import pytest

from engine import checkout
from tests.conftest import script

ME = "a00000000000000f1"
FILED = "2026-10-17T02:00:00Z"


TAKEN = f"{FILED} assigned [operator {ME}]: taking: budget 1 dollars, 100 s\n"


def state(tmp_path: Path, tickets: dict[str, str], budgets=()):
    """A state of the session whose tickets are the changes `tickets`
    gives, each by its path under `tickets/` and the log lines after its
    filing, long after their last progress, with a pace that admits a take
    and a budget for each change of `budgets`."""
    script("file_ticket")
    reads = script("ticket_reads")
    from operations.journal import Journal
    from operations.pacing import Until
    from operations.state import (Budget, Computed, GitRead, HeldRead, SessionsRead, State,
                                  TrackerRead, TranscriptsRead)
    held = {}
    for name, lines in tickets.items():
        path = tmp_path / "tickets" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\nkind: change\neditors: code-editor\n---\n# x: y\n\n## Log\n"
                        f"{FILED} draft [ticket-analyst]: filed\n" + lines)
        t = reads.held_ticket(path)
        held[t.number] = t
    first = next(iter(held.values()))
    return State(
        me=ME, now=first.filed + 100_000, session="s", started=0.0, transcripts_dir=tmp_path,
        main_tree=tmp_path, scratch=tmp_path, operators=(ME,), open_operators=frozenset(),
        past_bound=False, open_holders=frozenset(), session_holders=frozenset(),
        tracker=TrackerRead(held, (), first.session or 0),
        transcripts=TranscriptsRead((), (), (), {}, {}, {}, {}, {}, (), {}, {}),
        git=GitRead((), frozenset(), {}, {}, {}, frozenset(), {}, None, {}),
        taken_up=frozenset(), held=HeldRead({}, {}),
        sessions=SessionsRead(frozenset(), frozenset(), False, False, None),
        journal=Journal(()), listing=None,
        computed=Computed(budgets={n: Budget(1.0, 100.0, {}) for n in budgets}, pace=Until(0.0)))


def test_a_ticket_long_without_progress_is_not_stalled_at_the_read_that_first_finds_it_due(
        tmp_path: Path) -> None:
    from operations import ticket_stall
    from operations.constants import STUCK_SECONDS
    s = state(tmp_path, {"assigned/9-1_change_x_ticket-analyst.md": TAKEN})
    n = "9-1"
    assert n in ticket_stall.due(s)
    assert ticket_stall.stalled(s) == {}
    first = ticket_stall.due_times(s)
    assert first[n].since == s.now
    middle = ticket_stall.due_times(replace(s, now=s.now + STUCK_SECONDS / 2, due_since=first))
    later = replace(s, now=s.now + STUCK_SECONDS, due_since=middle)
    assert ticket_stall.stalled(later) == {n: s.now}


def test_an_unreadable_record_gives_no_due_times(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(checkout.scripts()))
    assembly = script("state_assembly")
    (tmp_path / assembly.DUE_SINCE).write_text('{"9-1": "x"')
    assert assembly.due_since_read(tmp_path) == {}
    (tmp_path / assembly.DUE_SINCE).write_text('{"9-1": "x"}')
    assert assembly.due_since_read(tmp_path) == {}
    (tmp_path / assembly.DUE_SINCE).write_text('{"9-1": 5.0}')
    assert assembly.due_since_read(tmp_path) == {}
    from operations.state import DueEntry
    assembly.write_due_since(tmp_path, {"9-1": DueEntry(5.0, 6.0)})
    assert assembly.due_since_read(tmp_path) == {"9-1": DueEntry(5.0, 6.0)}


def test_a_change_behind_the_head_of_the_take_is_not_stalled_at_the_read_where_it_reaches_it(
        tmp_path: Path) -> None:
    from operations import taking, ticket_stall
    from operations.constants import STUCK_SECONDS
    released = TAKEN + f"{FILED} open [operator {ME}]: released\n"
    tickets = {"open/9-1_change_x_ticket-analyst.md": released,
               "open/9-2_change_x_ticket-analyst.md": released}
    s = state(tmp_path, tickets)
    head, behind = (t.number for t in taking.batch(s))
    waits = state(tmp_path / "waits", tickets, [head])
    assert ticket_stall.due(waits) == {head}
    reached = replace(s, now=s.now + STUCK_SECONDS, due_since=ticket_stall.due_times(waits),
                      tracker=replace(s.tracker, tickets={behind: s.tracker.tickets[behind]}))
    assert ticket_stall.due(reached) == {behind}
    assert ticket_stall.stalled(reached) == {}


def test_a_ticket_whose_record_lapsed_is_not_stalled_at_the_read_where_it_is_due_again(
        tmp_path: Path) -> None:
    from operations import ticket_stall
    from operations.constants import STUCK_SECONDS
    s = state(tmp_path, {"assigned/9-1_change_x_ticket-analyst.md": TAKEN})
    n = "9-1"
    first = ticket_stall.due_times(s)
    outside = replace(s, now=s.now + STUCK_SECONDS, due_since=first,
                      tracker=replace(s.tracker, tickets={}))
    assert n not in ticket_stall.due_times(outside)
    for due_since in (first, ticket_stall.due_times(replace(s, now=s.now + 1, due_since=first,
                                                            tracker=replace(s.tracker, tickets={})))):
        back = replace(s, now=s.now + 2 * STUCK_SECONDS, due_since=due_since)
        assert ticket_stall.stalled(back) == {}
        assert ticket_stall.due_times(back)[n].since == back.now
        middle = ticket_stall.due_times(replace(back, now=back.now + STUCK_SECONDS / 2,
                                                due_since=ticket_stall.due_times(back)))
        later = replace(back, now=back.now + STUCK_SECONDS, due_since=middle)
        assert ticket_stall.stalled(later) == {n: back.now}


def test_a_ticket_due_at_every_read_keeps_its_time(tmp_path: Path) -> None:
    from operations import ticket_stall
    from operations.constants import STUCK_SECONDS
    s = state(tmp_path, {"assigned/9-1_change_x_ticket-analyst.md": TAKEN})
    record = ticket_stall.due_times(s)
    for k in range(1, 4):
        record = ticket_stall.due_times(replace(s, now=s.now + k * STUCK_SECONDS / 3,
                                                due_since=record))
    assert ticket_stall.stalled(replace(s, now=s.now + STUCK_SECONDS, due_since=record)) == {
        "9-1": s.now}
