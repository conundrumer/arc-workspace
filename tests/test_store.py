"""Stored cases: the rows a merged finding holds, a stored-case run
that fails, a stored relation read inside a comp, the solver's reads of a
relation a lib rule also reads, and the `@ignore: derive` and
`@ignore: store` lines."""

import pytest

from dl.facts import grid_to_facts, parse_output
from dl.souffle import _run_source
from dl.annotations import Ignore, ignore_lines
from dl.store import (
    OWNED,
    Found,
    _case_program,
    _index,
    _merge,
    _rename_reads,
    _stored_run,
)


def _found(case: str, facts: tuple) -> Found:
    return Found(rel="inner", cols=["p"], keys=[], types=["Position"],
                 sub=False, kind=OWNED, case=case, concept=case == "Rect",
                 read=True, ref=frozenset({frozenset({"[1, 1, 1, 1]"})}),
                 facts=facts)


def test_merged_cases_keep_the_rows_of_every_case():
    # One value under two cases: the stored case reads its rows at each.
    enclose = _found("Enclose", (("[1, 1, 1, 1]", "$Enclose"),))
    rect = _found("Rect", (("[1, 1, 1, 1]", "$Rect"),))
    (merged,) = _merge([enclose, rect])
    assert merged.case == "Enclose, Rect"
    assert set(merged.facts) == {("[1, 1, 1, 1]", "$Enclose"),
                                 ("[1, 1, 1, 1]", "$Rect")}


def test_a_failed_stored_case_run_raises_and_is_not_undefined():
    built = ".decl out(p: number)\nout(X) :- missing_rel(X).\n"
    with pytest.raises(RuntimeError):
        _stored_run(built, [[0]], None)


def test_a_stored_relation_of_a_comp_reaches_the_comp_readers():
    # The stored axis is 2, and only axis 1 reaches `out`: a case whose
    # comp rules still derive and read the relation gives the input back.
    source = (
        ".decl out(p: Position, col: Color)\n"
        ".comp Parse {\n"
        "    .decl pick(a: number, p: Position)\n"
        "    pick(1, P) :- in(P, _).\n"
        "    .decl shown(p: Position)\n"
        "    shown(P) :- pick(1, P).\n"
        "}\n"
        ".init parse = Parse\n"
        "out(P, C) :- parse.shown(P), in(P, C).\n")
    found = Found(rel="parse.pick", cols=["a"], keys=["p"], types=["number"],
                  sub=True, kind=OWNED, case="", concept=True, read=True,
                  ref=frozenset({frozenset({("2",)})}))
    built = _case_program(source, found)
    assert built is not None
    got = parse_output(_run_source(built, grid_to_facts([[3]])))
    assert all(not c.grid for c in got)


def test_the_solver_reads_the_twin_where_a_lib_rule_reads_the_relation():
    # `Extremes` reads `low` in its own clause: the solver's read still
    # takes the twin, and the lib's clause keeps reading `low`.
    source = (
        ".decl out(p: Position, col: Color)\n"
        ".init smallest = Extremes<number>\n"
        "smallest.cand(0, C) :- in(_, C).\n"
        "out(P, C) :- in(P, C), smallest.low(0, C).\n")
    built = _rename_reads(source, _index(source), "smallest.low", "twin")
    assert "out(P, C) :- in(P, C), twin(0, C)." in built
    assert "smallest.low" not in built


def test_the_ignore_lines_read_their_name_site_and_line():
    # A misread line excludes the wrong case with no sign in the output.
    source = "\n".join([
        "    // @derive RarestColor: variant derived",
        "    // @ignore: derive A & B \u2014 r",
        "    // @ignore: derive [A, B(C)] \u2014 r",
        "    .decl p(c: Color)",
        "// @ignore: derive \u2014 r",
        ".decl q(c: Color)",
        "// @ignore: store A & B \u2014 r",
        ".decl s(c: Color)",
        "// @ignore rank: store Alt \u2014 r",
        ".init scan = LexOrder<Scan>",
        "// @ignore: store \u2014 r",
        ".decl t(c: Color)",
    ])
    assert ignore_lines(source) == (
        Ignore("derive", "", "A & B", 2, "p", 1),
        Ignore("derive", "", "[A, B(C)]", 3, "p", 1),
        Ignore("derive", "", "", 5, "q"),
        Ignore("store", "", "A & B", 7, "s"),
        Ignore("store", "rank", "Alt", 9, "scan.rank"),
        Ignore("store", "", "", 11, "t"),
    )
