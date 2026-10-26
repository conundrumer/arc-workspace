"""Each component of `lib-forms.dl` states the relations of its signature component with the rows its construction gives on a small input."""

from collections.abc import Sequence
from typing import Any

from arclog_convert import libmap
from arclog_convert.lib import Lib, SIGNATURE
from arclog_convert.parity_text import FORM_PREFIX, FORMS, forms
from cli.common import LIMITS, engine
from engine import ParseFailure, Program, RecordValue, RelationName, Tuples, checkout


def rows_of(text: str, relations: Sequence[str]) -> dict[str, set[tuple[Any, ...]]]:
    """The rows of each of `relations`, relations of the instance `f`, after a run of the lib, the forms and `text`."""
    eng = engine()
    program = eng.parse(f'#include "lib.dl"\n#line 1\n{FORMS.read_text()}\n{text}', checkout.programs())
    assert isinstance(program, Program), program if isinstance(program, ParseFailure) else None
    got = eng.run(program, {}, [RelationName(("f",), r) for r in relations], LIMITS)
    assert isinstance(got, Tuples), got
    return {r: {tuple(_plain(v) for v in row[1:]) for row in got.relations[RelationName(("f",), r)]} for r in relations}


def _plain(value: Any) -> Any:
    return tuple(_plain(f) for f in value.fields) if isinstance(value, RecordValue) else value


def test_a_form_declares_the_width_of_each_relation_its_signature_component_declares() -> None:
    sig = Lib(SIGNATURE)
    for name, relations in forms().items():
        comp = name.removeprefix(FORM_PREFIX)
        renames = libmap.COMP.get(comp)
        if comp == "Gaps":   # the base of the forms that read gaps, no component of the signature
            continue
        target = sig.comps[renames.name if renames else comp]
        declared = {r.name: len(r.cols) for r in sig.relations(target.name)[1]}
        parts = renames.parts if renames else {}
        for relation, width in relations.items():
            assert declared.get(parts.get(relation, relation)) == width, (name, relation)
        assert {parts.get(r, r) for r in relations} >= declared.keys(), name


def test_a_tiling_places_each_inner_position_in_each_outer_tile() -> None:
    got = rows_of(""".init f = SigTiling<Unit>
f.outer($U(), [0, 1, 0, 1]).
f.outer($U(), [1, 0, 0, 1]).
f.inner($U(), [0, 1, 0, 1]).
f.inner($U(), [1, 0, 0, 1]).
""", ["cell"])
    assert got["cell"] == {((0, 1, 0, 1), (0, 1, 0, 1), (0, 3, 0, 3)), ((0, 1, 0, 1), (1, 0, 0, 1), (1, 2, 0, 3)),
                           ((1, 0, 0, 1), (0, 1, 0, 1), (2, 1, 0, 3)), ((1, 0, 0, 1), (1, 0, 0, 1), (3, 0, 0, 3))}


def test_a_tiling_with_a_gap_spaces_its_tiles() -> None:
    got = rows_of(""".init f = SigTiling<Unit>
f.outer($U(), [0, 1, 0, 0]).
f.outer($U(), [1, 0, 0, 0]).
f.inner($U(), [0, 0, 0, 0]).
f.gap($U(), AXIS_V, 1).
""", ["cell"])
    assert got["cell"] == {((0, 1, 0, 0), (0, 0, 0, 0), (0, 2, 0, 0)), ((1, 0, 0, 0), (0, 0, 0, 0), (2, 0, 0, 0))}


def test_a_division_cuts_each_axis_into_its_parts() -> None:
    got = rows_of(""".init f = SigDivision<Unit>
f.cell($U(), [0, 3, 0, 3]).
f.cell($U(), [1, 2, 0, 3]).
f.cell($U(), [3, 0, 3, 0]).
f.parts($U(), AXIS_V, 2).
f.parts($U(), AXIS_H, 2).
""", ["tile"])
    assert got["tile"] == {((0, 3, 0, 3), (0, 1, 0, 1), (0, 1, 0, 1)), ((1, 2, 0, 3), (0, 1, 0, 1), (1, 0, 0, 1)),
                           ((3, 0, 3, 0), (1, 0, 1, 0), (1, 0, 1, 0))}


def test_a_division_by_side_with_no_count_on_the_other_axis_passes_that_axis_through() -> None:
    got = rows_of(""".init f = SigDivision<Unit>
f.cell($U(), [0, 3, 0, 1]).
f.side($U(), AXIS_V, 2).
""", ["tile"])
    assert got["tile"] == {((0, 3, 0, 1), (0, 1, 0, 0), (0, 1, 0, 1))}


def test_the_divisions_of_an_extent_are_each_count_side_and_gap_that_fill_it() -> None:
    got = rows_of(""".init f = SigExtentDivisions<Unit>
f.frame($U(), [0, 3, 0, 0]).
""", ["division"])
    vertical = {row[1:] for row in got["division"] if row[0] == 20}
    assert vertical == {(2, 1, 2), (2, 2, 0), (2, 3, -2), (3, 2, -1), (4, 1, 0)}


def test_a_ray_runs_from_its_source_to_its_last_node() -> None:
    got = rows_of(""".init f = SigRay<Unit>
f.source($U(), [1, 1, 1, 1]).
f.dir($U(), DIR_R).
f.node($U(), [1, 1, 1, 1]).
f.node($U(), [1, 1, 2, 0]).
""", ["ray", "end"])
    assert got["end"] == {((1, 1, 2, 0), 13, 1, (1, 1, 1, 1))}
    assert got["ray"] == {((1, 1, 1, 1), 13, 0, (1, 1, 1, 1)), ((1, 1, 2, 0), 13, 1, (1, 1, 1, 1))}


def test_a_ray_from_a_source_off_the_grid_enters_it() -> None:
    got = rows_of(""".init f = SigRay<Unit>
f.source($U(), [1, 1, -1, 3]).
f.dir($U(), DIR_R).
f.node($U(), [1, 1, 0, 2]).
""", ["end"])
    assert got["end"] == {((1, 1, 0, 2), 13, 1, (1, 1, -1, 3))}


def test_a_distance_is_the_least_cost_from_a_start() -> None:
    got = rows_of(""".init f = SigGraphDistance<Unit, number>
f.edge($U(), 1, 2).
f.edge($U(), 2, 3).
f.edge($U(), 1, 3).
f.weight($U(), 1, 3, 5).
f.weight($U(), 3, 4, 1).
f.seed($U(), 1).
f.source_distance($U(), 2, 10).
""", ["distance", "pred"])
    assert got["distance"] == {(1, 0), (2, 1), (3, 1), (4, 2)}
    assert got["pred"] == {(2, 1), (3, 1), (4, 3)}



def test_an_order_under_before_ranks_the_members_and_a_probe() -> None:
    got = rows_of(""".init f = SigOrder<Unit, number>
f.elem($U(), 1). f.elem($U(), 2). f.elem($U(), 3).
f.before($U(), 1, 2). f.before($U(), 2, 3). f.before($U(), 1, 3).
f.probe($U(), 9). f.before($U(), 2, 9).
""", ["rank", "rank_desc", "first", "last", "next", "cyclic_successor"])
    assert got["rank"] == {(1, 0), (2, 1), (3, 2), (9, 1)}
    assert got["rank_desc"] == {(1, 2), (2, 1), (3, 0), (9, 0)}
    assert (got["first"], got["last"], got["next"]) == ({(1,)}, {(3,)}, {(1, 2), (2, 3)})
    assert got["cyclic_successor"] == {(1, 2), (2, 3), (3, 1)}


def test_an_order_under_score_ties_members_and_leaves_an_unscored_member_at_both_ends() -> None:
    got = rows_of(""".init f = SigOrder<Unit, number>
f.elem($U(), 1). f.elem($U(), 2). f.elem($U(), 3). f.elem($U(), 4).
f.score($U(), 1, 5). f.score($U(), 2, 5). f.score($U(), 3, 8).
f.probe($U(), 9). f.score($U(), 9, 6).
""", ["rank", "rank_desc", "first", "last", "next"])
    assert got["rank"] == {(1, 0), (2, 0), (3, 2), (4, 0), (9, 2)}
    assert got["rank_desc"] == {(1, 1), (2, 1), (3, 0), (4, 0), (9, 1)}
    assert (got["first"], got["last"], got["next"]) == ({(1,), (2,), (4,)}, {(3,), (4,)}, {(1, 3), (2, 3)})


def test_an_order_under_score_breaks_a_tie_by_secondary_score() -> None:
    got = rows_of(""".init f = SigOrder<Unit, number>
f.elem($U(), 1). f.elem($U(), 2). f.elem($U(), 3). f.elem($U(), 4).
f.score($U(), 1, 5). f.score($U(), 2, 5). f.score($U(), 3, 5). f.score($U(), 4, 7).
f.secondary_score($U(), 2, 3). f.secondary_score($U(), 3, 1).
""", ["rank", "rank_desc", "first", "last", "next"])
    assert got["rank"] == {(1, 0), (3, 1), (2, 2), (4, 3)}   # a member with none precedes the others of its score
    assert got["rank_desc"] == {(1, 3), (3, 2), (2, 1), (4, 0)}
    assert (got["first"], got["last"], got["next"]) == ({(1,)}, {(4,)}, {(1, 3), (3, 2), (2, 4)})


def test_a_rim_is_the_cells_with_a_step_out_of_the_set() -> None:
    got = rows_of(""".init f = SigRim<Unit>
f.cell($U(), [0, 1, 0, 1]).
f.cell($U(), [1, 0, 0, 1]).
f.dir(DIR_T).
f.dir(DIR_B).
""", ["rim", "rim_dir"])
    assert got["rim"] == {((0, 1, 0, 1),), ((1, 0, 0, 1),)}
    assert got["rim_dir"] == {((0, 1, 0, 1), 10), ((1, 0, 0, 1), 11)}


def test_an_agreement_finds_the_elements_that_map_a_family_onto_itself() -> None:
    got = rows_of(""".init f = SigAgreement<Unit, number>
f.source($U(), [0, 1, 0, 1], 5).
f.source($U(), [1, 0, 0, 1], 6).
f.target($U(), [0, 1, 0, 1], 5).
f.target($U(), [1, 0, 0, 1], 6).
f.transform(D4_ID).
f.transform(D4_TB).
""", ["mismatch", "conflict"])
    assert got["mismatch"] == {(55,)}
    assert got["conflict"] == {(55,)}


def test_an_agreement_with_no_transform_admits_the_eight_elements() -> None:
    got = rows_of(""".init f = SigAgreement<Unit, number>
f.source($U(), [0, 1, 0, 1], 5).
f.target($U(), [0, 1, 0, 1], 5).
""", ["mismatch", "conflict"])
    assert got["mismatch"] == {(d,) for d in (51, 52, 53, 54, 55, 57)}   # every element but the identity and the diagonal one
    assert got["conflict"] == set()
