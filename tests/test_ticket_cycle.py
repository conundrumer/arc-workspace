"""A log line that leaves a ticket on a cycle of links is refused, with the
cycle in order, so the changes on it do not stand with no start; a move
into `closed`, or into `draft`, still pulls a ticket off the cycle."""

from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

LOG = "\n\n## Log\n2026-10-17T00:00:00Z draft [ticket-analyst]: filed\n"


def ticket(tickets: Path, status: str, name: str, depends: str, *lines: str) -> None:
    (tickets / status).mkdir(parents=True, exist_ok=True)
    front = f"depends-on: {depends}\n" if depends else ""
    body = f"---\nkind: change\neditors: code-editor\n{front}---\n# t: w{LOG}"
    (tickets / status / name).write_text(body + "".join(f"{line}\n" for line in lines))


def cycle(tickets: Path) -> None:
    """1-1 depends on 1-2, which waits on 1-3, which depends on 1-1."""
    ticket(tickets, "draft", "1-1_change_a_coordinator.md", "1-2")
    ticket(tickets, "waiting", "1-2_change_b_coordinator.md", "",
           "2026-10-17T00:00:01Z waiting [ticket-analyst]: change 1-3: x")
    ticket(tickets, "open", "1-3_change_c_coordinator.md", "1-1")


def test_line_that_leaves_a_cycle_is_refused(tmp_path: Path) -> None:
    scripts_importable()
    log = script("ticket_log")
    cycle(tmp_path)
    path = tmp_path / "draft" / "1-1_change_a_coordinator.md"
    before = path.read_text()
    with pytest.raises(log.Refused, match="1-1 -> 1-2 -> 1-3 -> 1-1"):
        log.log_moves(tmp_path, log.ticket_number("1-1"), log.Status.OPEN, "ticket-reviewer",
                      log.Status.DRAFT, None, "reviewed")
    assert path.read_text() == before


@pytest.mark.parametrize("status, note", [("closed", "wontfix: cut"), ("draft", "revising")])
def test_closed_and_draft_moves_pass_on_a_cycle(tmp_path: Path, status: str, note: str) -> None:
    scripts_importable()
    log = script("ticket_log")
    cycle(tmp_path)
    moves = log.log_moves(tmp_path, log.ticket_number("1-3"), log.Status(status), "coordinator",
                          log.Status.OPEN, None, note)
    assert moves.moved[0] == tmp_path / status / "1-3_change_c_coordinator.md"


def test_closed_ticket_ends_the_walk(tmp_path: Path) -> None:
    scripts_importable()
    log = script("ticket_log")
    cycle(tmp_path)
    (tmp_path / "closed").mkdir()
    (tmp_path / "open" / "1-3_change_c_coordinator.md").rename(
        tmp_path / "closed" / "1-3_change_c_coordinator.md")
    moves = log.log_moves(tmp_path, log.ticket_number("1-1"), log.Status.OPEN, "ticket-reviewer",
                          log.Status.DRAFT, None, "reviewed")
    assert not moves.refused
