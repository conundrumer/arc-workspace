"""The read of a merge call's output: a run that the script's lines show
started and no footer of the script shows ended was stopped, and has no
outcome, so no refusal goes to an agent of the change."""

import pytest

from engine.duration import FOOTER, STEP
from handbook.paths import scripts_importable
from operations.merging import REFUSED, TOOL
from operations.state import Merge

from tests.conftest import script

scripts_importable()

COMMAND = "uv run python scripts/merge_change.py /w -m 'c: x'"
STEPS = STEP.format(tool=TOOL, step="uv run pyright on 167 files", secs=77) + "\n"
REFUSAL = REFUSED + "pyright failed\n"


@pytest.mark.parametrize(("result", "error", "outcome"), [
    (STEPS, True, None),
    (STEPS + FOOTER.format(tool="gate", secs=207) + "\n", True, None),
    (STEPS + REFUSAL + FOOTER.format(tool=TOOL, secs=80) + "\n", True, Merge.REFUSED),
    ("Error: the command was refused\n", True, Merge.NOT_RUN),
])
def test_merge_outcome(result: str, error: bool, outcome: Merge | None) -> None:
    merge_outcome = script("merge_reads").merge_outcome
    assert merge_outcome("a1", COMMAND, 100.0, result, error, {}, set(), []) is outcome
