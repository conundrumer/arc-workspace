"""Which gate commands a change affects. A command skipped wrongly passes
the merge in silence."""

import pytest

from engine import checkout
from tests.conftest import script

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


@pytest.fixture(scope="module")
def gate():
    return script("gate")


@pytest.mark.parametrize(("hunks", "runs"), [
    (((9, 1),), True),
    (((14, 1),), False),
    (((13, 0),), False),
    (((14, 0),), True),
    (((13, 1),), True),
    (((3, 1),), True),
    (((11, 0),), True),
    ((), True),
])
def test_a_hunk_runs_where_its_innermost_function_body_ran(gate, hunks, runs):
    assert gate.runs_hunks(SOURCE, hunks, RAN) is runs


def test_a_file_none_of_which_ran_runs_no_hunk(gate):
    assert gate.runs_hunks(SOURCE, ((3, 1),), frozenset()) is False


def test_a_change_affects_a_command_through_what_it_read_listed_or_ran(gate):
    cmd = gate.COMMANDS["lint"]
    deps = gate.Deps({"src/m.py": RAN}, frozenset({"programs/lib.dl"}),
                     frozenset({"programs/solvers"}))
    recorded = {"src/m.py": SOURCE}

    def affects(*touched):
        return gate.affects(cmd, "ac0c5833", deps, touched, recorded)

    S = checkout.Change
    T = gate.Touched
    assert affects(T("programs/lib.dl", S.MODIFIED))
    assert not affects(T("programs/other.dl", S.MODIFIED))
    assert affects(T("programs/solvers/new.dl", S.ADDED))
    assert not affects(T("programs/solvers/ac0c5833.dl", S.MODIFIED))
    assert not affects(T("src/m.py", S.MODIFIED, ((14, 1),)))
    assert affects(T("src/m.py", S.MODIFIED, ((9, 1),)))
    assert affects(T("src/m.py", S.DELETED))
    assert not affects(T("src/new.py", S.ADDED))
    assert affects(T("tests/gate/accepted/lint-ac0c5833.txt", S.MODIFIED))
    assert affects(T("uv.lock", S.MODIFIED))


def test_the_old_side_of_each_hunk_is_read_from_a_git_diff(gate):
    diff = ("diff --git a/m.py b/m.py\n--- a/m.py\n+++ b/m.py\n"
            "@@ -9 +9 @@ def ran(a):\n-    b = a + 1\n+    b = a + 2\n"
            "@@ -13,0 +14,2 @@ def not_ran(a):\n+    x\n+    y\n"
            "@@ -20,3 +22 @@\n-a\n-b\n-c\n+d\n")
    assert gate.hunks_of(diff) == ((9, 1), (13, 0), (20, 3))
