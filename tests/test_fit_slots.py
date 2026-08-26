"""fit_slots: name-mirrored slots, and the helper/slot name collision."""

import pytest

from dl.source import fit_slots

SOLVER = """\
#include "../lib.dl"

.comp Consts {
    .decl mark(col: Color) mark(7).
}

.init c = Consts

.decl out(p: Position, col: Color)
out(P, C) :- in(P, _), c.mark(C).

.comp Fit {
    .decl mark(SCHEMA)
    .decl helper(p: Position)
    helper(P) :- ex_in(_, P, _).
}
"""


def test_mirrored_slot_is_fitted():
    slots = fit_slots(SOLVER.replace("SCHEMA", "col: Color"))
    assert slots == {"mark": ["Color"]}


def test_name_collision_with_different_schema_raises():
    with pytest.raises(ValueError, match="rename the helper"):
        fit_slots(SOLVER.replace("SCHEMA", "p: Position"))
