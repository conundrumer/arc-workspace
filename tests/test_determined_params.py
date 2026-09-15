"""determined_params: name-mirrored parameters, and the helper/parameter name collision."""

import pytest

from dl.source import determined_params

SOLVER = """\
#include "../lib.dl"

.comp Params {
    .decl mark(col: Color) mark(7).
}

.init params = Params

.decl out(p: Position, col: Color)
out(P, C) :- in(P, _), params.mark(C).

.comp Determine {
    .decl mark(SCHEMA)
    .decl helper(p: Position)
    helper(P) :- ex_in(_, P, _).
}
"""


def test_mirrored_param_is_determined():
    params = determined_params(SOLVER.replace("SCHEMA", "col: Color"))
    assert params == {"mark": ["Color"]}


def test_name_collision_with_different_schema_raises():
    with pytest.raises(ValueError, match="rename the helper"):
        determined_params(SOLVER.replace("SCHEMA", "p: Position"))


DERIVED = """\
#include "../lib.dl"

.comp Params {
    .decl seed(col: Color) seed(7).

    .decl mark(col: Color)
    mark(C) :- seed(C).
}

.init params = Params

.decl out(p: Position, col: Color)
out(P, C) :- in(P, _), params.mark(C).

.comp Determine {
    .decl NAME(col: Color)
    NAME(C) :- ex_out(_, _, C).
}
"""


def test_determine_relation_named_for_derived_data_raises():
    with pytest.raises(ValueError, match="matches derived Params data"):
        determined_params(DERIVED.replace("NAME", "mark"))


def test_determine_relation_named_for_a_fact_parameter_is_determined():
    assert determined_params(DERIVED.replace("NAME", "seed")) == {"seed": ["Color"]}
