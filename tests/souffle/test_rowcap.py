"""A capped output holds all its rows when it has at most its cap. Every
`autoinc` of a run draws from one counter, so a cap read from the counter
alone would drop the rows of a relation numbered after a large one, with
no sign in the tool's output."""

from pathlib import Path

from engine import Limits, Program, RelationName, Tuples
from souffle import SouffleEngine

LIMITS = Limits(5, 20)


def test_a_relation_under_its_cap_keeps_every_row_after_one_over_it():
    engine = SouffleEngine(cache_dir=None)
    program = engine.parse(
        ".comp C<T> { .type P = [a: T, b: symbol] .decl r(p: P) }\n"
        ".init c = C<number>\n"
        ".decl n(x: number)\nn(0).\nn(x + 1) :- n(x), x < 29.\n"
        ".decl big(x: number, y: number)\nbig(x, y) :- n(x), n(y).\n"
        'c.r([x, "s"]) :- n(x), x < 5.\n', Path("."))
    assert isinstance(program, Program), program
    big, small = RelationName((), "big"), RelationName(("c",), "r")
    got = engine.run(program, {}, [big, small], LIMITS, {big: 10, small: 10})
    assert isinstance(got, Tuples), got
    assert len(got.relations[big]) == 11
    assert len(got.relations[small]) == 5
