"""The derived-constant survey: the program relations that read `in` and
hold the same tuples on every example."""

import random
from collections.abc import Mapping
from dataclasses import dataclass

from checker.domains import colors
from checker.finding import AtPair, RunKind
from checker.judged import is_timeout
from checker.runs import Runs
from checker.variants import TimedOut, timed_out
from engine import (
    DeclId,
    Grid,
    RelationName,
    Rows,
    RunFailure,
    Scope,
)
from engine.engine import resolved
from engine.program import (
    Component,
    Qualifier,
    body_atoms,
)
from engine.quotes import quotes
from solver.model import TOP, Solver
from solver.solve import as_grid, at_once, examples
from solver.vocabulary import INPUT, OUTPUT, RUN_RELATIONS

CONTROL_SEED = 7
"""The seed of the control grids, so a rerun reports the same
relations."""


@dataclass(frozen=True)
class Constant:
    """One constant relation, under every instance path that carries it
    with the same tuples."""

    paths: tuple[RelationName, ...]
    rows: Rows


@dataclass(frozen=True)
class ControlRun:
    """A control grid's run that gave no result: its index and failure."""

    index: int
    failure: RunFailure


@dataclass(frozen=True)
class ConstantReport:
    """The constant relations; how many relations the survey ran; how
    many the control grids left out; each control grid whose run gave no
    result, which leaves every constant standing."""

    constants: tuple[Constant, ...]
    tested: int
    dropped: int
    unrun: tuple[ControlRun, ...]


@dataclass(frozen=True)
class NoCandidate:
    """No relation both reads `in` and feeds `out`."""


@dataclass(frozen=True)
class NoConstant:
    """No relation of the `tested` holds one value over the examples."""

    tested: int


@dataclass(frozen=True)
class ExampleFails:
    """The stored program's run fails on an example."""

    failure: RunFailure


type ConstantResult = (ConstantReport | NoCandidate | NoConstant
                       | ExampleFails | TimedOut)


def _reachable(edges: dict[DeclId, set[DeclId]], start: DeclId
               ) -> set[DeclId]:
    seen = {start}
    work = [start]
    while work:
        for nxt in edges.get(work.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                work.append(nxt)
    return seen


def _path(c: Component) -> tuple[str, ...]:
    return (*c.scope.components, c.name)


def candidates(solver: Solver, runs: Runs
               ) -> list[tuple[RelationName, DeclId]]:
    """The relations that read `in` by forward dataflow and feed `out` by
    backward dataflow, by every name that reaches them from the top level,
    one instance path per name: a relation off either path is stored or
    dead. An inline relation is left out. The program compiles, so every
    atom resolves (`engine.engine.resolved`); the command refuses one that
    does not."""
    program = solver.program
    index = runs.index

    def decl(name: RelationName, scope: Scope) -> DeclId:
        return resolved(index, name, scope).declaration

    forward: dict[DeclId, set[DeclId]] = {}
    backward: dict[DeclId, set[DeclId]] = {}
    for u in program.units:
        if u.body is None:
            continue
        head = decl(u.head.relation, u.scope)
        for a, _negated in body_atoms(u.body):
            body = decl(a.relation, u.scope)
            forward.setdefault(body, set()).add(head)
            backward.setdefault(head, set()).add(body)
    start, end = decl(INPUT, TOP), decl(OUTPUT, TOP)
    wanted = _reachable(forward, start) & _reachable(backward, end)
    names: list[tuple[RelationName, DeclId]] = []
    seen: set[str] = set()

    def add(name: RelationName, d: DeclId) -> None:
        r = program.relation(d)
        if d not in wanted or r is None or Qualifier.INLINE in r.qualifiers \
                or name.text in seen:
            return
        seen.add(name.text)
        names.append((name, d))

    for r in program.relations:
        if not r.scope.components \
                and r.scoped_name not in RUN_RELATIONS:
            add(r.scoped_name, r.id)

    def walk(path: tuple[str, ...], comp: Component,
             stack: frozenset[str]) -> None:
        if comp.name in stack:
            return
        chain = index.chain(comp)
        for c in chain:
            for r in program.relations:
                if r.scope.components == _path(c):
                    add(RelationName(path, r.name), r.id)
        for c in chain:
            for inst in program.instances:
                if inst.scope.components == _path(c):
                    sub = index.component(inst.component, inst.scope)
                    if sub is not None:
                        walk((*path, inst.name), sub, stack | {comp.name})

    for inst in program.instances:
        if not inst.scope.components:
            comp = index.component(inst.component, TOP)
            if comp is not None:
                walk((inst.name,), comp, frozenset())
    return names


def controls(grids: list[Grid]) -> list[Grid]:
    """Control grids: each example's extent with its cells redrawn from
    its own palette, and one grid of a changed extent. A relation that
    reads the input moves when the input does; one that holds its tuples
    over these reads something else."""
    rng = random.Random(CONTROL_SEED)
    out: list[Grid] = []
    for grid in grids:
        palette = sorted(colors([grid]))
        out.append(tuple(tuple(rng.choice(palette) for _ in row)
                         for row in grid))
    first = grids[0]
    palette = sorted(colors([first]))
    height, width = len(first), len(first[0])
    out.append(tuple(tuple(rng.choice(palette)
                           for _ in range(max(1, width - 1)))
                     for _ in range(max(1, height + 1))))
    return out


@quotes("procedure.md", "Develop",
        "`uv run python scripts/run_dl.py store <task_id>` lists the derived "
        "values that are the same on every input.")
def survey_derived_constant(solver: Solver, runs: Runs) -> ConstantResult:
    """The relations whose tuples are the same, and not empty, on every
    train and test input, less those that keep their tuples on the
    control grids too: a derived value that is one value over the task,
    the evidence `store` rests on. Where a control grid's run gives no
    result, no relation is left out. A solver with no task file raises
    `ValueError`; the command refuses it first."""
    task = solver.given_task
    names = candidates(solver, runs)
    if not names:
        return NoCandidate()
    inputs = [(pair, as_grid(e.input)) for pair, e in examples(task)]
    outputs = [n for n, _ in names]

    def run(grid: Grid) -> Mapping[RelationName, Rows] | RunFailure:
        return runs.defined_relations(grid, outputs)

    got = at_once(run, [g for _, g in inputs])
    for (pair, _), r in zip(inputs, got, strict=True):
        if not isinstance(r, Mapping) and not is_timeout(r):
            return ExampleFails(r)
    for (pair, _), r in zip(inputs, got, strict=True):
        if not isinstance(r, Mapping):
            return timed_out(r, RunKind.PAIR, AtPair(pair))
    tuples = [r for r in got if isinstance(r, Mapping)]

    def rows(t: Mapping[RelationName, Rows], n: RelationName
             ) -> frozenset[object]:
        return frozenset(t[n])

    constant = {n: rows(tuples[0], n) for n in outputs
                if rows(tuples[0], n)
                and all(rows(t, n) == rows(tuples[0], n) for t in tuples)}
    if not constant:
        return NoConstant(len(names))
    flagged = sorted(constant, key=lambda n: n.text)
    control_runs = at_once(lambda g: runs.defined_relations(g, flagged),
                            controls([g for _, g in inputs]))
    unrun = tuple(ControlRun(i, r) for i, r in enumerate(control_runs)
                  if not isinstance(r, Mapping))
    moved: set[RelationName] = set()
    for r in control_runs:
        if isinstance(r, Mapping):
            moved |= {n for n in flagged if rows(r, n) != constant[n]}
    kept = [n for n in flagged if unrun or n in moved]
    first = tuples[0]
    groups: dict[tuple[str, frozenset[object]], list[RelationName]] = {}
    for n in kept:
        groups.setdefault((n.name, constant[n]), []).append(n)
    consts = tuple(Constant(tuple(sorted(paths, key=lambda p: p.text)),
                            tuple(first[paths[0]]))
                   for paths in groups.values())
    return ConstantReport(consts, len(names), len(flagged) - len(kept),
                          unrun)
