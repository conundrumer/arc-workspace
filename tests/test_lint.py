"""Body-lint checks: each fires on the shape it names and stays quiet next
to the legal form."""

from dl import solve
from dl.lint import LONE_PARSE_CAT, lint_program


def cats(src: str) -> list[str]:
    """The categories a source fires, less the header ones: a fragment under
    test carries no header."""
    return [f[0] for f in lint_program(src) if f[0] != "header"]


def of(src: str, cat: str) -> list[tuple[int, str]]:
    """The (line, why) pairs of one category."""
    return [(f[1], f[2]) for f in lint_program(src) if f[0] == cat]


def test_reserved_decl_name_fires():
    src = """\
.decl count(n: number)
count(0).
"""
    fs = [f for f in lint_program(src) if f[0] == "reserved name"]
    assert len(fs) == 1
    assert fs[0][1] == 1
    assert "`count` is a Souffle reserved word" in fs[0][2]
    assert "rename it" in fs[0][2]


def test_reserved_field_branch_and_targ_names_fire():
    src = """\
.type P = [cat: number, y: number]
.type T = Mk {n: number} | contains {}
.comp Tally<Key> {
    .decl n(key: Key, c: number)
}
.init t = Tally<count>
"""
    fs = [f for f in lint_program(src) if f[0] == "reserved name"]
    assert [f[1] for f in fs] == [1, 2, 6]
    assert "`cat`" in fs[0][2]
    assert "`contains`" in fs[1][2]
    assert "`count`" in fs[2][2]


def test_relation_named_for_a_lib_relation_fires_at_top_level_only():
    # Souffle scopes a declaration inside a comp to its instance.
    src = """\
.decl opposite(d: Dir)
.comp Parse<Key> {
    .decl opposite(key: Key, d: Dir)
}
"""
    fs = [f for f in lint_program(src) if f[0] == "lib name"]
    assert [f[1] for f in fs] == [1]
    assert "`opposite` is a lib relation" in fs[0][2]


def test_type_named_for_a_lib_type_fires():
    src = """\
.type Dir = Up {} | Down {}
"""
    fs = [f for f in lint_program(src) if f[0] == "lib name"]
    assert [f[1] for f in fs] == [1]
    assert "`Dir` is a lib type" in fs[0][2]


def test_comp_without_entry_fires(tmp_path, monkeypatch):
    import dl.lint as lint
    (tmp_path / "Ridge.md").write_text("# `Ridge<Key>`\n")
    monkeypatch.setattr(lint, "PROPOSALS_DIR", tmp_path)
    src = """\
.comp Ridge<Key> {
    .decl cell(key: Key, p: Position)
}
.comp Zigzag<Key> {
    .decl cell(key: Key, p: Position)
}
.comp Determine {
    .decl v(x: number)
}
"""
    fs = [f for f in lint_program(src) if f[0] == "comp without entry"]
    assert [f[1] for f in fs] == [4]
    assert "`Zigzag`" in fs[0][2]
    assert "docs/wf-solver/proposals/Zigzag.md" in fs[0][2]


def test_parse_comp_unread_by_determine_fires():
    src = """\
.comp Parse<Key> {
    .decl cell(key: Key, p: Position)
}
.init parse = Parse<Unit>
.comp Determine {
    .decl v(x: number)
}
"""
    fs = [f for f in lint_program(src) if f[0] == LONE_PARSE_CAT]
    assert [f[1] for f in fs] == [1]


def test_reserved_name_in_unparsable_source_fires():
    src = """\
.decl count(n: number)
count(0) :-
"""
    assert cats(src) == ["reserved name"]


def test_free_names_stay_quiet():
    # `tally` and `band_cell` are the renames; `type`, `plan`, and `init`
    # are reserved only with their leading dot.
    src = """\
.decl tally(n: number)
.decl band_cell(p: Position)
.decl type(x: number)
.decl plan(x: number)
.init init = Params
"""
    assert "reserved name" not in cats(src)


SHADOWING_LIB = """\
.comp Occurrences<Key, Val> {
    .type _KP = [key: Key, p: Position]
    .decl cell(key: Key, p: Position, v: Val)
}
"""


def test_shadowed_type_argument_fires(monkeypatch):
    monkeypatch.setattr("dl.lint._lib_source", lambda: SHADOWING_LIB)
    src = """\
.comp Parse<Key> {
    .type _KP = [key: Key, p_part: Position]
    .decl cell(key: Key, p: Position)
    .init occ = Occurrences<_KP, Color>
    occ.cell([Ky, Q], P, 1) :- cell(Ky, P), cell(Ky, Q).
}
.init parse = Parse<Unit>
"""
    fs = [f for f in lint_program(src) if f[0] == "shadowed type"]
    assert [f[1] for f in fs] == [4]
    assert "`_KP` also names a type inside `Occurrences`" in fs[0][2]
    assert "rename it" in fs[0][2]


def test_free_adt_fires_as_banned_type():
    src = """\
.type Assembly = Bare {} | With {o: Ident, rest: Assembly}
.decl out(p: Position, col: Color)
"""
    fs = [f for f in lint_program(src) if f[0] == "banned type"]
    assert [f[1] for f in fs] == [1]


def test_choice_closure_stays_quiet():
    # The type itself, a record body, a factor, and a constructor field.
    src = """\
.type Locate = Grid {} | Tile {}
.type Fill = [col: Color]
.type Choice = [loc: Locate, fill: Fill]
"""
    assert "banned type" not in cats(src)


def test_adt_filling_a_comp_param_fires():
    src = """\
.type Side = Legend {} | Field {}
.init comps = Components<Side>
"""
    fs = [f for f in lint_program(src) if f[0] == "banned type"]
    assert [f[1] for f in fs] == [1]


def test_family_case_the_representative_lacks_fires(tmp_path, monkeypatch):
    (tmp_path / "67a3c6ac.dl").write_text(".type Choice = Mirror {} | Turn {}\n")
    (tmp_path / "0d3d703e.dl").write_text(".decl out(p: Position, col: Color)\n")
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    src = """\
// 74dd1130
// @representative: 67a3c6ac Shear
"""
    fs = [f for f in lint_program(src) if f[0] == "family case"]
    assert [f[1] for f in fs] == [2]
    assert "`Shear` is no case of `67a3c6ac`'s `Choice`" in fs[0][2]

    src = """\
// c8f0f002
// @representative: 0d3d703e Recolor
"""
    fs = [f for f in lint_program(src) if f[0] == "family case"]
    assert [f[1] for f in fs] == [2]
    assert "`0d3d703e` declares no `Choice`" in fs[0][2]


INTERNAL_LIB = """\
.comp OffsetInvariance<Key, Val> {
    .decl cell(key: Key, p: Position, v: Val)  // @input
    .decl _cand(key: Key, k: number)
    _cand(Ky, K) :- cell(Ky, _, K).
    .decl period(key: Key, k: number)
    period(Ky, K) :- _cand(Ky, K).
    .init _breaks = Excess<Key, number>
}
.comp Excess<Key, Member> {
    .decl excess(key: Key, n: number)
    excess(Ky, 0) :- Ky = Ky.
}
.comp _Room<Key> {
    .decl cand(key: Key)  // @input
}
"""


def test_a_read_of_an_internal_lib_name_fires(monkeypatch):
    monkeypatch.setattr("dl.lint._lib_source", lambda: INTERNAL_LIB)
    src = """\
.init inv = OffsetInvariance<Unit, Color>
.init room = _Room<Unit>
.decl out(k: number)
out(K) :- inv._cand($U(), K).
out(K) :- inv._breaks.excess($U(), K).
out(K) :- inv.period($U(), K), !inv._cand($U(), K).
.comp Parse<Key> {
    .init inner = OffsetInvariance<Key, Color>
    .decl _own(key: Key)
    _own(Ky) :- inner.period(Ky, _).
}
.init parse = Parse<Unit>
.decl also(k: number)
also(K) :- parse._own(_), K = 0.
"""
    fs = [f for f in lint_program(src) if f[0] == "lib internal"]
    assert [(f[1], f[2].split(";")[0]) for f in fs] == [
        (2, "`_Room` is internal to the lib"),
        (4, "`_cand` is private to OffsetInvariance"),
        (5, "`_breaks` is private to OffsetInvariance"),
        (6, "`_cand` is private to OffsetInvariance"),
    ]


HEADER = """\
// 74dd1130
// @draft
// @keywords: decompose mapping
// input: a grid of tiles, one of them recolored
// output: the grid with every tile recolored
// review principle: Naming — the comp name says the mechanism
"""


def test_the_header_forms_that_pass():
    """A full header; a sibling, which names its representative in place of
    the other fields, so the missing `output:` is no finding; and a value
    continued on a line of `//` and two spaces."""
    assert of(HEADER, "header") == []

    sibling = """\
// 74dd1130
// @representative: 67a3c6ac Shear
"""
    assert of(sibling, "header") == []

    continued = """\
// 74dd1130
// @keywords: decompose
// output: the grid with every tile recolored
//  and the seam between them removed
"""
    assert of(continued, "header") == []


def test_prose_in_the_header_fires_once():
    src = """\
// 74dd1130
// @keywords: decompose
// output: a grid of tiles
// the grid is square
// and so is every tile
"""
    fs = of(src, "header")
    assert [f[0] for f in fs] == [4]
    assert "no prose in the header" in fs[0][1]


def test_a_keyword_the_doc_does_not_list_is_a_hint():
    src = """\
// 74dd1130
// @keywords: decompose tiling
// output: a grid of tiles
"""
    assert of(src, "header") == []
    assert of(src, "keyword") == [(2, "`tiling` is not in keywords.md; propose it in the review")]


RECORD_MARKED = """\
// 8618d23e
// @keywords: decompose
// output: a grid of tiles

// how wide the growth is
.type Growth =
      // one width
      Iso {{}}
      // @witness w1: plausible separates
      // per-axis widths
    | Aniso {{}}

// how the offset is computed
.type Choice =
      // derived from a growth
      Derive {{ g: Growth }}
      // @witness w2: plausible separates
      // a stored table
    | Disp {{}}

.comp Params {{
    // --- {marker} ---
    .decl sep(g: number) sep(1).
}}
"""


def test_a_marker_fixing_a_field_of_a_constructor_stays_quiet():
    assert of(RECORD_MARKED.format(marker="Derive(g=Iso)"), "case marker") == []


def test_an_include_in_the_solver_fires():
    src = """\
// 74dd1130
// @keywords: decompose
// output: a grid of tiles
#include "../lib.dl"
"""
    assert of(src, "include") == [(4, "the build adds the lib; drop the include")]


def test_a_retired_annotation_names_the_form_that_replaced_it():
    """No solver carries a retired form any more, so a run reports none of
    these and a lost check would be silent."""
    src = """\
// 74dd1130
// @keywords: decompose
// @invariant tiles: the grid is tiles
// @rule seam: the seam is removed
// @claim tiles

// what the tiles do
.type Choice = Mirror {} | Turn {}
"""
    assert of(src, "header") == [
        (3, "`@invariant` is retired; a claim about the input is "
            "`// @scene <slug>: <text>`")]
    assert (5, "`tiles` names no `@scene` or `@rule` line of the header") \
        in of(src, "claim")


def test_a_claim_reference_that_resolves_stays_quiet():
    src = """\
// 74dd1130
// @keywords: decompose
// @scene tiles: the grid is tiles
// @rule seam: the seam is removed

// what the tiles do
.type Choice =
    // @claim tiles
    Mirror {}
    // @witness w1: plausible separates
  | Turn {}
"""
    assert of(src, "claim") == []
