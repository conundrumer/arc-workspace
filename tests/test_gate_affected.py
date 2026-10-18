"""Which gate commands a change affects. A command skipped wrongly passes
the merge in silence."""

import pytest

from engine import checkout
from gating import deps, edits
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


INERT_OLD = '''"""Module."""
import os
from a import b, c

p = parser.add_argument("x", help="old")


def f(x):
    """Doc."""
    # note
    return x + 1
'''
"""Lines: the imports at 2 and 3, the `add_argument` call at 5, `f` from
8 to 11."""


@pytest.mark.parametrize(("hunk", "new", "passed"), [
    (deps.Hunk(9, 1, 9, 1), ['    """Other doc."""\n'], True),
    (deps.Hunk(10, 1, 10, 2), ["    # other\n", "\n"], True),
    (deps.Hunk(1, 1, 1, 0), [], True),
    (deps.Hunk(5, 1, 5, 1), ['p = parser.add_argument("x", help="new")\n'], True),
    (deps.Hunk(5, 1, 5, 1), ['p = parser.add_argument("y", help="old")\n'], False),
    (deps.Hunk(3, 1, 3, 1), ["from a import b\n"], True),
    (deps.Hunk(3, 1, 3, 1), ["from a import b, c, d\n"], True),
    (deps.Hunk(3, 1, 3, 1), ["from a import b\nfrom e import c\n"], False),
    (deps.Hunk(3, 1, 3, 1), ["from a import b, d as c\n"], False),
    (deps.Hunk(2, 1, 2, 0), [], False),
    (deps.Hunk(11, 1, 11, 1), ["    return x + 2\n"], False),
    (deps.Hunk(11, 1, 11, 1), ["    return (x\n"], False),
])
def test_a_hunk_is_inert_where_it_changes_only_docstrings_comments_help_or_imports(
        hunk, new, passed):
    assert edits.inert("src/m.py", INERT_OLD, new, hunk) is passed


SAME_OLD = '''from a import b
p = parser.add_argument("x", help="old")


def f(x):  # type: ignore[no-untyped-def]
    """Doc."""
    # note
    return x + 1
'''


@pytest.mark.parametrize(("old", "new", "same"), [
    ('"""Doc."""', '"""Other doc."""', True),
    ("# note", "# other note", True),
    ('help="old"', 'help="new"', True),
    ("# type: ignore[no-untyped-def]", "# type: ignore[misc]", False),
    ("from a import b", "from a import b, c", False),
    ('help="old"', 'help=f"{x}"', False),
    ("x + 1", "x + 2", False),
    ("x + 1", "(x", False),
    ("from a", '"""Module\ndoc."""\nfrom a', True),
    ("(x):  # type: ignore[no-untyped-def]\n    \"\"\"Doc.\"\"\"",
     "(x):\n    \"\"\"Doc.\"\"\"  # type: ignore[no-untyped-def]", False),
])
def test_same_code_holds_where_an_edit_changes_only_docstrings_plain_comments_or_help(
        old, new, same):
    assert edits.same_code("src/m.py", SAME_OLD, SAME_OLD.replace(old, new)) is same


def test_the_help_of_the_command_helper_is_inert_in_its_own_file_alone():
    old = 'command("x", f, help="old")\n'
    new = ['command("x", f, help="new")\n']
    assert edits.inert("src/cli/parser.py", old, new, H(1, 1))
    assert not edits.inert("src/m.py", old, new, H(1, 1))


def test_an_inert_hunk_affects_no_command_and_a_gate_file_runs_whole():
    cmd = COMMANDS["lint"]
    ran = deps.Deps({"src/m.py": RAN}, frozenset(), frozenset())

    def affects(*touched):
        return deps.affects(cmd, "ac0c5833", ran, touched, {"src/m.py": SOURCE})

    S = checkout.Change
    T = deps.Touched
    assert not affects(T("src/m.py", S.MODIFIED, (H(3, 1), H(9, 1)), passed=frozenset({0, 1})))
    assert not affects(T("src/m.py", S.MODIFIED, (H(3, 1), H(14, 1)), passed=frozenset({0})))
    assert affects(T("src/m.py", S.MODIFIED, (H(3, 1),), passed=frozenset()))
    assert not affects(T("src/gating/run.py", S.MODIFIED, (H(3, 1),), passed=frozenset({0})))
    assert affects(T("src/gating/run.py", S.MODIFIED, (H(3, 1), H(5, 1)), passed=frozenset({0})))
    assert affects(T("src/gating/run.py", S.MODIFIED))


@pytest.mark.parametrize(("old", "new", "hunk"), [
    ("from x import a\nfrom y import b\nfrom x import c\n",
     ["from y import b\n", "from x import a, c\n"], deps.Hunk(1, 3, 1, 2)),
    ("import sys\nsys.path.insert(0, 'p')\nimport foo\n",
     ["import foo\n", "sys.path.insert(0, 'p')\n"], H(2, 2)),
])
def test_a_hunk_that_moves_where_a_module_is_first_imported_is_not_inert(old, new, hunk):
    assert edits.inert("src/m.py", old, new, hunk) is False


def test_a_later_import_of_a_module_imported_before_is_inert():
    old = "import os\nfrom x import a\nfrom x import c\n"
    assert edits.inert("src/m.py", old, ["from x import c, d\n"], H(3, 1))
