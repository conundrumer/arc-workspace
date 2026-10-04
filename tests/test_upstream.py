"""The resolution of a task to its upstream source. The tests read the
`data/upstream/` submodules, which the `upstream` fixture sets up."""

import pytest

from arc.upstream import find, load

pytestmark = pytest.mark.usefixtures("upstream")


@pytest.mark.parametrize(
    "task_id,expected_dataset,expected_split",
    [
        # v1-only patched task (per analysis)
        ("3ed85e70", "arc-agi-1", "evaluation"),
        # shared, v1 evaluation / v2 training — v1 should win
        ("0d87d2a6", "arc-agi-1", "evaluation"),
        # v2-only patched task
        ("17829a00", "arc-agi-2", "training"),
        # v2-only, v2 evaluation
        ("4a21e3da", "arc-agi-2", "evaluation"),
    ],
)
def test_resolution(task_id: str, expected_dataset: str, expected_split: str) -> None:
    src = find(task_id)
    assert src is not None
    assert src.dataset == expected_dataset
    assert src.split == expected_split


def test_missing_task_raises():
    with pytest.raises(FileNotFoundError):
        load("ffffffff")
