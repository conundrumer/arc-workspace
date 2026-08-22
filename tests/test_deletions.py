"""Deletion variants: every one the generator yields is parseable."""

from dl.deletions import deletions
from dl.dlparse import parse

DISJ_BINDING = """\
.comp Fit {
    .decl run(e: number, t: number, p0: number, d: number, p: number)
    run(E, T, P0, D, P2) :-
        ( start(E, T, P0), stroke_cell(E, T, P0), dir_elem(D), P = P0  // inked start
        ; run(E, T, P0, D, P)                                          // or grow the run
        ),
        step_delta(D, S), compose(P, S, P2), stroke_cell(E, T, P2).
}
"""

DISJ_NEGATION = """\
.comp Fit {
    .decl drew(e: number, t: number, d: number, k: number, p: number)
    drew(E, T, D, K, P) :-
        run_len(E, T, D, K, P),
        ( parse.next_glyph(E, T, T2),                     // the successor stroke
          c.advance(Da), step_delta(Da, S), compose(P, S, P2),
          stroke_cell(E, T2, P2)                          // can start at this end
        ; parse.last_glyph(E, T),                         // no successor
          step_delta(D, S), compose(P, S, P2),
          !stroke_cell(E, T, P2)                          // the run is maximal
        ).
}
"""

SOLE_NEGATION = """\
.decl out(p: number)
out(P) :- cell(P), ( ink(P) ; !ink(P) ).
"""


def kinds(source: str, fit: bool = False) -> list[str]:
    out: list[str] = []
    for _, kind, _, mod in deletions(source, fit=fit):
        parse(mod)  # every variant stays in the dialect
        out.append(kind)
    return out


def test_disjunct_with_binding():
    assert kinds(DISJ_BINDING, fit=True) == ["rule", "disjunct", "disjunct"]


def test_disjunct_with_negation():
    assert kinds(DISJ_NEGATION, fit=True) == [
        "rule", "negation", "disjunct", "disjunct",
    ]


def test_sole_negation_in_disjunct_is_skipped():
    assert kinds(SOLE_NEGATION) == ["rule", "disjunct", "disjunct"]
