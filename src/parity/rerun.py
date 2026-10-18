"""One Souffle case run again on one pair with every relation of its
program written out, each by its arclog name, so that a mismatch report can
give the first relation whose rows differ."""

from collections.abc import Mapping

from cli.common import LIMITS, engine, solver_path
from engine import Engine, Program, RelationName, Rows, RunFailure, Scope
from engine.program import Qualifier, as_grid
from parity import case_name, name_map, relation_name
from solver.cases import cases as cases_of
from solver.load import load
from solver.outcome import Assignment
from solver.pair_runs import examples
from solver.solve import relations_at
from solver.undefined import Undefined


class NoSuchCase(LookupError):
    """No case of the solver has the arclog name asked for."""


class NoSuchPair(LookupError):
    """The solver's task has no pair of the name asked for."""


def every_relation(eng: Engine, program: Program) -> list[RelationName]:
    """Each relation of `program` a run can output, by its name from the
    top level: those declared there, then those each instance reaches, in
    declaration order; an `inline` relation has no rows of its own, and no
    run outputs it."""
    index = eng.index(program)
    kept = [r for r in program.relations if Qualifier.INLINE not in r.qualifiers]
    out = [RelationName((), r.name) for r in kept if not r.scope.components]

    def walk(scope: tuple[str, ...], prefix: tuple[str, ...], depth: int) -> None:
        if depth > len(program.components):
            return
        for inst in program.instances:
            if inst.scope.components != scope:
                continue
            comp = index.component(inst.component, Scope(scope))
            if comp is None:
                continue
            for c in index.chain(comp):
                inner = (*c.scope.components, c.name)
                out.extend(RelationName((*prefix, inst.name), r.name)
                           for r in kept if r.scope.components == inner)
                walk(inner, (*prefix, inst.name), depth + 1)

    walk((), (), 0)
    return list(dict.fromkeys(out))


def relations(stem: str, case: str, pair: str
              ) -> Mapping[str, Rows] | Undefined | RunFailure:
    """The rows of each relation of the program of the case of `stem` whose
    arclog name is `case` (`parity.case_name`), run on the input of the
    pair whose name is `pair` (`arc.task.pair_name`), each keyed by its arclog name
    (`parity.relation_name`); the case's undefined outcome or the run's
    failure where it gives no rows. Raises `NoSuchCase` and `NoSuchPair`."""
    eng = engine()
    solver = load(stem, eng, solver_path(stem))
    names = name_map(stem)
    every = cases_of(solver, eng, LIMITS)
    if not isinstance(every, tuple):
        return every
    chosen = next((c for c in every if case_name(solver, c, names) == case), None)
    if chosen is None:
        raise NoSuchCase(case)
    ex = next((ex for p, ex in examples(solver.given_task) if p.text == pair), None)
    if ex is None:
        raise NoSuchPair(pair)
    rels = every_relation(eng, solver.program)
    got = relations_at(eng, solver, chosen, as_grid(ex.input), rels, Assignment(()), LIMITS)
    if not isinstance(got, Mapping):
        return got
    return {relation_name(names, r): rows for r, rows in got.items()}

