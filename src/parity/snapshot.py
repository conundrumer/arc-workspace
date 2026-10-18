"""The stored record of a solver's Souffle outcomes, which the engine's
parity checks compare with and which no check runs Souffle to make: each
case's outcome on each pair, the split tasks it fits, its outcome on each
witness input, and the CPU seconds of the solver's runs, under the key of
what those outcomes depend on (`record_key`). A record holds no outcome
the load of the machine gives: its runs take the gate's wall limit
(`RECORD_LIMITS`), and a solver whose record would hold a run stopped at
it has no record standing."""

import hashlib
import json
import threading
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

from arc.task import task_file
from cli.common import LIMITS, compile_failure, solver_path, stamp
from engine import (Limits, Program, RelationName, RunResult, Tuples, WallLimit,
                    checkout)
from engine.engine import InputValue
from gating.run import TIME_LIMIT
from parity import NameMap, case_name, name_map, names_path
from solver.aggregate import Solver
from solver.cases import cases as cases_of
from solver.load import load, task_id_of
from solver.model import Case
from solver.names import name
from solver.outcome import Assignment, Grids, Outcome
from solver.pair_runs import CaseOnPair, PairRuns, pair_runs
from solver.problems import WitnessFileRole
from solver.solve import outcomes_on
from solver.undefined import Undefined
from solver.witness import Entry, path as witness_path
from solver.witnessed_cases import entry_assignments, task_inputs
from checker.judged import Fits, Misses, NoResult, fit
from checker.plan_cache import reaches_wall
from souffle import SouffleEngine
from souffle.install import binary_identity

VERSION = 1
"""The form of a record: a change to what a record holds changes it, so
that every record of the earlier form is no longer fresh."""

RECORD_LIMITS = Limits(cpu_seconds=LIMITS.cpu_seconds, wall_seconds=TIME_LIMIT)
"""The limits of a record's runs: the wall limit the gate gives its
commands (`gating.run.TIME_LIMIT`), so that the CPU limit is the one a run
reaches first."""

RECORDS_WORKERS = 4
"""The solvers whose records `write_all` makes at once."""


def parity_dir() -> Path:
    """`.cache/parity/` of the main worktree: a record per solver and the
    uses file (`parity.uses`)."""
    return checkout.caches() / "parity"


def record_path(stem: str) -> Path:
    """Where the record of `stem` stands."""
    return parity_dir() / f"{stem}.json"


class TimedEngine(SouffleEngine):
    """The engine every command runs through (`cli.common.engine`), which
    sums the CPU seconds of the results its runs give, read from the run
    cache or run now."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self.cpu_seconds = 0.0

    def run(self, program: Program, inputs: Mapping[RelationName, InputValue],
            outputs: Sequence[RelationName], limits: Limits,
            caps: Mapping[RelationName, int] | None = None) -> RunResult:
        got = super().run(program, inputs, outputs, limits, caps)
        if isinstance(got, Tuples):
            with self._lock:
                self.cpu_seconds += got.cpu_seconds
        return got


def _digest(path: Path) -> str | None:
    """The sha256 of the file at `path`; None where no file stands there."""
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def record_key(stem: str) -> dict[str, Any]:
    """What the record of `stem` depends on: the form of the record, the
    solver file, the code and Souffle sources of a run (`stamp`), the
    Souffle binary (`souffle.install.binary_identity`), the task file, the
    witness file, and the name map the cases are keyed through."""
    task_id = task_id_of(stem)
    return {"version": VERSION, "solver": _digest(solver_path(stem)),
            "stamp": stamp(), "souffle": hashlib.sha256(binary_identity()).hexdigest(),
            "task": _digest(task_file(task_id)),
            "witnesses": _digest(witness_path(task_id)),
            "names": _digest(names_path(stem))}


def stored(stem: str) -> dict[str, Any] | None:
    """The stored record of `stem`; None where none is stored or it cannot
    be read."""
    try:
        return json.loads(record_path(stem).read_text())
    except (OSError, ValueError):
        return None


def fresh(stem: str) -> bool:
    """Whether the stored record of `stem` holds the key of the files and
    the code as they stand (`record_key`)."""
    held = stored(stem)
    return held is not None and held.get("key") == record_key(stem)


def outcome_json(outcome: Outcome) -> Any:
    """An outcome as a record holds it: its grids, `undefined`, or the
    kind of its run's failure."""
    match outcome:
        case Grids(grids=grids):
            return {"grids": [[list(row) for row in g] for g in grids]}
        case Undefined():
            return "undefined"
    return {"failure": type(outcome).__name__}


def run_of(pair: PairRuns, case: Case) -> CaseOnPair:
    """The run of `case` on `pair`, one of the cases the pair's runs were
    made for."""
    return next(c for c in pair.cases if c.case == case)


def split_tasks(pairs: Sequence[PairRuns], case: Case) -> list[dict[str, str]]:
    """The split tasks `case` fits, each as the candidate it takes at each
    pair that has two, by pair (docs/handbook/principles.md#models-and-tasks):
    those where the case's run on each pair matches the candidate the split
    task takes there."""
    runs = [(p.pair.text, run_of(p, case)) for p in pairs]
    if any(not run.matches for _pair, run in runs):
        return []
    two = [(pair, run.matches) for pair, run in runs if len(run.matches) > 1]
    return [{pair: c.value for (pair, _m), c in zip(two, chosen, strict=True)}
            for chosen in product(*(m for _pair, m in two))]


def fit_json(pairs: Sequence[PairRuns], case: Case) -> Any:
    """How `case` alone meets Fit (`checker.judged.fit`)."""
    match fit(pairs, (case,)):
        case Fits():
            return "fits"
        case Misses(pair=pair):
            return {"misses": pair.text}
        case NoResult(pairs=failed):
            return {"no result": [p.text for p, _f in failed]}
    return None


def failure_record(key: dict[str, Any], failure: str) -> dict[str, Any]:
    """The record of a solver whose cases have no outcomes: the kind of
    what stopped them."""
    return {"key": key, "failure": failure}


def solver_record(stem: str) -> dict[str, Any] | WallLimit:
    """The record of `stem`: under its key (`record_key`), each case by its
    arclog name (`parity.case_name`) with its Souffle name, its outcome on
    each train and test pair, how it meets Fit, the split tasks it fits and
    its outcome on each witness input; and the CPU seconds of the runs the
    record read, from the run cache or run now. A solver whose task has no
    file, that does not compile, or whose cases' enumeration fails has the
    kind of its failure in place of its cases. A record that would hold a
    run stopped at its wall limit (`checker.plan_cache.reaches_wall`) gives
    a `WallLimit` in place of the record."""
    key = record_key(stem)
    eng = TimedEngine()
    solver = load(stem, eng, solver_path(stem))
    if solver.task is None:
        return failure_record(key, "no task")
    failed = compile_failure(eng, solver)
    if failed is not None:
        return failure_record(key, type(failed).__name__)
    cases = cases_of(solver, eng, RECORD_LIMITS)
    if isinstance(cases, WallLimit):
        return cases
    if not isinstance(cases, tuple):
        return failure_record(key, type(cases).__name__)
    names = name_map(stem)
    pairs = pair_runs(solver.task, cases,
                      outcomes_on(eng, solver, cases, task_inputs(solver.task),
                                  RECORD_LIMITS))
    entries = [] if solver.witness_file is None else entry_assignments(
        eng, solver, solver.witness_file.entries, WitnessFileRole.TASK)
    witnessed = outcomes_on(eng, solver, cases, [(e.input, at) for e, at in entries],
                            RECORD_LIMITS)
    if reaches_wall((pairs, witnessed)):
        return WallLimit(RECORD_LIMITS.wall_seconds)
    return {"key": key, "converted": names is not None,
            "cases": _cases(solver, cases, names, pairs, entries, witnessed),
            "cpu_seconds": eng.cpu_seconds}


def _cases(solver: Solver, cases: Sequence[Case], names: NameMap | None,
           pairs: Sequence[PairRuns], entries: Sequence[tuple[Entry, Assignment]],
           witnessed: Sequence[Mapping[Case, Outcome]]) -> dict[str, Any]:
    """Each of `cases` by its arclog name, with what `solver_record`
    gives of it."""
    out: dict[str, Any] = {}
    for case in cases:
        out[case_name(solver, case, names)] = {
            "souffle": name(solver, case),
            "pairs": {p.pair.text: outcome_json(run_of(p, case).outcome) for p in pairs},
            "fit": fit_json(pairs, case),
            "split tasks": split_tasks(pairs, case),
            "witnesses": [{"id": e.id, "outcome": outcome_json(w[case])}
                          for (e, _at), w in zip(entries, witnessed, strict=True)],
        }
    return out


@dataclass(frozen=True)
class Written:
    """What `write_all` did: the path of each record written, and the stem
    of each solver whose record would hold a run stopped at its wall limit
    and so has no record standing, each in the order of the stems given."""

    paths: list[Path]
    stopped: list[str]


def write(stem: str) -> Path | None:
    """Write the record of `stem` (`solver_record`), and give its path;
    None, with no record of `stem` standing, where a run of it was stopped
    at its wall limit."""
    record = solver_record(stem)
    if isinstance(record, WallLimit):
        record_path(stem).unlink(missing_ok=True)
        return None
    path = record_path(stem)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    return path


def write_all(stems: Sequence[str]) -> Written:
    """Write the record of each of `stems` that is not fresh, `RECORDS_WORKERS`
    solvers at once (`write`)."""
    stale = [s for s in stems if not fresh(s)]
    with ThreadPoolExecutor(max_workers=RECORDS_WORKERS) as pool:
        got = list(pool.map(write, stale))
    return Written(paths=[p for p in got if p is not None],
                   stopped=[s for s, p in zip(stale, got, strict=True) if p is None])
