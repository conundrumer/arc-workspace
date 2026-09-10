"""Deletion variants: every one the generator yields is parseable, and
what the report calls each one."""

from dl import deletions as deletions_mod
from dl.deletions import (
    BOUND_ENUMERATOR,
    CASE_COLUMN,
    NOOP_NOTE,
    UNEXERCISED_CASES,
    UNPROBED_CASE,
    _case_findings,
    _cases_agree,
    case_type,
    column_deletions,
    deletions,
    render_deletions,
)
from dl.dlparse import parse

DISJ_BINDING = """\
.comp Determine {
    .decl run(e: number, t: number, p0: number, d: number, p: number)
    run(E, T, P0, D, P2) :-
        ( start(E, T, P0), stroke_cell(E, T, P0), dir_elem(D), P = P0  // inked start
        ; run(E, T, P0, D, P)                                          // or grow the run
        ),
        step_delta(D, S), compose(P, S, P2), stroke_cell(E, T, P2).
}
"""

DISJ_NEGATION = """\
.comp Determine {
    .decl drew(e: number, t: number, d: number, k: number, p: number)
    drew(E, T, D, K, P) :-
        run_len(E, T, D, K, P),
        ( parse.next_glyph(E, T, T2),                     // the successor stroke
          params.advance(Da), step_delta(Da, S), compose(P, S, P2),
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
        # has no syntactic form and is skipped. `dir_elem(D)` enumerates a
        # variable `step_delta(D, S)` carries.
        "rule", "atom", "atom", BOUND_ENUMERATOR, *["atom"] * 3,
        "disjunct", "disjunct",
    ]


def test_disjunct_with_negation():
    assert kinds(DISJ_NEGATION, determine=True) == [
        "rule", "negation", *["atom"] * 9, "disjunct", "disjunct",
    ]


def test_sole_negation_in_disjunct_is_skipped():
    assert kinds(SOLE_NEGATION) == ["rule", "atom", "disjunct", "disjunct"]


GUARD = """\
.decl steps(b: number, n: number)
steps(B, N) :- handle_dir(B, _), advance.low(B, N).
"""

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


def test_positive_guard_atom_is_enumerated():
    assert atoms(GUARD) == ["handle_dir(B, _)", "advance.low(B, N)"]


def test_comparison_is_not_an_atom():
    assert atoms(COMPARISONS) == ["from_mark(Id, K)"]


def test_constructor_in_an_argument_list_is_not_an_atom():
    assert atoms(CONSTRUCTOR) == ["parse.border($U(), P)", "in(P, Col)"]


def test_negated_atom_stays_under_its_own_kind():
    assert kinds(CONSTRUCTOR) == ["rule", "negation", "atom", "atom"]


def test_a_body_finding_names_the_head_of_its_rule():
    """A body deletion reports the atom and the rule it came from, and
    the renderer quotes each of the two."""
    texts = [text for _, kind, text, _ in deletions(CONSTRUCTOR)]
    assert texts == [
        "edge(P)",
        "!params.bg(Col)` in `edge(P)",
        "parse.border($U(), P)` in `edge(P)",
        "in(P, Col)` in `edge(P)",
    ]
    disjuncts = [
        text for _, kind, text, _ in deletions(SOLE_NEGATION) if kind == "disjunct"
    ]
    assert disjuncts == ["ink(P)` in `out(P)", "!ink(P)` in `out(P)"]
    lines = render_deletions("7c66cb00", (9, [(24, "atom", texts[3])]))
    assert "  7c66cb00.dl:24: atom `in(P, Col)` in `edge(P)`" in lines


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
    variable, and the report keeps the finding apart from the guard note."""
    assert kinds(ENUMERATORS) == [
        "rule", "atom", BOUND_ENUMERATOR, "atom",
        "rule", "atom", "atom",
        "rule", "negation", "atom", "atom",
    ]
    lines = render_deletions("s", (23, [(2, BOUND_ENUMERATOR, "dir_elem(D)")]))
    assert lines[0] == "1/23 deletions remove an enumerator over a bound variable:"
    assert "  s.dl:2: bound enumerator `dir_elem(D)`" in lines
    body = " ".join(lines)
    assert "not a claim" in body
    assert "the pairs never instantiate" not in body
    assert "every deletion changes the result" not in body


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

PLAIN_SOLVER = """\
.decl trail_cell(p: Position, col: Color)
trail_cell(P, Col) :- in(P, Col).

.decl out(p: Position, col: Color)
out(P, Col) :- trail_cell(P, Col).
"""


def test_case_type_is_outs_choice_adt():
    assert case_type(CHOICE_SOLVER) == "Choice"


def test_case_type_absent_without_an_adt_column():
    assert case_type(PLAIN_SOLVER) is None


def test_column_kinds_name_the_case_column():
    kinds = {
        text: kind for _, kind, text, _ in column_deletions(CHOICE_SOLVER)
    }
    assert kinds["trail_cell.ch"] == CASE_COLUMN
    assert kinds["trail_cell.p"] == "column"


def test_column_kinds_are_plain_without_cases():
    kinds = {kind for _, kind, _, _ in column_deletions(PLAIN_SOLVER)}
    assert kinds == {"column"}


class _Ex:
    alt = None
    input = [[0]]


def test_unexercised_cases_report_without_a_case_column():
    """The reading follows the solver's Choice type, not a column
    deletion, and the agreement check runs only where it decides."""
    hypothesis = (1, UNEXERCISED_CASES, "Choice")
    assert _case_findings(CHOICE_SOLVER, [], lambda: True) == [hypothesis]
    assert _case_findings(CHOICE_SOLVER, [], lambda: False) == []
    assert _case_findings(PLAIN_SOLVER, [], lambda: 1 / 0) == []
    column = (9, CASE_COLUMN, "trail_cell.ch")
    assert _case_findings(CHOICE_SOLVER, [column], lambda: True) == [column]
    lines = render_deletions("s", (23, [hypothesis]))
    assert lines[0] == "every deletion changes the result (23 tested)"
    assert "the pairs do not exercise the coverage hypothesis:" in lines
    assert "  s.dl:1: unexercised cases `Choice`" in lines
    body = " ".join(" ".join(lines).split())
    assert "every case emits an accepted grid on every pair" in body
    assert "every passing multi-case solver" in body
    assert "settle nothing about the cases" in body
    assert "constructed witness" not in body


def test_cases_agree_reads_the_reference_profile():
    examples = [_Ex(), _Ex()]
    two = [frozenset({"$Corner", "$Quadrant"}), frozenset({"$Corner", "$Quadrant"})]
    assert _cases_agree(CHOICE_SOLVER, examples, two)
    one = [frozenset({"$Corner"}), frozenset({"$Corner", "$Quadrant"})]
    assert not _cases_agree(CHOICE_SOLVER, examples, one)


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


def test_ungrounds_is_false_on_other_failures(monkeypatch):
    def raiser(*_args, **_kwargs):
        raise RuntimeError("souffle exited 1:\nError: Type clash")

    monkeypatch.setattr(deletions_mod, "_run_source", raiser)
    monkeypatch.setattr(deletions_mod, "build_source", lambda src: src)
    monkeypatch.setattr(deletions_mod, "grid_to_facts", lambda rows: "")
    assert not deletions_mod._ungrounds(CHOICE_SOLVER, _Ex())


def test_render_case_column_is_not_dead_code():
    lines = render_deletions("s", (23, [(53, CASE_COLUMN, "trail_cell.ch")]))
    assert lines[0] == "1/23 deletions change nothing:"
    assert "  s.dl:53: case column `trail_cell.ch`" in lines
    body = " ".join(lines)
    assert "coverage hypothesis" in body
    assert "not dead code" in body


def test_render_plain_column_carries_only_the_legend():
    lines = render_deletions("s", (23, [(53, "column", "trail_cell.p")]))
    assert lines == [
        "1/23 deletions change nothing:",
        *NOOP_NOTE,
        "  s.dl:53: column `trail_cell.p`",
    ]


def test_render_legend_states_the_measurement_and_leaves_the_reading_open():
    """The no-op note reports what the probe measured, names both
    readings so the session judges which one holds, and states the scope
    of a column drop."""
    lines = render_deletions("s", (40, [(12, "atom", "handle_dir(B, _)")]))
    assert lines[0] == "1/40 deletions change nothing:"
    assert "  s.dl:12: atom `handle_dir(B, _)`" in lines
    body = " ".join(" ".join(lines).split())
    assert "changed no pair's output and no determined value" in body
    assert "the pairs never instantiate" in body
    assert "another atom already implies" in body
    assert "the session judges which" in body
    assert "every atom of the relation" in body
    assert "unbound at the consumers" in body


def test_render_legend_is_absent_when_nothing_survives():
    lines = render_deletions("s", (40, []))
    assert lines == ["every deletion changes the result (40 tested)"]


def test_render_unprobed_case_column_stands_apart():
    lines = render_deletions("s", (22, [(45, UNPROBED_CASE, "stamp.ch")]))
    assert lines[0] == "every deletion changes the result (22 tested)"
    assert "1 case column the probe cannot judge:" in lines
    assert "  s.dl:45: unprobed case column `stamp.ch`" in lines
    body = " ".join(" ".join(lines).split())
    assert "says nothing about the cases" in body
    assert "case emits an accepted grid on every pair" in body
    assert "every passing multi-case solver" in body
    assert "coverage" not in body


def test_render_baseline_failure():
    assert render_deletions("s", None) == [
        "baseline fails: stored source does not pass train+test"
    ]
