"""Matching a shape signature with the parser: the worked example.

A shape signature names an operation with no stable lexical anchor: the
relation names vary per solver, and the operation lives in rule
structure. Grep misses those sites; a survey matches them with a script
under its scratch path, over the parsed corpus:

    from cli.common import all_stems
    from solver.model import load
    from souffle import SouffleEngine

    engine = SouffleEngine()
    for stem in all_stems():
        program = load(stem, engine).program
        ...

`program.units` holds every rule and fact of the solver and of the lib it
includes: a unit's `head` atom and its `body` literals (None for a fact),
each an `AtomLiteral` (an `atom` and whether it is `negated`), a
`Comparison`, a `Disjunction` of conjunctions, or a `BoolLiteral`. An
atom's `relation` is the name as the statement writes it: a read through
a comp instance (`wall.ray(...)`) is `RelationName(("wall",), "ray")`, so
a matcher for a lib comp's relation tests `relation.name` and
`relation.instances`. A unit's `span` gives its lines and its file: None
for the solver's own units, the included file's path for the lib's. For
the node types, read `src/engine/program.py`.

The test below matches the Unanimous shape: one relation twice positive
in a rule, with a disequality between the two bindings of one argument.
A match is a candidate, not a home: each hit is read in its rule, per
the survey procedure.
"""

from itertools import combinations
from pathlib import Path

from engine import Program
from engine.program import (
    AtomLiteral,
    Comparison,
    ComparisonOperator,
    RelationName,
    Unit,
    Variable,
)
from souffle import SouffleEngine


def unanimous_sites(units: tuple[Unit, ...]) -> list[tuple[int, str]]:
    """(line, relation) of each rule holding the Unanimous shape."""
    hits = []
    for unit in units:
        if unit.body is None:
            continue
        diseq = {
            frozenset((c.lhs.name, c.rhs.name))
            for c in unit.body
            if isinstance(c, Comparison) and c.op == ComparisonOperator.NE
            and isinstance(c.lhs, Variable) and isinstance(c.rhs, Variable)
        }
        by_relation: dict[RelationName, list] = {}
        for lit in unit.body:
            if isinstance(lit, AtomLiteral) and not lit.negated:
                by_relation.setdefault(lit.atom.relation, []).append(lit.atom)
        for relation, atoms in by_relation.items():
            for a1, a2 in combinations(atoms, 2):
                if len(a1.args) == len(a2.args) and any(
                    isinstance(x, Variable) and isinstance(y, Variable)
                    and frozenset((x.name, y.name)) in diseq
                    for x, y in zip(a1.args, a2.args)
                ):
                    hits.append((unit.head.line, relation.text))
    return hits


FIXTURE = """\
.decl item(k: number, v: number)
.decl other(k: number, v: number)
.decl clash(k: number)
clash(K) :- item(K, V1), item(K, V2), V1 != V2.
.decl pair(k: number, a: number, b: number)
pair(K, A, B) :- item(K, A), item(K, B).
.decl diff(a: number, b: number)
diff(A, B) :- item(_, A), other(_, B), A != B.
"""


def test_unanimous_shape_match(tmp_path: Path):
    """The planted site is the only hit: `pair` repeats the relation with
    no disequality, and `diff`'s disequality spans two relations."""
    program = SouffleEngine(functor_dir=None, cache_dir=None).parse(
        FIXTURE, tmp_path)
    assert isinstance(program, Program), program
    assert unanimous_sites(program.units) == [(4, "item")]
