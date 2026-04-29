import pytest

from arc.upstream import find, load


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
def test_resolution(task_id, expected_dataset, expected_split):
    src = find(task_id)
    assert src is not None
    assert src.dataset == expected_dataset
    assert src.split == expected_split


def test_load_returns_task_with_examples():
    task, src = load("0d87d2a6")
    assert src.dataset == "arc-agi-1"
    assert len(task.train) > 0
    assert len(task.test) > 0
    # examples have non-empty grids
    for ex in task.train + task.test:
        assert len(ex.input) > 0
        assert len(ex.output) > 0
        assert all(len(row) > 0 for row in ex.input)
        assert all(len(row) > 0 for row in ex.output)


def test_missing_task_raises():
    with pytest.raises(FileNotFoundError):
        load("ffffffff")
