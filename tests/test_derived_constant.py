"""Derived-constant probe: which relations it runs, what the control grids
drop, and how sibling instance paths collapse."""

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from dl import cli
from dl import derived_constant
from dl.derived_constant import (
    Constant,
    _candidates,
    _collapse,
    _controls,
    _index,
    derived_constant_report,
    render_derived_constant,
)

STEM = "abcd1234"

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


def _stub(tmp_path: Path, monkeypatch, source: str, task) -> None:
    (tmp_path / f"{STEM}.dl").write_text(source)
    monkeypatch.setattr(derived_constant, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(derived_constant, "load_task", lambda task_id: task)
    # `_sets` answers in call order, so the pool takes one grid at a time.
    monkeypatch.setattr(derived_constant, "_pool_workers", lambda: 1)


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


def _sets(per_grid: dict[str, list[frozenset[str]]]):
    """A `_tuple_sets` stand-in reading each relation's tuples off a table,
    one entry per grid in call order."""
    calls = {"n": 0}

    def sets(built, grid, names):
        i = calls["n"]
        calls["n"] += 1
        return {n: per_grid[n][i] for n in names}

    return sets


def test_a_relation_the_controls_do_not_move_drops_out(tmp_path, monkeypatch):
    _stub(tmp_path, monkeypatch, SOURCE.replace("dead", "held"),
          SimpleNamespace(train=[SimpleNamespace(input=[[1]])],
                          test=[SimpleNamespace(input=[[2]])]))
    monkeypatch.setattr(derived_constant, "_candidates",
                        lambda ix: ["mid", "held", "empty"])
    same, moved, empty = frozenset({"a"}), frozenset({"b"}), frozenset()
    monkeypatch.setattr(derived_constant, "_tuple_sets", _sets({
        # two examples, then the three control grids they yield
        "mid": [same] * 2 + [moved] * 3,
        "held": [same] * 5,
        "empty": [empty] * 5,
    }))

    constants, tested, dropped = derived_constant_report(STEM)

    assert (tested, dropped) == (3, 1)  # `held` holds over the controls
    assert [c.paths for c in constants] == [["mid"]]


def test_a_relation_that_differs_on_one_example_is_no_constant(
    tmp_path, monkeypatch
):
    _stub(tmp_path, monkeypatch, SOURCE,
          SimpleNamespace(train=[SimpleNamespace(input=[[1]])],
                          test=[SimpleNamespace(input=[[2]])]))
    monkeypatch.setattr(derived_constant, "_tuple_sets", _sets({
        "mid": [frozenset({"a"}), frozenset({"b"})],
    }))

    report = derived_constant_report(STEM)

    assert report == "no constant relation among the 1 that read `in`"
    assert render_derived_constant(STEM, report) == [
        f"{STEM}.dl: no constant relation among the 1 that read `in`"]


def test_the_report_names_the_paths_the_tuples_and_the_controls_drop():
    lines = render_derived_constant(
        STEM, ([Constant(paths=["left.axis", "right.axis"],
                         tuples=["$U\t20"])], 12, 2))

    assert lines[0] == "12 relations read `in` and feed `out`"
    assert "  left.axis, right.axis: 1 tuple(s) — $U, 20" in lines
    assert ("2 relation(s) hold their tuples on the control grids too, so "
            "they do not read the input") in lines


@pytest.mark.skipif(shutil.which("souffle") is None, reason="needs souffle")
def test_a_span_axis_fixed_across_every_example_reports(capsys):
    """4a21e3da reads the cut axis off the marker, and every example puts
    the marker on the same edge."""
    assert cli.cmd_derived_constant("4a21e3da") == 0
    out = capsys.readouterr().out

    assert "relations read `in` and feed `out`" in out
    assert "  span.axis: 1 tuple(s)" in out


def test_the_verdict_stands_beside_the_controls_drop():
    """Every constant the controls drop leaves nothing to report, and the
    verdict says so without denying the constancy the drop line states."""
    lines = render_derived_constant(STEM, ([], 60, 2))

    assert lines == [
        "60 relations read `in` and feed `out`",
        "no relation reads the input and holds the same tuples on every "
        "example",
        "",
        "2 relation(s) hold their tuples on the control grids too, so they "
        "do not read the input",
    ]
