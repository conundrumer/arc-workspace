"""Drop-one probe: which fact a drop cuts, which parameters it covers, and
the noise notes a dropped fact carries."""

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from dl import cli
from dl import drop_one
from dl.drop_one import (
    GROUND_NOTE,
    SWEEP_NOTE,
    _atom_sites,
    _drop_site,
    _ground_values,
    _multi_fact_params,
    _notes,
    drop_one_report,
    render_drop_one,
)

STEM = "abcd1234"

PICTURE = """\
.comp Params {
    .decl bg(col: Color) bg(0).
    .decl seat(p: Position) seat([1, 1, 1, 1]).
    .decl pic(p: Position, col: Color)
    pic([0, 2, 0, 2], 0). pic([0, 2, 1, 1], 0). pic([1, 1, 0, 2], 3).
    .decl wide(id: Ident, g: Grid)
    wide(1, $G()). wide(2, $G()).
    .decl derived(col: Color)
    derived(C) :- bg(C).
}
"""


def _stub(tmp_path: Path, monkeypatch, source: str, task) -> None:
    (tmp_path / f"{STEM}.dl").write_text(source)
    monkeypatch.setattr(drop_one, "SOLVERS_DIR", tmp_path)
    monkeypatch.setattr(drop_one, "load_task", lambda task_id: task)


def test_a_drop_cuts_one_atom_and_leaves_its_neighbours():
    sites = _atom_sites(PICTURE, "pic")
    dropped = _drop_site(PICTURE, sites[1])

    assert "pic([0, 2, 1, 1])" not in dropped
    assert "pic([0, 2, 0, 2], 0)." in dropped
    assert "pic([1, 1, 0, 2], 3)." in dropped


def test_only_multi_fact_stored_parameters_are_covered():
    covered = {param for param, _types, _sites in _multi_fact_params(PICTURE)}

    assert covered == {"pic", "wide"}  # not bg or seat: one fact; not derived


def test_a_parameter_no_domain_enumerates_is_covered():
    """The cut is textual, so an Ident or a Grid column is no obstacle."""
    [sites] = [s for p, _t, s in _multi_fact_params(PICTURE) if p == "wide"]

    assert "wide(1, $G())" not in _drop_site(PICTURE, sites[0])


def test_a_majority_value_and_the_solvers_bg_read_as_ground():
    ground = _ground_values(PICTURE, ["Position", "Color"],
                            [["[0, 2, 0, 2]", "0"], ["[0, 2, 1, 1]", "0"],
                             ["[1, 1, 0, 2]", "3"]])

    assert ground == {(): {"0"}}


def test_each_picture_of_a_catalog_names_its_own_ground():
    """A catalog holds several pictures under a leading key. Each picture is
    its own frame, so the majority is taken per key."""
    types = ["Ident", "Position", "Color"]
    facts = [["0", "[0, 2, 0, 2]", "2"], ["0", "[0, 2, 1, 1]", "2"],
             ["0", "[1, 1, 0, 2]", "4"],
             ["1", "[0, 2, 0, 2]", "8"], ["1", "[0, 2, 1, 1]", "8"],
             ["1", "[1, 1, 0, 2]", "2"]]

    grounds = _ground_values("", types, facts)

    assert grounds == {("0",): {"2"}, ("1",): {"8"}}
    assert _notes(types, ["0", "[0, 2, 0, 2]", "2"], grounds) == [GROUND_NOTE]
    assert _notes(types, ["1", "[1, 1, 0, 2]", "2"], grounds) == []


def test_a_sparse_pictures_commonest_ink_is_not_ground():
    """A sparse picture omits its ground cells, so no stored value holds a
    majority for the ground."""
    facts = [["[0, 1, 0, 1]", "5"], ["[1, 0, 1, 0]", "1"]]

    assert _ground_values("", ["Position", "Color"], facts) == {(): set()}


def test_a_ground_cell_and_an_enumerable_parameter_each_note_themselves():
    types = ["Position", "Color"]

    assert _notes(types, ["[0, 2, 0, 2]", "0"], {(): {"0"}}) == [GROUND_NOTE,
                                                                SWEEP_NOTE]
    assert _notes(types, ["[1, 1, 0, 2]", "3"], {(): {"0"}}) == [SWEEP_NOTE]
    assert _notes(["Ident", "Grid"], ["1", "$G()"], {}) == []


def test_a_fact_the_test_pairs_need_reports_apart(tmp_path, monkeypatch):
    task = SimpleNamespace(train=["t"], test=["s"])
    _stub(tmp_path, monkeypatch, PICTURE, task)
    # Every drop holds the train profile; the test pairs hold only while
    # every pic cell stands.
    monkeypatch.setattr(
        drop_one, "_profile",
        lambda source, examples: (
            "ref" if examples is task.train
            else "test" if source.count("pic([") == 3
            else None))

    report = drop_one_report(STEM)
    lines = render_drop_one(STEM, report)
    hits, tested, params = report

    assert (tested, params) == (5, 2)
    assert [(h[1], h[2]) for h in hits] == [
        ("pic([0, 2, 0, 2], 0)", False),
        ("pic([0, 2, 1, 1], 0)", False),
        ("pic([1, 1, 0, 2], 3)", False),
        ("wide(1, $G())", True),
        ("wide(2, $G())", True),
    ]
    assert "2 fact(s) no pair needs:" in lines
    assert ("3 fact(s) the train pairs do not need, and the test pairs do:"
            in lines)
    assert f"  pic([0, 2, 0, 2], 0)  — {GROUND_NOTE}; {SWEEP_NOTE}" in lines
    assert "  wide(1, $G())" in lines


def test_a_baseline_that_fails_train_reports_no_facts(tmp_path, monkeypatch):
    _stub(tmp_path, monkeypatch, PICTURE,
          SimpleNamespace(train=["t"], test=["s"]))
    monkeypatch.setattr(drop_one, "_profile", lambda source, examples: None)

    assert drop_one_report(STEM) is None
    assert render_drop_one(STEM, None) == [
        "baseline fails: stored source does not pass train"]


@pytest.mark.skipif(shutil.which("souffle") is None, reason="needs souffle")
def test_a_stored_footprints_dead_cells_report_against_the_pairs(capsys):
    """60b61512 stores a 3x3 footprint; two of its cells lie outside every
    train shape and inside a test one."""
    assert cli.cmd_drop_one("60b61512") == 0
    out = capsys.readouterr().out

    assert "9 stored facts across 1 multi-fact parameter" in out
    assert ("2 fact(s) the train pairs do not need, and the test pairs do:"
            in out)
    assert "  footprint([0, 2, 0, 2])" in out
    assert "  footprint([0, 2, 1, 1])" in out
