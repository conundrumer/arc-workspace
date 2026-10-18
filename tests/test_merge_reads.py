"""The read of a merge call's output: a run that the script's lines show
started and no footer of the script shows ended was stopped, and has no
outcome, and a run that ended is refused only where its output holds a
refusal line, so no refusal goes to an agent of the change for any other
form of output."""

import pytest

from engine.duration import FOOTER, STEP
from handbook.paths import scripts_importable
from operations.merging import PREFIX, REFUSED, TOOL
from operations.state import Merge

from tests.conftest import script

scripts_importable()

COMMAND = "uv run python scripts/merge_change.py /w -m 'c: x'"
STEPS = STEP.format(tool=TOOL, step="uv run pyright on 167 files", secs=77) + "\n"
REFUSAL = REFUSED + "pyright failed\n"
END = FOOTER.format(tool=TOOL, secs=80) + "\n"
FAILURE = PREFIX + "failed: fast-forwarding master failed\nfatal: index.lock exists\n"
TRACEBACK = "Traceback (most recent call last):\nKeyError: 'x'\n"


@pytest.mark.parametrize(("result", "error", "outcome"), [
    (STEPS, True, None),
    (STEPS + FOOTER.format(tool="gate", secs=207) + "\n", True, None),
    (STEPS + REFUSAL + END, True, Merge.REFUSED),
    (STEPS + FAILURE + END, True, Merge.FAILED),
    (STEPS + TRACEBACK + END, True, Merge.FAILED),
    ("Error: the command was refused\n", True, Merge.NOT_RUN),
])
def test_merge_outcome(result: str, error: bool, outcome: Merge | None) -> None:
    merge_outcome = script("merge_reads").merge_outcome
    assert merge_outcome("a1", COMMAND, 100.0, result, error, {}, set(), []) is outcome
