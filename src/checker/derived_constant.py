"""The derived-constant survey: the program relations that read `in` and
hold the same tuples on every example."""

import random
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from checker.runs import Runs
from checker.variants import TimedOut, parallel
from checker.judged import is_timeout, no_result
from checker.finding import AtPair, RunKind
from engine import (
    DeclId,
    Grid,
    Program,
    RelationName,
    Resolved,
    RunFailure,
    Rows,
    Scope,
)
from engine.program import (
    Aggregate,
    AtomLiteral,
    BinaryTerm,
    BodyLiteral,
    Comparison,
    Component,
    ConstructorTerm,
    Disjunction,
    FunctorCall,
    IntrinsicCall,
    Qualifier,
    RecordTerm,
    Term,
    UnaryTerm,
)
from solver.model import Solver
from solver.solve import PairId, as_grid
from solver.vocabulary import INPUT, OUTPUT, RUN_RELATIONS

SKIP = frozenset(r.name for r in RUN_RELATIONS)
"""The run relations the survey never reads."""

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


def _term_atoms(term: Term) -> Iterator[AtomLiteral]:
    match term:
        case Aggregate(expr=expr, body=body):
            if expr is not None:
                yield from _term_atoms(expr)
            for lit in body:
                yield from _atoms(lit)
        case ConstructorTerm(args=args) | RecordTerm(args=args) \
                | IntrinsicCall(args=args) | FunctorCall(args=args):
            for a in args:
                yield from _term_atoms(a)
        case UnaryTerm(arg=arg):
            yield from _term_atoms(arg)
        case BinaryTerm(lhs=lhs, rhs=rhs):
            yield from _term_atoms(lhs)
            yield from _term_atoms(rhs)
        case _:
            pass


def _atoms(lit: BodyLiteral) -> Iterator[AtomLiteral]:
    """Every atom a body literal reads, in aggregates and disjunctions
    too."""
    match lit:
        case AtomLiteral(atom=atom):
            yield lit
            for a in atom.args:
                yield from _term_atoms(a)
        case Comparison(lhs=lhs, rhs=rhs):
            yield from _term_atoms(lhs)
            yield from _term_atoms(rhs)
        case Disjunction(branches=branches):
            for b in branches:
                for sub in b:
                    yield from _atoms(sub)
        case _:
            pass


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


def _chain(program: Program, comp: Component) -> list[Component]:
    """The component and the components it extends, nearest first."""
    out = [comp]
    while out[-1].base is not None:
        base = _find(program, out[-1].base, out[-1].scope)
        if base is None or base in out:
            break
        out.append(base)
    return out


def _find(program: Program, name: str, scope: Scope) -> Component | None:
    """The component `name` read in `scope`: the innermost one."""
    comps = scope.components
    for k in range(len(comps), -1, -1):
        for c in program.components:
            if c.name == name and c.scope.components == comps[:k]:
                return c
    return None


def candidates(solver: Solver, runs: Runs
               ) -> list[tuple[RelationName, DeclId]]:
    """The relations that read `in` by forward dataflow and feed `out` by
    backward dataflow, by every name that reaches them from the top level,
    one instance path per name: a relation off either path is stored or
    dead. An inline relation is left out."""
    program = solver.program
    index = runs.index
    top = Scope(())

    def decl(name: RelationName, scope: Scope) -> DeclId | None:
        got = index.resolve(name, scope)
        return got.declaration if isinstance(got, Resolved) else None

    forward: dict[DeclId, set[DeclId]] = {}
    backward: dict[DeclId, set[DeclId]] = {}
    for u in program.units:
        head = decl(u.head.relation, u.scope)
        if head is None or u.body is None:
            continue
        for lit in u.body:
            for a in _atoms(lit):
                body = decl(a.atom.relation, u.scope)
                if body is None:
                    continue
                forward.setdefault(body, set()).add(head)
                backward.setdefault(head, set()).add(body)
    start, end = decl(INPUT, top), decl(OUTPUT, top)
    if start is None or end is None:
        return []
    wanted = _reachable(forward, start) & _reachable(backward, end)
    by_id = {r.id: r for r in program.relations}
    names: list[tuple[RelationName, DeclId]] = []
    seen: set[str] = set()

    def add(name: RelationName, d: DeclId) -> None:
        r = by_id.get(d)
        if d not in wanted or r is None or Qualifier.INLINE in r.qualifiers \
                or name.text in seen:
            return
        seen.add(name.text)
        names.append((name, d))

    for r in program.relations:
        if not r.scope.components and r.name not in SKIP:
            add(RelationName((), r.name), r.id)

    def walk(path: tuple[str, ...], comp: Component,
             stack: frozenset[str]) -> None:
        if comp.name in stack:
            return
        chain = _chain(program, comp)
        for c in chain:
            for r in program.relations:
                if r.scope.components == _path(c):
                    add(RelationName(path, r.name), r.id)
        for c in chain:
            for inst in program.instances:
                if inst.scope.components == _path(c):
                    sub = _find(program, inst.component, Scope(_path(c)))
                    if sub is not None:
                        walk((*path, inst.name), sub, stack | {comp.name})

    for inst in program.instances:
        if not inst.scope.components:
            comp = _find(program, inst.component, top)
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
        palette = sorted({c for row in grid for c in row})
        out.append(tuple(tuple(rng.choice(palette) for _ in row)
                         for row in grid))
    first = grids[0]
    palette = sorted({c for row in first for c in row})
    height, width = len(first), len(first[0])
    out.append(tuple(tuple(rng.choice(palette)
                           for _ in range(max(1, width - 1)))
                     for _ in range(max(1, height + 1))))
    return out


def survey_derived_constant(solver: Solver, runs: Runs) -> ConstantResult:
    """The relations whose tuples are the same, and not empty, on every
    train and test input, less those that keep their tuples on the
    control grids too: a derived value that is one value over the task,
    the evidence `store` rests on (procedure.md:135). Where a control
    grid's run gives no result, no relation is left out."""
    engine, limits = runs.engine, runs.limits
    names = candidates(solver, runs)
    if not names:
        return NoCandidate()
    task = solver.task
    if task is None:
        return NoCandidate()
    examples = [(PairId("train", i), as_grid(e.input))
                for i, e in enumerate(task.train)] + [
        (PairId("test", i), as_grid(e.input))
        for i, e in enumerate(task.test)]
    outputs = [n for n, _ in names]

    def run(grid: Grid) -> Mapping[RelationName, Rows] | RunFailure:
        return runs.relations_on(grid, outputs)

    got = parallel(run, [g for _, g in examples])
    for (pair, _), r in zip(examples, got, strict=True):
        if not isinstance(r, Mapping) and not is_timeout(r):
            return ExampleFails(r)
    for (pair, _), r in zip(examples, got, strict=True):
        if not isinstance(r, Mapping):
            return TimedOut(no_result(r, RunKind.PAIR, None, AtPair(pair)))
    tuples = [r for r in got if isinstance(r, Mapping)]

    def rows(t: Mapping[RelationName, Rows], n: RelationName
             ) -> frozenset[object]:
        return frozenset(t.get(n, ()))

    constant = {n: rows(tuples[0], n) for n in outputs
                if rows(tuples[0], n)
                and all(rows(t, n) == rows(tuples[0], n) for t in tuples)}
    if not constant:
        return NoConstant(len(names))
    flagged = sorted(constant, key=lambda n: n.text)
    control_runs = parallel(lambda g: runs.relations_on(g, flagged),
                            controls([g for _, g in examples]))
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
                            tuple(first.get(paths[0], ())))
                   for paths in groups.values())
    return ConstantReport(consts, len(names), len(flagged) - len(kept),
                          unrun)
