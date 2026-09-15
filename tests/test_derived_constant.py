"""Derived-constant probe: which relations it runs, what the control grids
drop, and how sibling instance paths collapse."""

import shutil

import pytest

from dl import cli
from dl.derived_constant import (
    _candidates,
    _collapse,
    _controls,
    _index,
)

SOURCE = """\
.decl in(p: Position, col: Color)
.decl out(p: Position, col: Color)
.decl mid(p: Position)
mid(P) :- in(P, _).
.decl dead(p: Position)
dead(P) :- in(P, _).
.decl stored(col: Color)
stored(1).
out(P, C) :- mid(P), stored(C).
"""


def test_a_relation_runs_only_when_it_reads_in_and_feeds_out():
    # `dead` reads `in` and no rule takes it to `out`; `stored` feeds `out`
    # and reads nothing.
    assert _candidates(_index(SOURCE)) == ["mid"]


def test_sibling_paths_under_the_same_tuples_collapse_to_one_entry():
    entries = _collapse({
        "left.axis": frozenset({"$U\t20"}),
        "right.axis": frozenset({"$U\t20"}),
        "other.axis": frozenset({"$U\t21"}),
    })

    assert sorted(e.paths for e in entries) == [
        ["left.axis", "right.axis"], ["other.axis"],
    ]


def test_the_control_grids_keep_each_extent_and_change_one():
    grids = [[[1, 2], [2, 1]], [[3, 3, 3]]]
    controls = _controls(grids)

    extents = [(len(g), len(g[0])) for g in controls]
    assert extents[:2] == [(2, 2), (1, 3)]
    assert extents[2] == (3, 1)  # a row more, a column less
    assert all(c in (1, 2) for row in controls[0] for c in row)


@pytest.mark.skipif(shutil.which("souffle") is None, reason="needs souffle")
def test_a_span_axis_fixed_across_every_example_reports(capsys):
    """4a21e3da reads the cut axis off the marker, and every example puts
    the marker on the same edge."""
    assert cli.cmd_derived_constant("4a21e3da") == 0
    out = capsys.readouterr().out

    assert "relations read `in` and feed `out`" in out
    assert "  span.axis: 1 tuple(s)" in out


