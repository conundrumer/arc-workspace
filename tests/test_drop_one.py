"""Drop-one probe: which fact a drop cuts, which parameters it covers, and
the ground each picture names."""

import shutil

import pytest

from dl import cli
from dl.drop_one import (
    GROUND_NOTE,
    _atom_sites,
    _drop_site,
    _ground_values,
    _multi_fact_params,
    _notes,
)

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


def test_a_drop_cuts_one_atom_and_leaves_its_neighbours():
    sites = _atom_sites(PICTURE, "pic")
    dropped = _drop_site(PICTURE, sites[1])

    assert "pic([0, 2, 1, 1])" not in dropped
    assert "pic([0, 2, 0, 2], 0)." in dropped
    assert "pic([1, 1, 0, 2], 3)." in dropped


def test_only_multi_fact_stored_parameters_are_covered():
    covered = {param for param, _types, _sites in _multi_fact_params(PICTURE)}

    assert covered == {"pic", "wide"}  # not bg or seat: one fact; not derived


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
