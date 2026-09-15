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


def test_reserved_init_name_fires():
    src = """\
.comp Tally<Key> {
    .decl n(key: Key, c: number)
}
.init count = Tally<Color>
"""
    fs = [f for f in lint_program(src) if f[0] == "reserved name"]
    assert [f[1] for f in fs] == [4]


def test_reserved_name_inside_comp_fires():
    src = """\
.comp Parse<Key> {
    .decl band(key: Key, p: Position)
}
"""
    fs = [f for f in lint_program(src) if f[0] == "reserved name"]
    assert [f[1] for f in fs] == [2]
    assert "`band`" in fs[0][2]


def test_reserved_type_and_comp_names_fire():
    src = """\
.type max <: number
.comp output {
    .decl v(x: number)
}
"""
    fs = [f for f in lint_program(src) if f[0] == "reserved name"]
    assert [f[1] for f in fs] == [1, 2]


def test_reserved_attribute_name_fires():
    src = """\
.decl r(ord: number)
r(0).
"""
    fs = [f for f in lint_program(src) if f[0] == "reserved name"]
    assert [f[1] for f in fs] == [1]
    assert "`ord`" in fs[0][2]


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


def test_reserved_comp_param_fires():
    src = """\
.comp Pick<match> {
    .decl v(x: match)
}
"""
    fs = [f for f in lint_program(src) if f[0] == "reserved name"]
    assert [f[1] for f in fs] == [1]
    assert "`match`" in fs[0][2]


def test_type_named_for_a_lib_comp_fires():
    src = """\
.type Reach = Near {} | Object {}
.type Choice = [sp: Reach]
"""
    fs = [f for f in lint_program(src) if f[0] == "lib name"]
    assert [f[1] for f in fs] == [1]
    assert fs[0][2] == "`Reach` is a lib component; rename it"


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


def test_lib_macro_in_body_fires_as_orientation_literal():
    src = """\
.decl v(s: Sym)
v(SYM_BOX).
"""
    fs = [f for f in lint_program(src) if f[0] == "orientation literal"]
    assert [(f[1], f[2]) for f in fs] == [(2, "SYM_BOX")]


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


def test_parse_comp_without_determine_fires():
    src = """\
.comp Parse<Key> {
    .decl cell(key: Key, p: Position)
}
.init parse = Parse<Unit>
"""
    fs = [f for f in lint_program(src) if f[0] == LONE_PARSE_CAT]
    assert [f[1] for f in fs] == [1]
    assert "no Determine comp" in fs[0][2]


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
    assert "the Determine comp does not read this parse" in fs[0][2]


def test_parse_comp_instanced_in_determine_stays_quiet():
    src = """\
.comp Parse<Key> {
    .decl cell(key: Key, p: Position)
}
.comp Determine {
    .init parse = Parse<Unit>
    .decl v(x: number)
}
"""
    assert LONE_PARSE_CAT not in cats(src)


def test_parse_comp_read_in_determine_stays_quiet():
    src = """\
.comp Parse<Key> {
    .decl cell(key: Key, p: Position)
}
.init parse = Parse<Unit>
.comp Determine {
    .decl v(p: Position)
    v(P) :- parse.cell(_, P).
}
"""
    assert LONE_PARSE_CAT not in cats(src)


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


def test_reserved_word_in_a_comment_stays_quiet():
    src = """\
// .decl count(n: number)
.decl tally(n: number)
"""
    assert "reserved name" not in cats(src)


def test_qualified_member_named_for_a_keyword_stays_quiet():
    # The check reads declared names, not uses, so a member access that
    # merely ends in a keyword is not a collision.
    src = """\
.decl v(x: number)
v(N) :- params.max(N).
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


def test_shadowed_type_reaches_through_a_nested_instance(monkeypatch):
    monkeypatch.setattr("dl.lint._lib_source", lambda: SHADOWING_LIB)
    src = """\
.comp Wrap<K> {
    .init o = Occurrences<K, Color>
    .decl cell(key: K, p: Position)
    o.cell(K, P, 1) :- cell(K, P).
}
.type _KP = [key: Unit, p_part: Position]
.init w = Wrap<_KP>
"""
    fs = [f for f in lint_program(src) if f[0] == "shadowed type"]
    assert [f[1] for f in fs] == [7]
    assert "`Wrap`" in fs[0][2]


def test_free_type_argument_stays_quiet():
    # `KD` collides with nothing inside `Bbox`, type-parameter field
    # and all.
    src = """\
.comp Parse<Key> {
    .type KD = [key: Key, p_part: Position]
    .decl cell(key: Key, p: Position)
    .init box = Bbox<KD>
    box.cell([Ky, Q], P) :- cell(Ky, P), cell(Ky, Q).
}
.init parse = Parse<Unit>
"""
    assert "shadowed type" not in cats(src)


def test_type_argument_to_a_typeless_comp_stays_quiet():
    src = """\
.type KP = [key: Unit, p_part: Position]
.init tally = Mode<KP>
"""
    assert "shadowed type" not in cats(src)


def test_free_adt_fires_as_banned_type():
    src = """\
.type Assembly = Bare {} | With {o: Ident, rest: Assembly}
.decl out(p: Position, col: Color)
"""
    fs = [f for f in lint_program(src) if f[0] == "banned type"]
    assert [f[1] for f in fs] == [1]
    assert "`Assembly` is outside the sanctioned type kinds" in fs[0][2]


def test_choice_closure_stays_quiet():
    # The type itself, a record body, a factor, and a constructor field.
    src = """\
.type Locate = Grid {} | Tile {}
.type Fill = [col: Color]
.type Choice = [loc: Locate, fill: Fill]
"""
    assert "banned type" not in cats(src)


def test_record_filling_a_comp_param_stays_quiet():
    src = """\
.type RunKey = [p_line: Position, col: Color]
.init runs = Components<RunKey>
"""
    assert "banned type" not in cats(src)


def test_adt_filling_a_comp_param_fires():
    src = """\
.type Side = Legend {} | Field {}
.init comps = Components<Side>
"""
    fs = [f for f in lint_program(src) if f[0] == "banned type"]
    assert [f[1] for f in fs] == [1]


def test_record_filling_no_param_fires():
    src = """\
.type Leg = [p: Position, d: Dir]
.decl on_path(leg: Leg)
"""
    fs = [f for f in lint_program(src) if f[0] == "banned type"]
    assert [f[1] for f in fs] == [1]


def test_tiebreak_resolution_and_its_fields_stay_quiet():
    src = """\
.type Piece = Bar {} | Dot {}
.type TiebreakResolution =
    End {} | Sit {b: Position, pc: Piece, rest: TiebreakResolution}
"""
    assert "banned type" not in cats(src)


def test_type_in_a_skipped_comp_stays_quiet():
    # A proposal comp is skipped wholesale, its types included.
    src = """\
.comp Profile<Key> {
    .type Edge = Lo {} | Hi {}
    .decl cell(key: Key, p: Position)
}
"""
    assert "banned type" not in cats(src)


def test_type_in_determine_lints_and_a_filled_record_there_stays_quiet():
    src = """\
.comp Determine {
    .type EC = [e: Example, col: Color]
    .type Tag = A {} | B {}
    .init tally = Mode<EC>
}
"""
    fs = [f for f in lint_program(src) if f[0] == "banned type"]
    assert [f[1] for f in fs] == [3]


def test_plan_join_order_passes_through():
    """A `.plan` names body positions, so its numbers are not data."""
    src = """\
.comp Determine {
    .decl walk(a: Position, b: Position)
    walk(A, B) :- step(A, B).
    walk(A, B) :- walk(A, C), step(C, B).
    .plan 0:(2, 1)
}
"""
    assert cats(src) == []


def test_family_case_the_representative_lacks_fires(tmp_path, monkeypatch):
    (tmp_path / "67a3c6ac.dl").write_text(".type Choice = Mirror {} | Turn {}\n")
    (tmp_path / "0d3d703e.dl").write_text(".decl out(p: Position, col: Color)\n")
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    src = """\
// 74dd1130
// representative: 67a3c6ac Shear
"""
    fs = [f for f in lint_program(src) if f[0] == "family case"]
    assert [f[1] for f in fs] == [2]
    assert "`Shear` is no case of `67a3c6ac`'s `Choice`" in fs[0][2]

    src = """\
// c8f0f002
// representative: 0d3d703e Recolor
"""
    fs = [f for f in lint_program(src) if f[0] == "family case"]
    assert [f[1] for f in fs] == [2]
    assert "`0d3d703e` declares no `Choice`" in fs[0][2]


def test_family_case_the_representative_is_a_record_fires(tmp_path, monkeypatch):
    (tmp_path / "87ab05b8.dl").write_text(".type Choice = [d: DecChoice, b: Body]\n")
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    src = """\
// 74dd1130
// representative: 87ab05b8 Shear
"""
    fs = [f for f in lint_program(src) if f[0] == "family case"]
    assert [f[1] for f in fs] == [2]
    assert fs[0][2] == (
        "`87ab05b8`'s `Choice` is a record; a sibling of it names no case"
    )


def test_family_case_the_representative_holds_stays_quiet(tmp_path, monkeypatch):
    (tmp_path / "67a3c6ac.dl").write_text(".type Choice = Mirror {} | Turn {}\n")
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    src = """\
// 74dd1130
// representative: 67a3c6ac Turn
"""
    assert "family case" not in cats(src)


def test_family_case_the_grammar_rejects_fires(tmp_path, monkeypatch):
    (tmp_path / "67a3c6ac.dl").write_text(".type Choice = Mirror {} | Turn {}\n")
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    src = """\
// 74dd1130
// representative: 67a3c6ac Mirror Turn
// representative:
"""
    fs = [f for f in lint_program(src) if f[0] == "family case"]
    assert [f[1] for f in fs] == [2, 3]
    assert "at most one case name after the id" in fs[0][2]
    assert fs[0][3] == "// representative: 67a3c6ac Mirror Turn"


def test_family_case_the_line_with_no_case_stays_quiet(tmp_path, monkeypatch):
    (tmp_path / "67a3c6ac.dl").write_text(".type Choice = Mirror {} | Turn {}\n")
    monkeypatch.setattr(solve, "SOLVERS_DIR", tmp_path)
    src = """\
// 74dd1130
// representative: 67a3c6ac
"""
    assert "family case" not in cats(src)


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
    assert [(f[1], f[2]) for f in fs] == [
        (2, "`_Room` is internal to the lib; instantiate a public unit"),
        (4, "`_cand` is internal to OffsetInvariance; read a public readout"),
        (5, "`_breaks` is internal to OffsetInvariance; read a public readout"),
        (6, "`_cand` is internal to OffsetInvariance; read a public readout"),
    ]


# ---------- the header ----------

HEADER = """\
// 74dd1130
// draft
// keywords: decompose mapping
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
// representative: 67a3c6ac Shear
"""
    assert of(sibling, "header") == []

    continued = """\
// 74dd1130
// keywords: decompose
// output: the grid with every tile recolored
//  and the seam between them removed
"""
    assert of(continued, "header") == []


def test_a_continuation_line_with_a_colon_passes():
    """A continuation line stands in the continuation form, so its text is a
    value, whatever colon it holds."""
    src = """\
// 74dd1130
// keywords: decompose
// output: the grid with every tile recolored
//  pieces recolored: its wires take one fill
"""
    assert of(src, "header") == []


def test_the_old_header_labels_fire():
    src = """\
// 74dd1130
// theme: tiling
// shape: latent-canvas
// family: 67a3c6ac
// output: a grid of tiles
"""
    fs = of(src, "header")
    assert [f[0] for f in fs] == [1, 2, 3, 4]
    assert "`theme:` is no header field" in fs[1][1]
    assert "`shape:` is no header field" in fs[2][1]
    assert "`family:` is no header field" in fs[3][1]
    assert fs[0][1] == "the header carries `keywords:` or `representative:`"


def test_prose_in_the_header_fires_once():
    src = """\
// 74dd1130
// keywords: decompose
// output: a grid of tiles
// the grid is square
// and so is every tile
"""
    fs = of(src, "header")
    assert [f[0] for f in fs] == [4]
    assert "no prose in the header" in fs[0][1]


def test_a_review_line_off_a_draft_passes():
    src = """\
// 74dd1130
// keywords: decompose
// output: a grid of tiles
// review principle: Naming — the comp name says the mechanism
"""
    assert of(src, "header") == []


def test_a_review_sweep_line_passes():
    src = """\
// 74dd1130
// draft
// keywords: decompose
// output: a grid of tiles
// review sweep: recolor — the pairs leave the fill color open
"""
    assert of(src, "header") == []


def test_a_keyworded_header_without_an_output_fires():
    src = """\
// 74dd1130
// keywords: decompose
// input: a grid of tiles
"""
    assert of(src, "header") == [(1, "the header carries `output:`")]


def test_a_keyword_the_doc_does_not_list_is_a_hint():
    src = """\
// 74dd1130
// keywords: decompose tiling
// output: a grid of tiles
"""
    assert of(src, "header") == []
    assert of(src, "keyword") == [(2, "`tiling` is not in keywords.md; propose it in the review")]


def test_keywords_the_doc_lists_pass():
    src = """\
// 74dd1130
// keywords: decompose mapping latent-canvas
// output: a grid of tiles
"""
    assert of(src, "keyword") == []


def test_the_concept_field_stands_between_keywords_and_input():
    src = """\
// 74dd1130
// keywords: decompose
// concept: the grid is a tiling, and the output is one tile
// input: a tiled grid
// output: a grid of tiles
"""
    assert of(src, "header") == []
    src = """\
// 74dd1130
// keywords: decompose
// input: a tiled grid
// concept: the grid is a tiling, and the output is one tile
// output: a grid of tiles
"""
    assert [f[0] for f in of(src, "header")] == [4]


# ---------- the glosses over the choice ----------


CHOICE = """\
// 74dd1130
// keywords: decompose
// concept: the tiles turn
// output: a grid of tiles

// which way the tiles turn
.type Choice =
      // mirror across the seam
      Mirror {{}}
      // a quarter turn
{turn_line}    | Turn {{}}
"""


def test_a_branch_after_the_first_carries_a_deviation_line():
    src = CHOICE.format(turn_line="      // @deviation: -1 +0 ~0\n")
    assert of(src, "deviation") == []
    fs = of(CHOICE.format(turn_line=""), "deviation")
    assert fs == [(11, "`Turn` carries `// @deviation: -<relaxed> +<added> "
                       "~<contradicted>` under its gloss")]


def test_the_first_branch_carries_no_deviation_line():
    src = CHOICE.format(turn_line="      // @deviation: -1 +0 ~0\n").replace(
        "      // mirror across the seam\n",
        "      // mirror across the seam\n      // @deviation: -0 +0 ~0\n")
    fs = of(src, "deviation")
    assert fs == [(10, "`Mirror` stands first, so it is the intended branch and "
                      "carries no `@deviation` line")]


def test_the_field_type_of_a_constructor_record_is_checked():
    src = """\
// 74dd1130
// keywords: decompose
// concept: the tiles turn
// output: a grid of tiles

// how far the tiles turn
.type Amount =
      // a quarter turn
      Quarter {}
      // a half turn
    | Half {}

// which way the tiles turn
.type Choice =
      // a turn by an amount
      Turn { a: Amount }
      // mirror across the seam
      // @deviation: -1 +0 ~0
    | Mirror {}
"""
    fs = of(src, "deviation")
    assert fs == [(11, "`Half` carries `// @deviation: -<relaxed> +<added> "
                       "~<contradicted>` under its gloss")]


def test_a_choice_on_one_line_fires():
    src = """\
// 74dd1130
// keywords: decompose
// output: a grid of tiles

.type Choice = Mirror {} | Turn {}
"""
    fs = of(src, "gloss")
    assert [f[0] for f in fs] == [5, 5, 5]
    assert fs[0][1] == "a gloss stands above `Choice`: what the choice is"
    assert fs[1][1] == "`Mirror` opens its own line, under its gloss"
    assert fs[2][1] == "`Turn` opens its own line, under its gloss"


def test_a_record_choice_is_read_through_its_field_types():
    src = """\
// 74dd1130
// keywords: decompose
// output: a grid of tiles

// what to do, and what to do it to
.type Choice = [d: DecChoice, b: Body]

// which way the tiles turn
.type DecChoice =
      // mirror across the seam
      Mirror {}
      // a quarter turn
    | Turn {}

// what the choice acts on
.type Body =
      Whole {}
"""
    assert of(src, "gloss") == [(17, "a gloss stands above `Whole`")]


# ---------- the case markers ----------


MARKED = """\
// 74dd1130
// keywords: decompose
// output: a grid of tiles

// which way the tiles turn
.type Choice =
      // mirror across the seam
      Mirror {{}}
      // @deviation: -0 +0 ~0
      // a quarter turn
    | Turn {{}}

.comp Params {{
    // --- {marker} ---
    .decl seam(d: Dir) seam(DIR_T).
}}
"""


def test_a_marker_joining_case_names_with_a_slash_fires():
    fs = of(MARKED.format(marker="Mirror / Turn"), "case marker")
    assert fs == [(14, "a marker over several cases joins their names with a "
                       "comma: `// --- Box, Erode ---`")]


def test_a_marker_joining_case_names_with_a_comma_stays_quiet():
    assert of(MARKED.format(marker="Mirror, Turn"), "case marker") == []


RECORD_MARKED = """\
// 8618d23e
// keywords: decompose
// output: a grid of tiles

// how wide the growth is
.type Growth =
      // one width
      Iso {{}}
      // @deviation: -0 +0 ~0
      // per-axis widths
    | Aniso {{}}

// how the offset is computed
.type Choice =
      // derived from a growth
      Derive {{ g: Growth }}
      // @deviation: -0 +0 ~0
      // a stored table
    | Disp {{}}

.comp Params {{
    // --- {marker} ---
    .decl sep(g: number) sep(1).
}}
"""


def test_a_marker_fixing_a_field_of_a_constructor_stays_quiet():
    assert of(RECORD_MARKED.format(marker="Derive(g=Iso)"), "case marker") == []



# ---------- the lib include ----------

def test_an_include_in_the_solver_fires():
    src = """\
// 74dd1130
// keywords: decompose
// output: a grid of tiles
#include "../lib.dl"
"""
    assert of(src, "include") == [(4, "the build adds the lib; drop the include")]
