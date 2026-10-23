"""The grounding check on a program that Souffle refuses."""

from pathlib import Path

from engine import Program
from souffle import SouffleEngine
from souffle.grounding import ungrounded

SOLVERS = Path(__file__).resolve().parents[2] / "programs" / "solvers"


def test_atom_of_another_arity_than_an_inline_declaration_raises_nothing():
    text = (
        ".decl t(a: number, b: number) inline\n"
        "t(A, B) :- A = 1, B = 2.\n"
        ".decl t(a: number)\n"
        "t(1).\n"
        ".decl r(a: number)\n"
        "r(A) :- t(A).\n")
    program = SouffleEngine(cache_dir=None).parse(text, SOLVERS)
    assert isinstance(program, Program), program
    assert ungrounded(program) is None
