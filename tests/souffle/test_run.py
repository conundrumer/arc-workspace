"""Runs of real solvers: the values Souffle prints read back by column
type, the line a rejected program's error stands on, and a relation fixed
in one instance of a shared component. Each can go wrong with no sign in
the tool's output."""

from pathlib import Path

import pytest

from arc.task import load
from engine import (
    AdtValue,
    Engine,
    GridInput,
    InputValue,
    Limits,
    Program,
    RecordValue,
    RelationName,
    RemoveAtom,
    RemoveColumn,
    Tuples,
    UngroundedVariable,
)
from souffle import SouffleEngine

SOLVERS = Path(__file__).resolve().parents[2] / "programs" / "solvers"
LIMITS = Limits(5, 20)
IN = RelationName((), "in")
OUT = RelationName((), "out")


@pytest.fixture(scope="module")
def engine() -> Engine:
    return SouffleEngine(cache_dir=None)


def _parsed(engine: Engine, text: str) -> Program:
    program = engine.parse(text, SOLVERS)
    assert isinstance(program, Program), program
    return program


def _solver(engine: Engine, stem: str) -> tuple[str, Program, dict[RelationName, InputValue]]:
    text = (SOLVERS / f"{stem}.dl").read_text()
    program = _parsed(engine, '#include "../lib.dl"\n#line 1\n' + text)
    grid = GridInput(tuple(tuple(row) for row in load(stem).train[0].input))
    return text, program, {IN: grid}


def test_printed_values_read_as_their_column_types(engine: Engine):
    program = _parsed(engine, (
        ".type C = A {} | B {x: number, y: symbol}\n.type R = [p: number, q: C]\n"
        ".decl r(c: C, r: R, s: symbol)\n"
        'r($A(), [1, $B(2, "h i")], "p=").\nr($B(3, "=="), [-1, $A()], "").\n'))
    rel = RelationName((), "r")
    result = engine.run(program, {}, [rel], LIMITS)
    assert isinstance(result, Tuples)
    assert set(result.relations[rel]) == {
        (AdtValue("A", ()), RecordValue((1, AdtValue("B", (2, "h i")))), "p="),
        (AdtValue("B", (3, "==")), RecordValue((-1, AdtValue("A", ()))), ""),
    }


def test_an_error_stands_at_the_file_line_of_the_rule(engine: Engine):
    text, program, inputs = _solver(engine, "9edfc990")
    unit = next(u for u in program.units
                if u.span is not None and u.span.file is None and u.head.relation.name == "node")
    assert unit.span is not None
    assert text.splitlines()[unit.span.first - 1].startswith("flood.node(")
    result = engine.run(engine.remove(program, RemoveAtom(unit.id, (0,))), inputs, [OUT],
                        LIMITS)
    assert isinstance(result, UngroundedVariable)
    assert result.line == unit.span.first


def test_an_ungrounded_record_is_an_ungrounded_variable(engine: Engine):
    text, program, inputs = _solver(engine, "1caeab9d")
    group = next(r for r in program.relations if r.name == "group" and r.span.file is None)
    reader = next(u for u in program.units
                  if u.span is not None and u.span.file is None
                  and u.head.relation == RelationName(("bbox",), "cell"))
    assert reader.span is not None
    assert text.splitlines()[reader.span.first - 1].startswith("bbox.cell([Ch, Id], P)")
    removed = engine.remove(program, RemoveColumn(group.id, 0))
    result = engine.run(removed, inputs, [OUT], LIMITS)
    assert result == UngroundedVariable("Ch", reader.span.first)


def test_an_argument_an_aggregate_grounds_used_outside_it_is_ungrounded(engine: Engine):
    program = _parsed(engine, (".decl p(x: number)\np(1).\n.decl a(n: number, x: number)\n"
                               "a(N, X) :- N = count : { p(X) }.\n"))
    result = engine.run(program, {}, [RelationName((), "a")], LIMITS)
    assert result == UngroundedVariable("X", 4)


def test_a_fixed_relation_of_one_instance_leaves_the_others(engine: Engine):
    _, program, inputs = _solver(engine, "103eff5b")
    key, shape = RelationName(("key_box",), "box"), RelationName(("shape_box",), "box")
    before = engine.run(program, inputs, [key, shape, OUT], LIMITS)
    assert isinstance(before, Tuples)
    value = ((AdtValue("U", ()), RecordValue((0, 0, 0, 0))),)
    after = engine.run(engine.fix_relation(program, key, value), inputs, [key, shape, OUT],
                       LIMITS)
    assert isinstance(after, Tuples)
    assert after.relations[key] == value
    assert after.relations[shape] == before.relations[shape]
