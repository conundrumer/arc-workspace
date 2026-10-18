"""A request that waits on a change closed `fixed` must keep waiting where
another open change serves it: a request that closed in its place would
drop the need its open changes serve, with no sign."""

from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

LOG = "\n\n## Log\n2026-10-17T00:00:00Z open [ticket-analyst]: filed\n"


def ticket(tickets: Path, status: str, name: str, kind: str, motivation: str, *lines: str) -> None:
    (tickets / status).mkdir(parents=True, exist_ok=True)
    body = f"---\nkind: {kind}\n---\n# t: w\n\n## Motivation\n{motivation}{LOG}"
    (tickets / status / name).write_text(body + "".join(f"{line}\n" for line in lines))


@pytest.mark.parametrize("served", [True, False])
def test_fixed_change_leaves_served_request_waiting(tmp_path: Path, served: bool) -> None:
    scripts_importable()
    log = script("ticket_log")
    ticket(tmp_path, "assigned", "1-2_change_a_coordinator.md", "change", "- Serves request 1-1.")
    ticket(tmp_path, "waiting", "1-1_change_r_coordinator.md", "request", "- m.",
           "2026-10-17T00:00:01Z waiting [ticket-analyst]: change 1-2: x")
    if served:
        ticket(tmp_path, "open", "1-4_change_c_coordinator.md", "change", "- Serves request 1-1.")
        ticket(tmp_path, "open", "1-3_change_b_coordinator.md", "change", "- Serves request 1-1.")
    moves = log.log_moves(tmp_path, log.ticket_number("1-2"), log.Status.CLOSED, "operator",
                          log.Status.ASSIGNED, None, "fixed: done")
    assert not moves.refused
    if served:
        request = tmp_path / "waiting" / "1-1_change_r_coordinator.md"
        assert log.waits_on(request.read_text()) == log.ticket_number("1-3")
    else:
        assert (tmp_path / "closed" / "1-1_change_r_coordinator.md").exists()
