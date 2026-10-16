"""A run of the engine: the values Souffle prints read back by column
type, which can go wrong with no sign in the tool's output."""

from pathlib import Path

import pytest

from engine import (
    AdtValue,
    Engine,
    Limits,
    Program,
    RecordValue,
    RelationName,
    Tuples,
)
from souffle import SouffleEngine

SOLVERS = Path(__file__).resolve().parents[2] / "programs" / "solvers"
LIMITS = Limits(5, 20)


@pytest.fixture(scope="module")
def engine() -> Engine:
    return SouffleEngine(cache_dir=None)


def _parsed(engine: Engine, text: str) -> Program:
    program = engine.parse(text, SOLVERS)
    assert isinstance(program, Program), program
    return program


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
