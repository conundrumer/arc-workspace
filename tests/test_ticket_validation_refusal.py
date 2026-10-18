"""`log` must refuse the move of a `request` into `waiting` where its
`Validation` section gives an `Exercised:` pattern that matches its own
text: the sweep would refuse it only after the change merged, with the
check stalled."""

from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

LOG = "\n\n## Log\n2026-10-17T00:00:00Z open [ticket-analyst]: filed\n"

REQUEST = "1-1_change_r_coordinator.md"


@pytest.mark.parametrize("pattern, refused", [
    ("controlled_markdown xrefs", True),
    ('"command":"[^"]*-m controlled_markdown xrefs', False),
])
def test_log_refuses_self_matching_pattern(tmp_path: Path, pattern: str, refused: bool) -> None:
    scripts_importable()
    log = script("ticket_log")
    for status in ("open", "assigned"):
        (tmp_path / status).mkdir()
    (tmp_path / "assigned" / "1-2_change_a_coordinator.md").write_text(
        f"---\nkind: change\n---\n# t: w\n\n## Motivation\n- m.{LOG}")
    (tmp_path / "open" / REQUEST).write_text(
        f"---\nkind: request\n---\n# t: w\n\n## Motivation\n- m.\n\n"
        f"## Validation\n- Exercised: {pattern}{LOG}")
    args = (tmp_path, log.ticket_number("1-1"), log.Status.WAITING, "ticket-analyst",
            log.Status.OPEN, None, "change 1-2: x")
    if refused:
        with pytest.raises(log.Refused):
            log.log_moves(*args)
        assert (tmp_path / "open" / REQUEST).exists()
    else:
        log.log_moves(*args)
        assert (tmp_path / "waiting" / REQUEST).exists()
