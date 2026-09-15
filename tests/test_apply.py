import pytest

from arc.apply import PatchApplyError, apply_patch
from arc.patch import parse
from arc.task import Alt, Example, Task


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


def test_diff_changes_one_cell():
    p = parse("@diff train 0 output\n1 1\n1 1~9\n")
    out = apply_patch(_task(), p)
    assert out.train[0].output == [[1, 1], [1, 9]]
    # other examples untouched
    assert out.train[1].output == [[3, 3], [3, 3]]


def test_diff_assert_fails_on_drift():
    p = parse("@diff train 0 output\n1 1\n9 1\n")  # claims first cell of row 1 is 9
    with pytest.raises(PatchApplyError, match="expected 9, got 1"):
        apply_patch(_task(), p)


def test_replace_swaps_grid_with_assert():
    text = """\
@replace train 0 output
1 1
1 1
---
9 8 7
6 5 4
3 2 1
"""
    out = apply_patch(_task(), parse(text))
    assert out.train[0].output == [[9, 8, 7], [6, 5, 4], [3, 2, 1]]


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


def test_delete_removes_example():
    text = """\
@delete train 1
2 2
2 2
---
3 3
3 3
"""
    out = apply_patch(_task(), parse(text))
    assert len(out.train) == 2
    assert out.train[0].input == [[0, 0], [0, 0]]
    assert out.train[1].input == [[4, 4], [4, 4]]  # was train[2]


def test_deletes_use_pre_patch_indices_when_combined():
    # delete train 0 and train 2 together should work: indices both refer to original
    text = """\
@delete train 0
0 0
0 0
---
1 1
1 1

@delete train 2
4 4
4 4
---
5 5
5 5
"""
    out = apply_patch(_task(), parse(text))
    assert len(out.train) == 1
    assert out.train[0].input == [[2, 2], [2, 2]]


def test_diff_then_delete_uses_original_indices():
    # Diff train 0, then delete train 1. After delete, train[0] should still have the diff.
    text = """\
@diff train 0 output
1 1
1 1~9

@delete train 1
2 2
2 2
---
3 3
3 3
"""
    out = apply_patch(_task(), parse(text))
    assert len(out.train) == 2
    assert out.train[0].output == [[1, 1], [1, 9]]


def test_branch_rule_sets_alt():
    p = parse("@branch test 0 rule\n7 7\n7~5 7\n")
    out = apply_patch(_task(), p)
    assert out.test[0].alt == Alt(kind="rule", grid=[[7, 7], [5, 7]])
    # base output unchanged
    assert out.test[0].output == [[7, 7], [7, 7]]


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


def test_deepcopy_does_not_mutate_input():
    t = _task()
    snapshot_train_0_output = [row[:] for row in t.train[0].output]
    p = parse("@diff train 0 output\n1 1\n1 1~9\n")
    apply_patch(t, p)
    assert t.train[0].output == snapshot_train_0_output
