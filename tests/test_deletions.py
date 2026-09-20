"""Deletion variants: every one the generator yields is parseable, and the
kind each one takes."""

from dl import deletions as deletions_mod
from dl.deletions import (
    BOUND_ENUMERATOR,
    case_type,
    deletions,
)
from dl.dlparse import parse

DISJ_BINDING = """\
.comp Determine {
    .decl run(e: number, t: number, p0: number, d: number, p: number)
    run(E, T, P0, D, P2) :-
        ( start(E, T, P0), stroke_cell(E, T, P0), dir_elem(D), P = P0  // inked start
        ; run(E, T, P0, D, P)                                          // or grow the run
        ),
        step_offset(D, S), compose(P, S, P2), stroke_cell(E, T, P2).
}
"""

DISJ_NEGATION = """\
.comp Determine {
    .decl drew(e: number, t: number, d: number, k: number, p: number)
    drew(E, T, D, K, P) :-
        run_len(E, T, D, K, P),
        ( parse.next_glyph(E, T, T2),                     // the successor stroke
          params.advance(Da), step_offset(Da, S), compose(P, S, P2),
          stroke_cell(E, T2, P2)                          // can start at this end
        ; parse.last_glyph(E, T),                         // no successor
          step_offset(D, S), compose(P, S, P2),
          !stroke_cell(E, T, P2)                          // the run is maximal
        ).
}
"""

SOLE_NEGATION = """\
.decl out(p: number)
out(P) :- cell(P), ( ink(P) ; !ink(P) ).
"""


def kinds(source: str, determine: bool = False) -> list[str]:
    out: list[str] = []
    for _, kind, _, mod in deletions(source, determine=determine):
        parse(mod)  # every variant stays in the dialect
        out.append(kind)
    return out


def atoms(source: str, determine: bool = False) -> list[str]:
    """The deleted atoms alone, with the head each finding names dropped."""
    return [
        text.split("` in `")[0]
        for _, kind, text, _ in deletions(source, determine=determine)
        if kind == "atom"
    ]


def test_disjunct_with_binding():
    assert kinds(DISJ_BINDING, determine=True) == [
        # `run(...)` is the whole of the second branch, so its deletion
        # has no syntactic form and is skipped. `step_offset` carries the
        # variable of `dir_elem(D)` at a Dir8 column, so that atom narrows
        # the binding and stands as an atom.
        "rule", *["atom"] * 6, "disjunct", "disjunct",
    ]


def test_disjunct_with_negation():
    assert kinds(DISJ_NEGATION, determine=True) == [
        "rule", "negation", *["atom"] * 9, "disjunct", "disjunct",
    ]


def test_sole_negation_in_disjunct_is_skipped():
    assert kinds(SOLE_NEGATION) == ["rule", "atom", "disjunct", "disjunct"]


COMPARISONS = """\
.decl near(id: Ident, k: number)
near(Id, K) :- from_mark(Id, K), K < 3, K != 0, K = max(0, K).
"""

CONSTRUCTOR = """\
.decl edge(p: Position)
edge(P) :- parse.border($U(), P), in(P, Col), !params.bg(Col).
"""

AGGREGATE = """\
.decl extent(n: number)
extent(N) :- dist_set(_), N = count : { dist_set(K) }.
"""


def test_comparison_is_not_an_atom():
    assert atoms(COMPARISONS) == ["from_mark(Id, K)"]


def test_constructor_in_an_argument_list_is_not_an_atom():
    assert atoms(CONSTRUCTOR) == ["parse.border($U(), P)", "in(P, Col)"]


def test_aggregate_body_is_not_top_level():
    assert atoms(AGGREGATE) == ["dist_set(_)"]


ENUMERATORS = """\
.decl cast(col: Color, d: Dir)
cast(Col, D) :- mark(Col, P), dir_elem(D), dist_pair(P, D, K, K2), K < K2.

.decl width(d: Dir, k: number)
width(D, K) :- dir_elem(D), params.line_width(K).

.decl tile_line(a: Axis, p_axis: Position)
tile_line(A, P_axis) :- axis_elem(A), !split(P_axis, A, _, _), in(P_axis, _).
"""


def test_an_enumerator_over_a_bound_variable_stands_apart_from_the_atoms():
    """Only a positive atom of the same rule binds the enumerator's
    variable."""
    assert kinds(ENUMERATORS) == [
        "rule", "atom", BOUND_ENUMERATOR, "atom",
        "rule", "atom", "atom",
        "rule", "negation", "atom", "atom",
    ]


NARROWING = """\
.decl near(p: Position, d: Dir)
near(P, D) :- in(P, _), dir_elem(D), neighbor(P, D, Q), in(Q, _).
"""


def test_an_enumerator_over_a_wider_column_is_a_plain_atom():
    """`neighbor` carries the variable at a Dir8 column, so `dir_elem(D)`
    narrows the binding rather than reading it out: a claim, and its
    deletion is an atom deletion."""
    assert kinds(NARROWING) == ["rule", *["atom"] * 4]


CHOICE_SOLVER = """\
.type Choice = Corner {} | Quadrant {}

.decl impl_choice(ch: Choice)
impl_choice($Corner()). impl_choice($Quadrant()).

.decl trail(col: Color)
trail(Col) :- in(P, Col).

.decl trail_cell(p: Position, ch: Choice)
trail_cell(P, Ch) :- in(P, _), impl_choice(Ch).

.decl out(p: Position, col: Color, ch: Choice)
out(P, Col, Ch) :- trail_cell(P, Ch), trail(Col).
"""


def test_case_type_is_outs_choice_adt():
    assert case_type(CHOICE_SOLVER) == "Choice"


class _Ex:
    alt = None
    input = [[0]]


UNGROUNDED = """\
Warning: No rules/facts defined for relation ex_in in file lib.dl at line 99
Error: Ungrounded variable Ch in file .tmp1234.dl at line 67
1 errors generated, evaluation aborted
"""


def test_ungrounds_reads_souffles_error(monkeypatch):
    def raiser(*_args, **_kwargs):
        raise RuntimeError(f"souffle exited 1:\n{UNGROUNDED}")

    monkeypatch.setattr(deletions_mod, "_run_source", raiser)
    monkeypatch.setattr(deletions_mod, "build_source", lambda src: src)
    monkeypatch.setattr(deletions_mod, "grid_to_facts", lambda rows: "")
    assert deletions_mod._ungrounds(CHOICE_SOLVER, _Ex())


