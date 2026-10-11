"""Which gate commands a change affects. A command skipped wrongly passes
the merge in silence."""

import pytest

from engine import checkout
from gating import deps
from gating.commands import COMMANDS

SOURCE = '''import os

X = 1


@decorated
def ran(a):
    """Doc."""
    b = a + 1
    return b


def not_ran(a):
    return a
'''
"""Lines: `ran` has its header at 6 and 7, its body from 8 to 10;
`not_ran` its header at 13 and its body at 14."""

RAN = frozenset({1, 3, 6, 7, 9, 10, 13})


def H(start, count):
    return deps.Hunk(start, count, start, count)


@pytest.mark.parametrize(("hunks", "runs"), [
    ((H(9, 1),), True),
    ((H(14, 1),), False),
    ((H(13, 0),), False),
    ((H(14, 0),), True),
    ((H(13, 1),), True),
    ((H(3, 1),), True),
    ((H(11, 0),), True),
    ((), True),
])
def test_a_hunk_runs_where_its_innermost_function_body_ran(hunks, runs):
    assert deps.runs_hunks(SOURCE, hunks, RAN) is runs


def test_a_file_none_of_which_ran_runs_no_hunk():
    assert deps.runs_hunks(SOURCE, (H(3, 1),), frozenset()) is False


def test_a_change_affects_a_command_through_what_it_read_listed_or_ran():
    cmd = COMMANDS["lint"]
    ran = deps.Deps({"src/m.py": RAN}, frozenset({"programs/lib.dl"}),
                    frozenset({"programs/solvers"}))
    recorded = {"src/m.py": SOURCE}

    def affects(*touched):
        return deps.affects(cmd, "ac0c5833", ran, touched, recorded)

    S = checkout.Change
    T = deps.Touched
    assert affects(T("programs/lib.dl", S.MODIFIED))
    assert not affects(T("programs/other.dl", S.MODIFIED))
    assert affects(T("programs/solvers/new.dl", S.ADDED))
    assert not affects(T("programs/solvers/ac0c5833.dl", S.MODIFIED))
    assert not affects(T("src/m.py", S.MODIFIED, (H(14, 1),)))
    assert affects(T("src/m.py", S.MODIFIED, (H(9, 1),)))
    assert affects(T("src/m.py", S.DELETED))
    assert not affects(T("src/new.py", S.ADDED))
    assert affects(T("tests/gate/accepted/lint-ac0c5833.txt", S.MODIFIED))
    assert affects(T("uv.lock", S.MODIFIED))


def test_the_old_side_of_each_hunk_is_read_from_a_git_diff():
    diff = ("diff --git a/m.py b/m.py\n--- a/m.py\n+++ b/m.py\n"
            "@@ -9 +9 @@ def ran(a):\n-    b = a + 1\n+    b = a + 2\n"
            "@@ -13,0 +14,2 @@ def not_ran(a):\n+    x\n+    y\n"
            "@@ -20,3 +22 @@\n-a\n-b\n-c\n+d\n")
    assert deps.hunks_of(diff) == ((9, 1, 9, 1), (13, 0, 14, 2), (20, 3, 22, 1))


def test_a_line_outside_every_hunk_moves_by_the_lines_the_hunks_before_it_add():
    hunks = (deps.Hunk(9, 1, 9, 1), deps.Hunk(13, 0, 14, 2), deps.Hunk(20, 3, 22, 1))
    assert deps.moved(frozenset({8, 10, 13, 14, 19, 23}), hunks) == {8, 10, 13, 16, 21, 23}
