"""The Determine run and what it reads."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from engine import (
    Engine,
    InputValue,
    Limits,
    Program,
    RelationName,
    Row,
    Rows,
    RunFailure,
    Tuples,
    UnitId,
    Value,
)
from engine.program import POSE_COLUMN, Atom, RigidCall, Unit, body_atoms
from engine.quotes import quotes
from solver.aggregate import Solver, has_determine
from solver.cycles import cyclic_components
from solver.graph import InstancePath
from solver.model import Parameter, StoredGrid
from solver.probe import example_inputs
from solver.readers import instance_of, parameter, row_value
from solver.value_order import row_key
from solver.variant_limits import over_examples, variant_limits
from solver.vocabulary import (
    DETERMINE,
    DETERMINE_SCOPE,
    IDENT,
    INPUT,
    PARAMS,
    PARAMS_SCOPE,
)


@dataclass(frozen=True)
class ParamDiff:
    """Where a determined parameter's value differs from its stored one."""

    parameter: str
    stored_only: Rows
    determined_only: Rows
    rigid: bool
    """The parameter is stored by a RIGID call: no D4 image of its block's
    stored assembly gives the determined one, and the rows are placed
    rows (`determine`)."""


@dataclass(frozen=True)
class CycleRead:
    """A read in a circular determination: the determination of
    `parameter` reads the stored value of `reads`, at the atom on `line` of
    `unit`."""

    parameter: str
    reads: str
    unit: UnitId
    line: int


@quotes("solver-file.md", "Determination",
        "`Determine` contains the determination as one relation per "
        "determined parameter, with the parameter's name and schema")
@dataclass(frozen=True)
class Determined:
    """The `Determine` component's run against the stored values: the diffs,
    the parameters it reproduces, and its cycles."""

    diffs: tuple[ParamDiff, ...]
    reproduced: tuple[str, ...]
    cycles: tuple[tuple[CycleRead, ...], ...]
    """Each group of determined parameters whose determinations read each
    other's stored values: every read inside the group, by parameter and
    the parameter it reads."""
    cpu_seconds: float
    """The CPU seconds of the runs it took, none where no parameter is
    determined."""


@dataclass(frozen=True)
class NoDetermine:
    """The solver has no `Determine` comp."""


type DetermineResult = Determined | NoDetermine | RunFailure


@dataclass(frozen=True)
class DetermineInstance:
    """The instance of the `Determine` comp that a solver's runs run."""

    name: str
    added: bool
    """No `.init` of the solver's text makes the instance, and a run adds
    it."""

    @property
    def path(self) -> InstancePath:
        return (self.name,)


@dataclass(frozen=True)
class RunProgram:
    """The program a solver's runs run, and its `Determine` instance: None
    where the solver has no `Determine` comp."""

    program: Program
    determine: DetermineInstance | None


def run_program(solver: Solver) -> RunProgram:
    """The solver's program with an instance of its `Determine` comp where
    no `.init` instantiates it, the one comp a run of a solver
    instantiates that no `.init` does."""
    program = solver.program
    if not has_determine(solver):
        return RunProgram(program, None)
    inst = instance_of(program, DETERMINE)
    if inst is not None:
        return RunProgram(program, DetermineInstance(inst.name, False))
    name = "determine"
    return RunProgram(solver.engine.instantiate(program, DETERMINE, name),
                      DetermineInstance(name, True))


def determine(engine: Engine, solver: Solver, limits: Limits,
              measured: float | None = None) -> DetermineResult:
    """The Determine comp over the examples, diffed against the stored values
    (solver-file.md, under "Determination"). The parameters with an `Ident`
    column compare together modulo a renaming of ids (solver-file.md, under
    "Determination"), one a RIGID call stores by the orbit of its placed rows
    at each id (`_signatures`). The other parameters a RIGID call stores
    compare together per block, up to a D4 image of the stored assembly, since
    a RIGID block exposes them only as D4 placements that transform them
    together and the stored pose is unobservable (patterns.md, under "`RIGID` —
    parameter relations coupled as a rigid assembly"): the Determine relations
    stand in for the block's charts, the program places them, and the
    parameters agree where some pose of one side gives the rows of every
    parameter of the block that the other side gives at some pose
    (`_same_pose_orbits`). A diff of such a parameter holds its placed rows.
    The runs take `limits` once per example; a variant's runs, where the
    solver's own determination spent `measured` CPU seconds, take
    `variant_limits` of those. A solver whose task has no task file is a
    caller's error: `ValueError`."""
    run = run_program(solver)
    if run.determine is None:
        return NoDetermine()
    program, det_name = run.program, run.determine.name
    task = solver.task
    if task is None:
        raise ValueError("a determination runs over the task's examples, "
                         "and the solver's task has no task file")
    params_inst = instance_of(program, PARAMS)
    determined = [p for p in solver.params.parameters if p.determined]
    if params_inst is None or not determined:
        return Determined((), (), (), 0.0)
    outputs: list[RelationName] = []
    for p in determined:
        outputs += [RelationName((det_name,), p.name),
                    parameter(solver, p.name)]
    inputs: dict[RelationName, InputValue] = {INPUT: (),
                                              **example_inputs(task)}
    each = over_examples(limits, task)
    if measured is not None:
        each = variant_limits(each, measured)
    got = engine.run(program, inputs, outputs, each)
    if not isinstance(got, Tuples):
        return got
    spent = got.cpu_seconds
    stored = {p.name: got.relations[parameter(solver, p.name)]
              for p in determined}
    derived = {p.name: got.relations[RelationName((det_name,), p.name)]
               for p in determined}
    rigid = rigid_parameters(solver)
    ident_cols = {p.name: [c.type.text for c in p.columns].index(IDENT)
                  for p in determined
                  if IDENT in [c.type.text for c in p.columns]}
    charts = _charts(solver, [p.name for p in determined if p.name in rigid])
    if charts:
        placed = program
        for name, chart in charts.items():
            placed = engine.fix_relation(
                placed, parameter(solver, chart),
                derived[name])
        again = engine.run(placed, inputs, [
            parameter(solver, n) for n in charts], each)
        if not isinstance(again, Tuples):
            return again
        spent += again.cpu_seconds
        for name in charts:
            derived[name] = again.relations[
                parameter(solver, name)]
    placed_ids = frozenset(n for n in charts if n in ident_cols)
    ids_agree = _signatures(stored, ident_cols, placed_ids) \
        == _signatures(derived, ident_cols, placed_ids)
    posed = _same_pose_orbits(
        solver, {n: c for n, c in charts.items() if n not in ident_cols},
        stored, derived)
    diffs: list[ParamDiff] = []
    reproduced: list[str] = []
    for p in determined:
        s, d = set(stored[p.name]), set(derived[p.name])
        if p.name in ident_cols and ids_agree or s == d \
                or p.name in posed:
            reproduced.append(p.name)
            continue
        diffs.append(ParamDiff(
            p.name, tuple(r for r in stored[p.name] if r not in d),
            tuple(r for r in derived[p.name] if r not in s),
            p.name in rigid))
    return Determined(tuple(diffs), tuple(reproduced),
                      cycles(solver, params_inst.name,
                             [p.name for p in determined]), spent)


def stored_facts(engine: Engine, solver: Solver, p: Parameter) -> list[Row]:
    """The parameter's stored facts, a GRID call's cells among them."""
    if not isinstance(p.stored, StoredGrid):
        return list(p.stored)
    expanded = engine.expand(solver.program)
    out: list[Row] = []
    for u in expanded.units:
        if u.scope == PARAMS_SCOPE and u.body is None \
                and u.head.relation == RelationName((), p.name):
            row = row_value(u.head.args, solver.lib.constants)
            if row is None:
                raise ValueError(f"a fact of `{p.name}` the GRID expansion "
                                 "wrote states no constant")
            out.append(row)
    return out


def rigid_parameters(solver: Solver) -> frozenset[str]:
    """The parameters a RIGID call in `Params` stores: the relations that
    are a RIGID chart, the names a call binds, and the relations its units
    feed."""
    scope = PARAMS_SCOPE
    heads = {u.id: u.head.relation for u in solver.program.units}
    out: set[str] = set()
    for m in solver.program.macros:
        if isinstance(m, RigidCall) and m.scope == scope:
            out |= set(solver.program.bound_names(m))
            out |= {heads[u].name for u in m.body
                    if u in heads and not heads[u].instances}
    return frozenset(out)


def _blocks(solver: Solver) -> dict[str, tuple[str, str]]:
    """Each relation a RIGID call in `Params` binds, with its block and the
    chart relation the call declares for it: the block's charts in the
    order the call binds its relations. A call whose charts are not one
    per name is left out, and is a fault of `load`
    (`model.instance_faults`)."""
    scope = PARAMS_SCOPE
    out: dict[str, tuple[str, str]] = {}
    for m in solver.program.macros:
        if not isinstance(m, RigidCall) or m.scope != scope:
            continue
        for name, chart in solver.program.bound_charts(m) or ():
            out[name] = (m.block, chart.name)
    return out


def rigid_charts(solver: Solver) -> dict[str, str]:
    """Each relation a RIGID call in `Params` binds, with the chart
    relation that holds its facts (`_blocks`)."""
    return {n: chart for n, (_block, chart) in _blocks(solver).items()}


def _charts(solver: Solver, names: Sequence[str]) -> dict[str, str]:
    """The chart relation of each of `names` that a RIGID call binds."""
    blocks = _blocks(solver)
    return {n: blocks[n][1] for n in names if n in blocks}


def _same_pose_orbits(solver: Solver, charts: Mapping[str, str],
                      stored: Mapping[str, Rows], derived: Mapping[str, Rows]
                      ) -> frozenset[str]:
    """The parameters of `charts` whose block agrees up to pose: the set of
    the block's placed row sets per pose, the pose left out, is one set on
    both sides, so each side is a D4 image of the other."""
    blocks = _blocks(solver)
    by_block: dict[str, list[str]] = {}
    for name in charts:
        by_block.setdefault(blocks[name][0], []).append(name)

    def orbit(rows: Mapping[str, Rows], names: Sequence[str]
              ) -> frozenset[tuple[tuple[Row, ...], ...]]:
        poses: dict[Value, list[set[Row]]] = {}
        for k, name in enumerate(names):
            for row in rows.get(name, ()):
                poses.setdefault(row[POSE_COLUMN], [set() for _ in names])[k].add(
                    tuple(v for i, v in enumerate(row) if i != POSE_COLUMN))
        return frozenset(
            tuple(tuple(sorted(rs, key=row_key)) for rs in sets)
            for sets in poses.values())

    out: set[str] = set()
    for names in by_block.values():
        if orbit(stored, names) == orbit(derived, names):
            out |= set(names)
    return frozenset(out)


type _Key = tuple[object, ...]


def _signatures(rows_by_param: Mapping[str, Rows],
                ident_cols: Mapping[str, int],
                placed: frozenset[str]) -> list[tuple[_Key, ...]]:
    """Each id's rows across the parameters, the id left out, as a sorted
    multiset: two sides with equal signatures differ by a renaming of ids
    alone. A parameter of `placed`, stored by a RIGID call, holds placed rows,
    and each id's assembly is its own: its part of the id's signature is the
    orbit of its placed rows at the id, the set over the poses of its rows at
    the pose, so that the id's assembly in any pose gives the same part
    (patterns.md, under "`RIGID` — parameter relations coupled as a rigid
    assembly")."""
    by_id: dict[Value, list[_Key]] = {}
    for name, col in ident_cols.items():
        if name not in placed:
            for row in rows_by_param.get(name, ()):
                rest = tuple(v for i, v in enumerate(row) if i != col)
                by_id.setdefault(row[col], []).append((name, row_key(rest)))
            continue
        poses: dict[Value, dict[Value, set[_Key]]] = {}
        for row in rows_by_param.get(name, ()):
            rest = tuple(v for i, v in enumerate(row)
                         if i not in (POSE_COLUMN, col))
            poses.setdefault(row[col], {}).setdefault(row[POSE_COLUMN], set()).add(
                row_key(rest))
        for id_, at in poses.items():
            orbit = sorted({tuple(sorted(rows)) for rows in at.values()})
            by_id.setdefault(id_, []).append((name, tuple(orbit)))
    return sorted(tuple(sorted(rows)) for rows in by_id.values())


def cycles(solver: Solver, params_instance: str,
           determined: Sequence[str]) -> tuple[tuple[CycleRead, ...], ...]:
    """The determined parameters whose determinations read each other's
    stored values, through the `Determine` relations between: for each
    group of them that reads around, a parameter that reads its own stored
    value included, every read inside the group, each at the first atom by
    line where it happens, in name order."""
    scope = DETERMINE_SCOPE
    feeds: dict[RelationName, list[tuple[Unit, Atom]]] = {}
    for u in solver.program.units:
        if u.scope != scope or u.body is None:
            continue
        reads = feeds.setdefault(u.head.relation, [])
        reads += [(u, a) for a, _negated in body_atoms(u.body)]

    def local(rel: RelationName) -> list[RelationName]:
        if rel.instances and rel.instances[0] != params_instance:
            return [h for h in feeds if h.instances[:1] == rel.instances[:1]]
        return [rel] if rel in feeds else []

    wanted = set(determined)
    edges: dict[str, dict[str, tuple[UnitId, int]]] = {}
    for p in determined:
        seen: set[RelationName] = set()
        stack = [RelationName((), p)]
        found: dict[str, tuple[UnitId, int]] = {}
        while stack:
            rel = stack.pop()
            if rel in seen:
                continue
            seen.add(rel)
            for u, atom in feeds.get(rel, ()):
                read = atom.relation
                if read.instances == (params_instance,) and read.name in wanted:
                    if read.name not in found \
                            or atom.line < found[read.name][1]:
                        found[read.name] = (u.id, atom.line)
                else:
                    stack += local(read)
        edges[p] = found
    groups = [sorted(c) for c in cyclic_components(
        sorted(determined), lambda v: sorted(edges.get(v, {})))]
    out = [tuple(CycleRead(p, q, *edges[p][q]) for p in group
                 for q in sorted(edges[p]) if q in group)
           for group in groups]
    return tuple(sorted(out, key=lambda c: [(r.parameter, r.reads)
                                            for r in c]))
