"""A move into a take's queue goes into the one status its source gives,
so a released change stands apart from a fresh one and a reopened ticket
from a new one: a writer that names another queue status is refused and
writes nothing."""

from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

NAME = "1-1_change_a_coordinator.md"


def assigned(tickets: Path) -> Path:
    path = tickets / "assigned" / NAME
    path.parent.mkdir(parents=True)
    path.write_text("---\nkind: change\neditors: code-editor\n---\n# t: w\n\n## Log\n"
                    "2026-10-17T00:00:00Z draft [ticket-analyst]: filed\n"
                    "2026-10-17T00:01:00Z approved [ticket-reviewer]: passed\n"
                    "2026-10-17T00:02:00Z assigned [operator a0000000000000001]: taking\n")
    return path


@pytest.mark.parametrize("status", ["new", "approved", "reopened"])
def test_a_move_into_another_queue_status_is_refused(tmp_path: Path, status: str) -> None:
    scripts_importable()
    log = script("ticket_log")
    path = assigned(tmp_path)
    before = path.read_text()
    with pytest.raises(log.Refused, match="released"):
        log.log_moves(tmp_path, log.ticket_number("1-1"), log.Status(status), "operator",
                      log.Status.ASSIGNED, None, "released")
    assert path.read_text() == before


def test_the_move_queued_gives_is_written(tmp_path: Path) -> None:
    scripts_importable()
    log = script("ticket_log")
    assigned(tmp_path)
    moves = log.log_moves(tmp_path, log.ticket_number("1-1"), log.Status.RELEASED, "operator",
                          log.Status.ASSIGNED, None, "released")
    assert moves.moved == [tmp_path / "released" / NAME]
