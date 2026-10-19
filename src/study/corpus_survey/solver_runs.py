"""The rows of a Souffle solver's relations on the inputs of its task, by
the arclog names of `gen/` that the converter's name map
(`parity.name_map`) gives them, with each value as plain JSON."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from arc.task import Grid
from arc.task import load as load_task
from checker.runs import Runs
from cli.common import LIMITS, engine, solver_path
from engine import RelationName, Resolved, Scope
from engine.program import AdtValue, NilValue, Qualifier, RecordValue, as_grid
from parity import name_map
from solver.aggregate import Solver
from solver.load import load
from solver.outcome import Assignment
from souffle.parser import relation_name

CAP = 2_000_000
"""The rows of one relation past which a dump marks it over and holds no
more."""

type Plain = int | str | list["Plain"]


def plain(v: object) -> Plain:
    """A value as plain JSON: a constructor as `$Name` or `["$Name", args]`,
    a record as the list of its fields, `nil` as `$nil`."""
    if isinstance(v, AdtValue):
        return f"${v.constructor}" if not v.args else [f"${v.constructor}", *(plain(a) for a in v.args)]
    if isinstance(v, RecordValue):
        return [plain(a) for a in v.fields]
    if isinstance(v, NilValue):
        return "$nil"
    assert isinstance(v, (int, str))
    return v


@dataclass(frozen=True)
class Loaded:
    solver: Solver
    runs: Runs


def loaded(stem: str) -> Loaded:
    eng = engine()
    s = load(stem, eng, solver_path(stem))
    return Loaded(s, Runs(eng, s, LIMITS))


def columns(lo: Loaded, rel: RelationName) -> list[tuple[str, str]] | None:
    """The name and the type of each column of the relation `rel` names
    from the top level; None where it names none, or an `inline` relation,
    which has no rows of its own."""
    got = lo.runs.index.resolve(rel, Scope(()))
    if not isinstance(got, Resolved):
        return None
    d = lo.solver.program.relation(got.declaration)
    if d is None or Qualifier.INLINE in d.qualifiers:
        return None
    return [(c.name, c.type.name) for c in d.columns]


def arclog_relations(stem: str, lo: Loaded, read: set[str]) -> dict[str, tuple[RelationName, list[tuple[str, str]]]]:
    """Each arclog name of the solver's name map whose Souffle relation a
    top-level instance reaches, `&x` as `x`, with that relation and its
    columns; `in` for the input; and each name of `read` the map lacks, by
    the first Souffle name that resolves of: the name, the name under
    `params`, the name with one `_` as a `.`, the name under a top-level
    instance."""
    found: dict[str, tuple[RelationName, list[tuple[str, str]]]] = {}
    names = name_map(stem)
    pairs = [("in", "in")] + ([] if names is None else
                              [(a.lstrip("&"), s.path) for a, ss in names.relations.items() for s in ss if s.path])
    for a, path in pairs:
        if a in found:
            continue
        rel = relation_name(path)
        cols = columns(lo, rel)
        if cols is not None:
            found[a] = (rel, cols)
    instances = [i.name for i in lo.solver.program.instances if not i.scope.components]
    for a in sorted(read - set(found)):
        for cand in [a, "params." + a, *(a[:i] + "." + a[i + 1:] for i, ch in enumerate(a) if ch == "_"),
                     *(f"{i}.{a}" for i in instances)]:
            rel = relation_name(cand)
            cols = columns(lo, rel)
            if cols is not None:
                found[a] = (rel, cols)
                break
    return found


def rows_on(lo: Loaded, grid: Grid, rels: Sequence[RelationName]) -> Mapping[RelationName, list[list[Plain]]] | str:
    """The rows of each of `rels` on `grid` at the stored assignment, up to
    `CAP` and one more; the name of what the run gave in their place
    where it gave none."""
    got = lo.runs.relations_on(as_grid(tuple(tuple(r) for r in grid)), list(rels), Assignment(()), cap=CAP)
    if not isinstance(got, Mapping):
        return type(got).__name__
    return {r: [[plain(x) for x in row] for row in got[r]] for r in rels}


def train_inputs(solver: Solver) -> dict[str, Grid]:
    """Train input 0 and the train input of the most cells, by index."""
    task = load_task(solver.task_id)
    areas = [len(ex.input) * len(ex.input[0]) for ex in task.train]
    return {str(i): task.train[i].input for i in sorted({0, max(range(len(areas)), key=lambda i: areas[i])})}


def dump(stem: str, read: set[str]) -> dict[str, Any]:
    """The rows on `train_inputs` of every relation of the name map and of
    `read` (`arclog_relations`), as the slow sections read them."""
    lo = loaded(stem)
    rels = arclog_relations(stem, lo, read)
    out: dict[str, Any] = {"stem": stem, "alias": {a: r.text for a, (r, _) in rels.items()},
                           "cols": {a: c for a, (_, c) in rels.items()}, "inputs": {}}
    for i, grid in train_inputs(lo.solver).items():
        got = rows_on(lo, grid, [r for r, _ in rels.values()])
        if isinstance(got, str):
            out["inputs"][i] = {"error": got}
            continue
        out["inputs"][i] = {"grid": grid, "rel": {a: {"n": len(got[r]), "over": len(got[r]) > CAP, "rows": got[r]}
                                                  for a, (r, _) in rels.items()}}
    return out

