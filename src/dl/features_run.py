"""What a solver's cases do on its own pairs: which pairs tell two cases
apart, and which pairs a case is undefined on.

Every pair of the task counts, train and test alike. A case's key on a pair
is the set of grids it emits there, each grid or `UNDEF` when the grid is not
readable, and the stored output never enters the key. Two cases are separated by a pair when their keys there
differ, and the key tuples over all pairs partition the cases into
separation classes.
"""

import sys
from dataclasses import dataclass, field

from arc.task import load as load_task
from dl.models import Cases, CaseId, case_label, model_label
from dl.solve import PairResult, res_out_stem, run_task, solver_file

UNDEF = "UNDEF"
"""The key of a case that emits no readable grid on a pair."""

ABSENT = "ABSENT"
"""The key of a case that emits nothing at all on a pair."""

type Grid = str | tuple[tuple[int, ...], ...]
type Key = frozenset[Grid] | str
type Matrix = dict[CaseId, dict[CaseId, int]]


@dataclass
class RunReport:
    cases: list[CaseId] = field(default_factory=list)
    separating: dict[CaseId, int] = field(default_factory=dict)
    undefined: dict[CaseId, int] = field(default_factory=dict)
    separates: Matrix = field(default_factory=dict)
    classes: int = 0


def _grid(variant) -> Grid:
    if variant.error or variant.conflicts or variant.missing:
        return UNDEF
    return tuple(tuple(row) for row in variant.actual)


def _pair_keys(
    pairs: list[PairResult], cases: list[CaseId] | None, resolution: bool,
    held: list[dict[CaseId, Grid]] | None = None,
) -> tuple[list[CaseId], list[dict[CaseId, Key]]]:
    """The cases in the order the pairs produce them, and each pair's key
    per case. `cases` leads that order, so a case silent on every pair is
    still reported. A variant is keyed by its case spelled in full
    (`dl.models.model_label`) when `cases` spells it so, and by the
    runner's label otherwise. `held` holds, per pair, the grid each case
    that takes a `@derive` or `@store` branch gives there. A pair that
    fails outright produces no case."""
    order: list[CaseId] = list(cases or [])
    known = set(order)
    per_pair: list[dict[CaseId, Key]] = []
    for i, p in enumerate(pairs):
        emitted: dict[CaseId, set[Grid]] = {}
        for v in p.variants:
            full = model_label(v.name, resolution)
            name = full if full in known else case_label(v.name, resolution)
            if name not in order:
                order.append(name)
            emitted.setdefault(name, set()).add(_grid(v))
        keys: dict[CaseId, Key] = {n: frozenset(g) for n, g in emitted.items()}
        if held is not None and p.variants:
            for name, grid in held[i].items():
                if name not in order:
                    order.append(name)
                keys[name] = frozenset({grid})
        per_pair.append(keys)
    return order, per_pair


def _held_grids(stem: str, space: Cases, pairs: list[PairResult]
                ) -> list[dict[CaseId, Grid]]:
    """Per pair, the grid each case that takes a `@derive` or `@store`
    branch gives on the pair's input, or `UNDEF` where it gives none."""
    from dl.witness import held_outcomes

    path, task_id = solver_file(stem)
    task = load_task(task_id)
    source = path.read_text()
    ids = list(space.runner)
    out: list[dict[CaseId, Grid]] = []
    for p in pairs:
        ex = (task.train if p.kind == "train" else task.test)[p.idx]
        got = held_outcomes(stem, space, ids, ex.input, source)
        out.append({c: UNDEF if not isinstance(g, list)
                    else tuple(tuple(row) for row in g)
                    for c, g in got.items()})
    return out


def report_of(pairs: list[PairResult], cases: list[CaseId] | None = None,
              resolution: bool = False,
              held: list[dict[CaseId, Grid]] | None = None) -> RunReport:
    """The separation report over one solver's pair results, with `held`
    as `_pair_keys` takes it."""
    cases, per_pair = _pair_keys(pairs, cases, resolution, held)
    separates = {
        a: {b: sum(1 for keys in per_pair
                   if keys.get(a, ABSENT) != keys.get(b, ABSENT))
            for b in cases if b != a}
        for a in cases
    }
    separating = {
        a: sum(1 for keys in per_pair
               if any(keys.get(a, ABSENT) != keys.get(b, ABSENT)
                      for b in cases if b != a))
        for a in cases
    }
    undefined = {a: sum(1 for keys in per_pair if UNDEF in keys.get(a, ()))
                 for a in cases}
    tuples = {tuple(keys.get(a, ABSENT) for keys in per_pair) for a in cases}
    return RunReport(cases=cases, separating=separating, undefined=undefined,
                     separates=separates, classes=len(tuples))


def run_features(stem: str, space: Cases) -> RunReport:
    """Run every pair of `stem`, train and test, and report how its cases
    separate: the held cases of `space` (`dl.models.enumeration`), so one
    that emits nothing on every pair is reported rather than dropped, and
    the cases that take a `@derive` or `@store` branch."""
    pairs = run_task(stem).pairs
    print(f"{stem}: {len(pairs)} pairs", file=sys.stderr)
    held = _held_grids(stem, space, pairs) if space.runner else None
    return report_of(pairs, space.plain, res_out_stem(stem), held)
