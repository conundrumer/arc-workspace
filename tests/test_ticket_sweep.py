"""The runs and the lines the sweep checks a `validation` ticket against:
a line written before the ticket's last move into `deferred` that
exercised it would open or close it unchecked, and a run or a line after
it that the sweep missed would leave it unexercised, both with no
failure."""

import json
import sys
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
ticket_sweep = script("ticket_sweep")
state_reads = sys.modules["state_reads"]

TICKET = """---
kind: validation
validates: 1-1
---
# request 1-1: a check

## Validation
- Exercised: {pattern}

## Log
2026-10-18T11:00:00Z deferred [operator]: filed: validates request 1-1
"""


def entry(text: str, t: str | None) -> str:
    e: dict = {"type": "user", "message": {"content": text}}
    if t is not None:
        e["timestamp"] = t
    return json.dumps(e)


@pytest.mark.parametrize(("pattern", "exercised"), [
    ("befor[e]-move", False),
    ("afte[r]-move", True),
    ("untime[d]-after", False),
])
def test_lines_from_the_move(tmp_path: Path, pattern: str, exercised: bool) -> None:
    run = tmp_path / "s.jsonl"
    run.write_text("\n".join([
        entry("before-move", "2026-10-18T10:00:00Z"),
        entry("after-move", "2026-10-18T12:00:00Z"),
        entry("untimed-after", None),
    ]) + "\n")
    ticket = tmp_path / "1-1_request_1-1_operator.md"
    text = TICKET.format(pattern=pattern)
    ticket.write_text(text)
    state_reads.new_state()
    since = ticket_sweep.deferred_since(ticket, text)
    for read_from in (0.0, since):
        given = {"s": ticket_sweep.given_run(str(run), read_from)}
        move = ticket_sweep.judged(ticket, text, given, since + 60, float("inf"))
        assert (move is not None) is exercised


def test_runs_under_no_operator(tmp_path: Path) -> None:
    from dataclasses import replace

    from operations.after_profile import unbatched_runs
    from tests.test_ticket_stall import TAKEN, state
    s = replace(state(tmp_path, {"assigned/9-1_change_x_ticket-analyst.md": TAKEN}),
                operators=("op1", "op2", "op3"), session="sess",
                parents={"op1": "main", "op2": "launcher", "op3": "launcher"})
    assert unbatched_runs(s) == ["op1", "op2", "op3", "launcher", "sess"]


def test_untimed_run_gives_no_lines(tmp_path: Path) -> None:
    run = tmp_path / "s.jsonl"
    run.write_text(entry("untimed", None) + "\n")
    state_reads.new_state()
    assert ticket_sweep.given_run(str(run), 0.0).lines == []
