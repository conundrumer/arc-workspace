"""The Determine run and what it reads."""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from arc.task import Example, Task
from engine import (
    Engine,
    InputValue,
    Limits,
    Program,
    RelationName,
    Row,
    Rows,
    RunFailure,
    RunResult,
    Tuples,
    UnitId,
    Value,
)
from engine.engine import resolved
from engine.program import POSE_COLUMN, Column, RelationDecl, RigidCall
from engine.quotes import quotes
from solver.aggregate import TOP, Solver, has_determine
from solver.cycles import cyclic_components
from solver.graph import Graph, InstancePath, Node, NodeKind
from solver.model import Parameter
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
        "`Determine` contains the determination's clauses as one relation "
        "per parameter whose value they give, with the parameter's name and "
        "schema")
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
class NotRun:
    """A determination result under which the determination does not run,
    so no determined value is checked."""


@dataclass(frozen=True)
class NoDetermine(NotRun):
    """The solver has no `Determine` comp."""


@dataclass(frozen=True)
class KeysOff(NotRun):
    """The determination relations of each of `blocks`, RIGID blocks, do
    not lead with the same key columns (`off_key_blocks`), so no copy of a
    block's assembly is known and the determination does not run."""

    blocks: tuple[str, ...]


type DetermineResult = Determined | NoDetermine | KeysOff | RunFailure


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
              measured: float | None = None,
              added: Sequence[Example] = ()) -> DetermineResult:
    """The Determine comp over the examples, diffed against the stored values
    (docs/handbook/solver-file.md#determination). The parameters with an
    `Ident` column compare together modulo a renaming of ids
    (docs/handbook/solver-file.md#determination), one a RIGID call stores by
    the orbit of its placed rows at each id (`_signatures`). The other
    parameters a RIGID call stores compare together per block, up to a D4 image
    of the stored assembly, since a RIGID block exposes them only as D4
    placements that transform them together and the stored pose is unobservable
    (docs/handbook/patterns.md#rigid-a-stored-shape-and-its-attached-parts-in-every-orientation):
    the Determine relations stand in for the block's charts, the program places
    them, and the parameters agree where some pose of one side gives the rows
    of every parameter of the block that the other side gives at some pose
    (`_same_pose_orbits`). A block whose Determine relations lead with key
    columns gives one copy of the assembly per key, each placed and compared on
    its own (`_compare_copies`). A diff of such a parameter holds its placed
    rows.
    The runs take `limits` once per example; a variant's runs, where the
    solver's own determination spent `measured` CPU seconds, take
    `variant_limits` of those. A solver whose task has no task file is a
    caller's error: `ValueError`.
    Each pair of `added` joins the train examples, after the task's own and
    before the test inputs."""
    run = run_program(solver)
    if run.determine is None:
        return NoDetermine()
    program, det_name = run.program, run.determine.name
    task = solver.task
    if task is None:
        raise ValueError("a determination runs over the task's examples, "
                         "and the solver's task has no task file")
    task = Task([*task.train, *added], task.test)
    params_inst = instance_of(program, PARAMS)
    determined = [p for p in solver.params.parameters if p.determined]
    if params_inst is None or not determined:
        return Determined((), (), (), 0.0)
    off = off_key_blocks(solver)
    if off:
        return KeysOff(off)
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
    keys = block_key_columns(solver)
    blocks = rigid_blocks(solver)
    widths = {n: len(keys[blocks[n]][n]) for n in charts}
    keyed = {n: c for n, c in charts.items() if widths[n]}
    whole = {n: c for n, c in charts.items() if not widths[n]}
    if whole:
        again = _place(engine, solver, program, inputs, each, whole, derived)
        if not isinstance(again, Tuples):
            return again
        spent += again.cpu_seconds
        for name in whole:
            derived[name] = again.relations[parameter(solver, name)]
    rest = {n: c for n, c in ident_cols.items() if n not in keyed}
    placed_ids = frozenset(n for n in whole if n in ident_cols)
    ids_agree = _signatures(stored, rest, placed_ids) \
        == _signatures(derived, rest, placed_ids)
    posed = _same_pose_orbits(
        solver, {n: c for n, c in whole.items() if n not in ident_cols},
        stored, derived)
    diffs: list[ParamDiff] = []
    reproduced: list[str] = []
    copied = _copies(solver, keyed, widths, derived)
    for block in copied.values():
        got_block = _compare_copies(engine, solver, program, inputs, each,
                                    block, stored, ident_cols)
        if not isinstance(got_block, _Compared):
            return got_block
        spent += got_block.cpu_seconds
        diffs += got_block.diffs
        reproduced += got_block.reproduced
    for p in determined:
        if p.name in keyed:
            continue
        if _reproduces(p.name, stored[p.name], derived[p.name], ident_cols,
                       ids_agree, posed):
            reproduced.append(p.name)
            continue
        diffs.append(_diff(p.name, stored[p.name], derived[p.name],
                           p.name in rigid))
    order = [p.name for p in determined]
    diffs.sort(key=lambda d: order.index(d.parameter))
    reproduced.sort(key=order.index)
    return Determined(tuple(diffs), tuple(reproduced),
                      cycles(Graph(program, engine), params_inst.name,
                             det_name, [p.name for p in determined]), spent)


class ProgramFacts:
    """The facts of each parameter in `solver.program`: read from the
    program `engine.expand` gives, by the declaration `params.<name>`
    resolves to from the top level, so that a GRID call's cells and the
    top-level facts `engine.fix_relation` writes count."""

    def __init__(self, engine: Engine, solver: Solver) -> None:
        self.solver = solver
        expanded = engine.expand(solver.program)
        self.index = engine.index(expanded)
        self.units = {u.id: u for u in expanded.units}

    def of(self, p: Parameter) -> list[Row]:
        decl = resolved(self.index, parameter(self.solver, p.name),
                        TOP).declaration
        out: list[Row] = []
        for o in self.index.feeding(decl):
            u = self.units[o.unit]
            if u.body is not None:
                continue
            row = row_value(u.head.args, self.solver.lib.constants)
            if row is None:
                raise ValueError(f"a fact of `{p.name}` states no constant")
            out.append(row)
        return out


def stored_facts(engine: Engine, solver: Solver, p: Parameter) -> list[Row]:
    """The parameter's facts in `solver.program` (`ProgramFacts`)."""
    return ProgramFacts(engine, solver).of(p)


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


def rigid_blocks(solver: Solver) -> dict[str, str]:
    """Each relation a RIGID call in `Params` binds, with its block
    (`_blocks`)."""
    return {n: block for n, (block, _chart) in _blocks(solver).items()}


def rigid_charts(solver: Solver) -> dict[str, str]:
    """Each relation a RIGID call in `Params` binds, with the chart
    relation that holds its facts (`_blocks`)."""
    return {n: chart for n, (_block, chart) in _blocks(solver).items()}


def _charts(solver: Solver, names: Sequence[str]) -> dict[str, str]:
    """The chart relation of each of `names` that a RIGID call binds."""
    blocks = _blocks(solver)
    return {n: blocks[n][1] for n in names if n in blocks}


def determine_columns(p: Parameter, rigid: frozenset[str]
                      ) -> tuple[Column, ...]:
    """The columns of `p`'s determination relation after its key columns:
    its own, the pose column of a parameter of `rigid` left out, since the
    determination writes such a parameter's chart in a pose of its own
    (docs/handbook/patterns.md#rigid-a-stored-shape-and-its-attached-parts-in-every-orientation)."""
    return tuple(c for i, c in enumerate(p.columns)
                 if p.name not in rigid or i != POSE_COLUMN)


def determine_relation(solver: Solver, name: str) -> RelationDecl | None:
    """The relation `Determine` declares under `name`, None where it
    declares none."""
    return next((d for d in solver.program.relations
                 if d.scope == DETERMINE_SCOPE and d.name == name), None)


def key_width(d: RelationDecl, p: Parameter, rigid: frozenset[str]) -> int:
    """The number of key columns that lead `d`, the relation of `Determine`
    that gives `p`: the columns before as many as `determine_columns`
    gives, for a parameter of `rigid`, and none for any other; negative
    where `d` has too few columns
    (docs/handbook/solver-file.md#determination)."""
    if p.name not in rigid:
        return 0
    return len(d.columns) - len(determine_columns(p, rigid))


def column_signature(columns: tuple[Column, ...]
                     ) -> tuple[tuple[str, str], ...]:
    return tuple((c.name, c.type.text) for c in columns)


def block_key_columns(solver: Solver
                      ) -> dict[str, dict[str, tuple[Column, ...]]]:
    """Each RIGID block's relations of `Determine`, with the key columns
    that lead each (`key_width`)."""
    rigid = rigid_parameters(solver)
    blocks = rigid_blocks(solver)
    params = {p.name: p for p in solver.params.parameters}
    out: dict[str, dict[str, tuple[Column, ...]]] = {}
    for d in solver.program.relations:
        if d.scope != DETERMINE_SCOPE or d.name not in blocks \
                or d.name not in params:
            continue
        width = key_width(d, params[d.name], rigid)
        out.setdefault(blocks[d.name], {})[d.name] = d.columns[:max(0, width)]
    return out


def off_key_blocks(solver: Solver) -> tuple[str, ...]:
    """The RIGID blocks whose relations of `Determine` do not lead with the
    same key columns, by name and type (`block_key_columns`), in name
    order."""
    return tuple(sorted(
        block for block, keys in block_key_columns(solver).items()
        if len({column_signature(k) for k in keys.values()}) > 1))


type _Copy = dict[str, Rows]


def _copies(solver: Solver, keyed: Mapping[str, str],
            widths: Mapping[str, int], derived: Mapping[str, Rows]
            ) -> dict[str, list[_Copy]]:
    """The copies of the assembly each block of `keyed` determines, in key
    order, copies with equal rows once: the rows of the block's relations
    at one key, the key columns left out. A block with no row gives one
    copy with no rows, which compares as an empty relation does."""
    blocks = _blocks(solver)
    by_block: dict[str, list[str]] = {}
    for name in keyed:
        by_block.setdefault(blocks[name][0], []).append(name)
    out: dict[str, list[_Copy]] = {}
    for block, names in by_block.items():
        at: dict[tuple[object, ...], dict[str, list[Row]]] = {}
        for name in names:
            w = widths[name]
            for row in derived[name]:
                at.setdefault(row_key(row[:w]), {n: [] for n in names})[
                    name].append(row[w:])
        copies: list[_Copy] = []
        for key in sorted(at):
            copy = {n: tuple(sorted(rows, key=row_key))
                    for n, rows in at[key].items()}
            if copy not in copies:
                copies.append(copy)
        out[block] = copies or [{n: () for n in names}]
    return out


@dataclass(frozen=True)
class _Compared:
    """The parameters of a block whose copies are compared, and the CPU
    seconds of the runs that placed them."""

    diffs: tuple[ParamDiff, ...]
    reproduced: tuple[str, ...]
    cpu_seconds: float


def _place(engine: Engine, solver: Solver, program: Program,
           inputs: Mapping[RelationName, InputValue], limits: Limits,
           charts: Mapping[str, str], rows: Mapping[str, Rows]
           ) -> RunResult:
    """The placed rows of each of `charts`, where each chart holds the rows
    `rows` gives for its parameter."""
    placed = program
    for name, chart in charts.items():
        placed = engine.fix_relation(placed, parameter(solver, chart),
                                     rows[name])
    return engine.run(placed, inputs, [parameter(solver, n) for n in charts],
                      limits)


def _reproduces(name: str, stored: Rows, placed: Rows, ids: Collection[str],
                ids_agree: bool, posed: Collection[str]) -> bool:
    """Whether the determination reproduces `name`'s stored rows: as an
    id-keyed chart of `ids` whose ids agree up to renaming, as one of
    `posed` whose block agrees up to pose, or with equal rows."""
    return name in ids and ids_agree or name in posed \
        or set(stored) == set(placed)


def _compare_copies(engine: Engine, solver: Solver, program: Program,
                    inputs: Mapping[RelationName, InputValue],
                    limits: Limits, copies: Sequence[_Copy],
                    stored: Mapping[str, Rows], ident_cols: Mapping[str, int]
                    ) -> _Compared | RunFailure:
    """Each copy of a block's assembly placed and compared with the stored
    assembly, up to pose, and per id with id renaming for an id-keyed chart:
    the block is reproduced where every copy agrees and each stored id's
    signature is that of an id of some copy. The runs stop at the first copy
    that does not agree, whose placed rows its diffs hold."""
    names = list(copies[0])
    charts = _charts(solver, names)
    ids = {n: c for n, c in ident_cols.items() if n in charts}
    placed_ids = frozenset(ids)
    poseable = {n: c for n, c in charts.items() if n not in ids}
    want = _id_signatures(stored, ids, placed_ids)
    seen: set[tuple[_Key, ...]] = set()
    spent = 0.0
    for copy in copies:
        again = _place(engine, solver, program, inputs, limits, charts, copy)
        if not isinstance(again, Tuples):
            return again
        spent += again.cpu_seconds
        placed = {n: again.relations[parameter(solver, n)] for n in names}
        mine = set(_id_signatures(placed, ids, placed_ids).values())
        ids_agree = mine <= set(want.values())
        posed = _same_pose_orbits(solver, poseable, stored, placed)
        bad = [n for n in names
               if not _reproduces(n, stored[n], placed[n], ids, ids_agree,
                                  posed)]
        if bad:
            return _Compared(
                tuple(_diff(n, stored[n], placed[n], True) for n in bad),
                tuple(n for n in names if n not in bad), spent)
        seen |= mine
    unseen = {id_ for id_, sig in want.items() if sig not in seen}
    bad = [n for n in ids if any(r[ids[n]] in unseen for r in stored[n])]
    return _Compared(
        tuple(ParamDiff(n, tuple(r for r in stored[n]
                                 if r[ids[n]] in unseen), (), True)
              for n in bad),
        tuple(n for n in names if n not in bad), spent)


def _diff(name: str, stored: Rows, derived: Rows, rigid: bool
          ) -> ParamDiff:
    """The rows each side holds that the other does not."""
    s, d = set(stored), set(derived)
    return ParamDiff(name, tuple(r for r in stored if r not in d),
                     tuple(r for r in derived if r not in s), rigid)


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
    """The sorted signatures of `_id_signatures`."""
    return sorted(_id_signatures(rows_by_param, ident_cols, placed).values())


def _id_signatures(rows_by_param: Mapping[str, Rows],
                   ident_cols: Mapping[str, int],
                   placed: frozenset[str]
                   ) -> dict[Value, tuple[_Key, ...]]:
    """Each id's rows across the parameters, the id left out, as a sorted
    multiset: two sides with equal signatures differ by a renaming of ids
    alone. The parameters of `placed`, stored by a RIGID call, hold placed
    rows, and each id's assembly is its own: its part of the id's signature
    is one orbit over all of those parameters, the set over the poses of the
    id's rows of every such parameter at the pose, so that the id's assembly
    in any pose gives the same part, and the parameters agree on one joint
    pose
    (docs/handbook/patterns.md#rigid-a-stored-shape-and-its-attached-parts-in-every-orientation)."""
    by_id: dict[Value, list[_Key]] = {}
    names = sorted(n for n in ident_cols if n in placed)
    joint: dict[Value, dict[Value, list[set[_Key]]]] = {}
    for name, col in ident_cols.items():
        if name not in placed:
            for row in rows_by_param.get(name, ()):
                rest = tuple(v for i, v in enumerate(row) if i != col)
                by_id.setdefault(row[col], []).append((name, row_key(rest)))
            continue
        for row in rows_by_param.get(name, ()):
            rest = tuple(v for i, v in enumerate(row)
                         if i not in (POSE_COLUMN, col))
            poses = joint.setdefault(row[col], {}).setdefault(
                row[POSE_COLUMN], [set() for _ in names])
            poses[names.index(name)].add(row_key(rest))
    for id_, at in joint.items():
        orbit = sorted({tuple(tuple(sorted(rows)) for rows in sets)
                        for sets in at.values()})
        by_id.setdefault(id_, []).append(("+".join(names), tuple(orbit)))
    return {id_: tuple(sorted(rows)) for id_, rows in by_id.items()}


def cycles(graph: Graph, params_instance: str, determine_instance: str,
           determined: Sequence[str]) -> tuple[tuple[CycleRead, ...], ...]:
    """The determined parameters whose determinations read each other's
    stored values: for each group of them that reads around, a parameter
    that reads its own stored value included, every read inside the group,
    each at the first atom by line where it happens, in name order. The walk
    from a parameter's `Determine` relation follows each relation the units
    that head it read, at the instance paths they run at, the relations
    `Params` derives and those of the instances nested in `Determine`
    among them, and stops at the stored value of a determined parameter."""
    wanted = set(determined)
    edges: dict[str, dict[str, tuple[UnitId, int]]] = {}
    for p in determined:
        seen: set[Node] = set()
        stack = [Node(NodeKind.RELATION, (determine_instance,), p)]
        found: dict[str, tuple[UnitId, int]] = {}
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            for placed in graph.heading(node):
                for atom, read, _name in graph.body(placed):
                    if read.path == (params_instance,) \
                            and read.name in wanted:
                        if read.name not in found \
                                or atom.line < found[read.name][1]:
                            found[read.name] = (placed[0].id, atom.line)
                    else:
                        stack.append(read)
        edges[p] = found
    groups = [sorted(c) for c in cyclic_components(
        sorted(determined), lambda v: sorted(edges.get(v, {})))]
    out = [tuple(CycleRead(p, q, *edges[p][q]) for p in group
                 for q in sorted(edges[p]) if q in group)
           for group in groups]
    return tuple(sorted(out, key=lambda c: [(r.parameter, r.reads)
                                            for r in c]))
