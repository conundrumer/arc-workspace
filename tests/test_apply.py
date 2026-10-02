import pytest

from arc.apply import PatchApplyError, apply_patch
from arc.patch import parse
from arc.task import Example, Task


def _task() -> Task:
    return Task(
        train=[
            Example(input=[[0, 0], [0, 0]], output=[[1, 1], [1, 1]]),
            Example(input=[[2, 2], [2, 2]], output=[[3, 3], [3, 3]]),
            Example(input=[[4, 4], [4, 4]], output=[[5, 5], [5, 5]]),
        ],
        test=[
            Example(input=[[6, 6], [6, 6]], output=[[7, 7], [7, 7]]),
        ],
    )


def test_diff_assert_fails_on_drift():
    p = parse("@diff train 0 output\n1 1\n9 1\n")  # claims first cell of row 1 is 9
    with pytest.raises(PatchApplyError, match="expected 9, got 1"):
        apply_patch(_task(), p)


def test_replace_old_grid_drift_fails():
    text = """\
@replace train 0 output
9 9
9 9
---
0 0
0 0
"""
    with pytest.raises(PatchApplyError, match="old grid does not match"):
        apply_patch(_task(), parse(text))


def test_branch_double_assignment_errors():
    text = """\
@branch test 0 rule
7 7
7~5 7

@branch test 0 tiebreak
7 7
7 7~3
"""
    with pytest.raises(PatchApplyError, match="already has an alt"):
        apply_patch(_task(), parse(text))
