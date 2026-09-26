"""RIGID blocks: parsing, macro expansion, determination compare, lint."""


from dl.determine import _ident_match, _rigid_match
from dl.dlparse import Index, parse
from dl.source import (
    build_determine_source,
    determined_params,
    expand_macros,
    expand_rigid_macros,
)

SOLVER = """\
#include "../lib.dl"

.comp Params {
    .decl bg(col: Color) bg(0).

    RIGID(marker,
        .decl glyph(p: Position)
        GRID_MASK_2x2(glyph,
            1, 1,
            1, _)
        .decl aim(d: DiagDir) aim(DIAG_TL).
    )
}

.init params = Params

.decl out(p: Position, col: Color)
out(P, C) :- params.marker_glyph(_, P), params.bg(C).

.comp Determine {
    .decl marker_glyph(p: Position)
    marker_glyph(P) :- ex_in(_, P, _).
    .decl marker_aim(d: DiagDir)
    marker_aim(DIAG_TL).
}
"""


def test_parse_and_placed_decls():
    ix = Index(parse(SOLVER))
    placed = ix.decls["Params"]
    assert "marker_glyph" in placed and "marker_aim" in placed
    assert [f.type for f in placed["marker_glyph"].fields] == ["D4", "Position"]
    assert "glyph" not in placed


def test_expansion():
    out = expand_rigid_macros(SOLVER)
    assert "RIGID" not in out
    assert ".decl _rigid_marker_glyph(p: Position)" in out
    assert "GRID_MASK_2x2(_rigid_marker_glyph," in out
    assert "_rigid_marker_aim(DIAG_TL)." in out
    assert ".decl marker_glyph(d4: D4, p: Position)" in out
    assert ("marker_glyph(D4, A0) :- _rigid_marker_glyph(B0), d4_elem(D4), "
            "apply(D4, B0, A0)." in out)
    assert ("marker_aim(D4, A0) :- _rigid_marker_aim(B0), d4_elem(D4), "
            "apply_diag_dir(D4, B0, A0)." in out)
    # the full pipeline expands the chart's GRID call too, and parses
    assert "GRID_MASK" not in expand_macros(SOLVER)
    Index(parse(expand_macros(SOLVER)))


def test_determined_params_and_build():
    params = determined_params(SOLVER)
    assert params == {"marker_glyph": ["Position"], "marker_aim": ["DiagDir"]}
    assert params is not None
    built = build_determine_source(SOLVER, params)
    assert ("determine_rigid_marker_glyph(D4, A0) :- determine.marker_glyph(B0), "
            "d4_elem(D4), apply(D4, B0, A0)." in built)
    assert "params_rigid_marker_glyph(D4, A0) :- params.marker_glyph(D4, A0)." in built
    assert '_determination_diff("marker_glyph")' not in built


# Position rows here use opaque scalar stand-ins: the compare never
# interprets values, only groups by the leading pose label.

def rows(*pairs):
    return [f"{d}\t{v}" for d, v in pairs]


def test_rigid_match_pose_quotient():
    # determination chart is pose 51 of the stored assembly: orbits agree
    rels = {
        "params_rigid_m_a": rows((50, 10), (51, 11), (52, 12), (53, 13)),
        "determine_rigid_m_a": rows((50, 11), (51, 12), (52, 13), (53, 10)),
    }
    assert _rigid_match({"m_a": "m"}, rels) == []
    # a different assembly: some pose signature has no counterpart
    rels["determine_rigid_m_a"] = rows((50, 11), (51, 12), (52, 13), (53, 99))
    assert _rigid_match({"m_a": "m"}, rels) == ["m_a (pose)"]


def test_rigid_match_couples_block():
    # each relation's orbit matches, but no single pose aligns both
    rels = {
        "params_rigid_m_a": rows((50, 1), (51, 2)),
        "params_rigid_m_b": rows((50, 8), (51, 9)),
        "determine_rigid_m_a": rows((50, 1), (51, 2)),
        "determine_rigid_m_b": rows((50, 9), (51, 8)),
    }
    assert _rigid_match({"m_a": "m", "m_b": "m"}, rels) == ["m_a+m_b (pose)"]


def test_ident_match_rigid_orbits():
    # ids relabeled and each id's chart in a different pose: still a match
    params = {"p_member": ["Ident", "number"], "p_color": ["Ident", "Color"]}
    rels = {
        "params_rigid_p_member": rows((50, "0\t7"), (51, "0\t8"), (50, "1\t5"), (51, "1\t6")),
        "determine_rigid_p_member": rows((50, "3\t8"), (51, "3\t7"), (50, "4\t5"), (51, "4\t6")),
        "params_ident_p_color": ["0\t2", "1\t4"],
        "determine_ident_p_color": ["3\t2", "4\t4"],
    }
    assert _ident_match(params, rels, {"p_member"})
    # color moved to the other id: signatures no longer pair up
    rels["determine_ident_p_color"] = ["3\t4", "4\t2"]
    assert not _ident_match(params, rels, {"p_member"})


