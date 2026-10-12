"""The witnessed cases: the inputs the witness file records, the
branches a case takes, and what the runs show on those inputs."""

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from arc.task import Task
from engine import Engine, Grid, Limits, RunFailure, checkout
from engine.memo import write_whole
from engine.program import as_grid
from solver.aggregate import Solver, branch_witnesses, is_concept_case
from solver.annotations import VerdictWord
from solver.cases import cases as cases_of
from solver.model import (
    Branch,
    Case,
    Choice,
    ChoicePoint,
    ConstructorBranch,
    DeriveBranch,
    StoreBranch,
    constructor_named,
    constructors_taken,
    is_concept_branch,
    other_branches,
    path_constructors,
)
from solver.outcome import Assignment, Outcome, is_result
from solver.pair_runs import Candidate, RunOn, candidates, examples, matching
from solver.problems import WitnessFileRole
from solver.solve import assignment, outcomes_on
from solver.witness import Entry, same_output

if TYPE_CHECKING:
    from solver.names import Denoted


def recorded_inputs(engine: Engine, solver: Solver, entries: Sequence[Entry],
                    file: WitnessFileRole
                    ) -> list[tuple[Grid, Assignment]]:
    """The recorded inputs: the task's inputs, train then test, at the
    stored assignment, then each of `entries`', entries of `file`, inputs
    at its entry's assignment, each once. An entry whose assignment the
    model cannot place (`assignment`) gives none."""
    return placed_inputs(solver, entry_assignments(engine, solver, entries,
                                                   file))


def placed_inputs(solver: Solver, placed: Iterable[tuple[Entry, Assignment]]
                  ) -> list[tuple[Grid, Assignment]]:
    """The task's inputs, train then test, at the stored assignment, where
    the solver has a task, then the input of each entry of `placed` at its
    assignment, each once."""
    out: list[tuple[Grid, Assignment]] = []
    if solver.task is not None:
        out += task_inputs(solver.task)
    out += [(e.input, at) for e, at in placed]
    return list(dict.fromkeys(out))


def task_inputs(task: Task) -> list[tuple[Grid, Assignment]]:
    """The task's inputs, train then test (`examples`), each at the stored
    assignment."""
    return [(as_grid(ex.input), Assignment(())) for _pair, ex in examples(task)]


type Candidates = tuple[tuple[Candidate, frozenset[Grid]], ...]
"""A pair's candidates (`candidates`)."""


def pairs_at(task: Task | None) -> dict[tuple[Grid, Assignment],
                                        tuple[Candidates, ...]]:
    """The candidates of each pair of `task` (`examples`) whose input is
    each of its inputs at the stored assignment, keyed as `task_inputs`
    keys a pair's input; none where there is no task."""
    out: dict[tuple[Grid, Assignment], tuple[Candidates, ...]] = {}
    if task is None:
        return out
    for (_pair, ex), at in zip(examples(task), task_inputs(task), strict=True):
        out[at] = (*out.get(at, ()), candidates(ex))
    return out


def entry_assignments(engine: Engine, solver: Solver, entries: Sequence[Entry],
                      file: WitnessFileRole
                      ) -> list[tuple[Entry, Assignment]]:
    """Each of `entries`, entries of `file`, at its assignment
    (`assignment`), in order; an entry whose assignment the model cannot
    place is left out."""
    return [(e, at) for e in entries
            if isinstance(at := assignment(engine, solver, e, file), Assignment)]


type Taken = tuple[str, tuple[str, ...]] | Branch
"""A non-concept branch a case takes: a constructor, by its name and its
point's path, or a `@derive` or `@store` branch."""


def taken(solver: Solver, case: Case) -> frozenset[Taken]:
    """The non-concept branches `case` takes: each constructor of its base
    other than its point's first, and its `@derive` and `@store`
    branches."""
    out: set[Taken] = set(case.branches)
    choice = solver.choice
    if choice is not None and case.base is not None:
        out |= {(ctor, p.path)
                for p, ctor in constructors_taken(choice, case.base)
                if not is_concept_branch(p, ctor)}
    return frozenset(out)


def rejected(solver: Solver, branch: Taken) -> bool:
    """Whether `branch` is rejected: it has a `@witness` line or a
    `@derive` or `@store` line, and every verdict on it is `concept`."""
    if isinstance(branch, tuple):
        verdicts = [w.verdict for w in branch_witnesses(solver, branch[0])]
    elif isinstance(branch, DeriveBranch | StoreBranch) \
            and branch.line is not None:
        verdicts = [branch.line.verdict]
    else:
        verdicts = []
    return bool(verdicts) and all(v is VerdictWord.CONCEPT for v in verdicts)


def constructor_denoted(choice: Choice, point: ChoicePoint,
                        ctor: ConstructorBranch) -> "Denoted":
    """The branches a model of `ctor` at `point` fixes: `ctor`, and the
    constructor at each point above it through which it is reached."""
    from solver.names import Denoted

    parents: list[ConstructorBranch] = []
    for name in path_constructors(choice, point.path):
        parent = constructor_named(choice, name)
        assert parent is not None, "a point's path names its constructors"
        parents.append(parent)
    return Denoted((*parents, ctor), ())


def branch_models(solver: Solver, cases: Sequence[Case]) -> list[Case]:
    """The model of each branch other than a point's concept branch, among
    `cases` (`branch_model`): a constructor at its choice point, and each
    `@derive` and `@store` branch."""
    from solver.names import Denoted

    denoted: list[Denoted] = []
    choice = solver.choice
    if choice is not None:
        denoted += [constructor_denoted(choice, p, c)
                    for p in choice.points for c in other_branches(p)]
    denoted += [Denoted((), (b,)) for b in solver.branches
                if isinstance(b, DeriveBranch | StoreBranch)]
    return [m for d in denoted
            if (m := branch_model(solver, cases, d)) is not None]


def branch_model(solver: Solver, cases: Sequence[Case], d: "Denoted"
                 ) -> Case | None:
    """The case of `cases` that stands for the model of the branch `d`
    names: its model (`solver.names.model_of`) where that is one of
    `cases`; else the case of `cases` that takes the branch and differs
    from the concept case at the fewest points, constructors and branches
    counted alike (`taken`), ties by name order; None where no case of
    `cases` takes it."""
    from solver.names import name

    tied = stand_ins(solver, cases, d)
    return min(tied, key=lambda c: name(solver, c)) if tied else None


def stand_ins(solver: Solver, cases: Sequence[Case], d: "Denoted"
              ) -> list[Case]:
    """The cases of `cases` that can stand for the model of the branch `d`
    names: its model (`solver.names.model_of`) alone where that is one of
    `cases`; else every case of `cases` that takes the branch and differs
    from the concept case at the fewest points, constructors and branches
    counted alike (`taken`), in the order of `cases`; none where no case
    takes it."""
    from solver.names import cases_of, model_of

    model = model_of(solver, d, cases)
    if model is not None and model in cases:
        return [model]
    taking = cases_of(solver, d, cases)
    if not taking:
        return []
    away = {c: len(taken(solver, c)) for c in taking}
    least = min(away.values())
    return [c for c in taking if away[c] == least]


@dataclass(frozen=True)
class Shown:
    """What one recorded input shows of the solver's cases (`witnessed`):
    the cases whose run on it fails, the cases whose output on it no
    case they extend gives, and the cases whose run gives a result that
    is no candidate of a pair of the task whose input it is."""

    failed: frozenset[Case]
    differing: frozenset[Case]
    missed: frozenset[Case]


def shown_on(cases: Sequence[Case],
             extends: Mapping[Case, Sequence[Case]],
             got: Mapping[Case, Outcome],
             pairs: Sequence[Candidates]) -> Shown:
    """What one recorded input shows of `cases` (`Shown`), from `got`,
    what each of them gives on it, `extends` giving the cases each
    extends, and `pairs` the candidates of each pair of the task whose
    input it is."""
    failed = frozenset(c for c in cases if not is_result(got[c]))
    return Shown(failed, frozenset(
        c for c in cases if c not in failed
        and all(not same_output(got[d], got[c]) for d in extends[c])),
        frozenset(c for c in cases if c not in failed
                  and any(not matching(p, got[c]) for p in pairs)))


def extended(took: Mapping[Case, frozenset[Taken]]
             ) -> dict[Case, list[Case]]:
    """The cases each case of `took` extends (`witnessed`), `took` giving
    each case's branches (`taken`). The branches are compared by their
    place in one numbering, so that no comparison reads a branch's
    parts."""
    number: dict[Taken, int] = {}
    coded = {c: frozenset(number.setdefault(b, len(number)) for b in t)
             for c, t in took.items()}
    return {c: [d for d, other in coded.items() if other < mine]
            for c, mine in coded.items()}


def witnessed_by(solver: Solver, cases: Sequence[Case],
                 took: Mapping[Case, frozenset[Taken]],
                 shown: Iterable[Shown]) -> tuple[Case, ...]:
    """The witnessed cases of `cases`, in their order (`witnessed`), from
    what each recorded input shows of them, `took` giving the branches
    each takes (`taken`)."""
    rejects = {b for t in took.values() for b in t if rejected(solver, b)}
    requires: dict[Taken, frozenset[Taken]] = {}
    for t in took.values():
        for b in t:
            requires[b] = requires[b] & t if b in requires else t

    def stacked(t: frozenset[Taken]) -> bool:
        mine = list(t & rejects)
        return any(y not in requires[x] and x not in requires[y]
                   for i, x in enumerate(mine) for y in mine[i + 1:])

    kept = set(branch_models(solver, cases))
    kept |= {c for c in cases if is_concept_case(solver, c)}
    failed: set[Case] = set()
    differing: set[Case] = set()
    for one in shown:
        failed |= one.failed | one.missed
        differing |= one.differing
    return tuple(c for c in cases if c in failed or c in kept or (
        not stacked(took[c]) and c in differing))


WITNESSED_DIR = "witnessed"
"""The directory under the run cache that holds, for each recorded input,
what it shows of the solver's cases (`witnessed`)."""


SHOWN_FIELD = "differing"
"""The field of a kept record (`hold_shown`) that names the cases whose
output on the input no case they extend gives (`Shown.differing`)."""


MISSED_FIELD = "missed"
"""The field of a kept record (`hold_shown`) that names the cases whose
result on the input is no candidate of a pair whose input it is
(`Shown.missed`)."""


def witnessed_base(solver: Solver, limits: Limits) -> "hashlib._Hash":
    """The hash that every recorded input's key starts from
    (`shown_key`): the content of the solver's program, of its annotations
    and of its branches, a line a survey proposes among them, without
    where their parts stand or the comments (`_placeless`), of the task,
    the limits, and the tool's sources."""
    h = hashlib.sha256()
    h.update(repr((_placeless(solver.program),
                   _placeless(solver.annotations),
                   _placeless(solver.branches),
                   solver.task, limits)).encode())
    for path in sorted((checkout.ROOT / "src").rglob("*.py")):
        h.update(b"\0" + path.read_bytes())
    return h


def shown_key(base: "hashlib._Hash", input: Grid, at: Assignment) -> str:
    """The key of what the recorded input `input` at `at` shows of the
    solver's cases, `base` the solver's hash (`witnessed_base`)."""
    h = base.copy()
    h.update(b"\0" + repr((input, at)).encode())
    return h.hexdigest()


_PLACES = frozenset({"span", "line", "comments", "layout"})
"""The fields `_placeless` leaves out: where a part stands in the file,
and the comments, whose annotations the solver's annotations hold."""


def _placeless(x: object) -> object:
    """A value that states `x` without where its parts stand in the file
    and without its comments: what the witnessed cases read of a program
    or of its annotations, so that an edit to a comment that is no
    annotation, or a line moved, keeps their key."""
    if isinstance(x, tuple | list):
        return tuple(_placeless(y) for y in x)
    if isinstance(x, Mapping):
        return tuple((_placeless(k), _placeless(v)) for k, v in x.items())
    if is_dataclass(x) and not isinstance(x, type):
        return (type(x).__name__, tuple(
            (f.name, _placeless(getattr(x, f.name))) for f in fields(x)
            if f.name not in _PLACES))
    return x


def _shown_path(key: str) -> Path:
    return checkout.cache() / WITNESSED_DIR / f"{key}.json"


def held_shown(key: str, by_name: Mapping[str, Case]) -> Shown | None:
    """What a recorded input shows of the solver's cases, kept under `key`
    (`hold_shown`), `by_name` giving each case by its name
    (`solver.names.name`); None where nothing is kept, or where a kept
    name is the name of no case."""
    try:
        got = json.loads(_shown_path(key).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(got, dict):
        return None
    named: list[frozenset[Case]] = []
    for field in (SHOWN_FIELD, MISSED_FIELD):
        picked = got.get(field)
        if not isinstance(picked, list):
            return None
        if not all(isinstance(n, str) and n in by_name for n in picked):
            return None
        named.append(frozenset(by_name[n] for n in picked))
    return Shown(frozenset(), *named)


def hold_shown(key: str, by_name: Mapping[str, Case], shown: Shown) -> None:
    """Keeps `shown`, what a recorded input shows of the solver's cases,
    where no run on the input failed, under `key`, by the cases' names,
    `by_name` giving each case by its name (`solver.names.name`) in the
    order of the cases. A failed run is not kept, so that it runs
    again."""
    if shown.failed:
        return
    path = _shown_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_whole(path, json.dumps({
        field: [n for n, c in by_name.items() if c in held]
        for field, held in ((SHOWN_FIELD, shown.differing),
                            (MISSED_FIELD, shown.missed))}).encode())


def witnessed(engine: Engine, solver: Solver, limits: Limits,
              file: WitnessFileRole,
              entries: Sequence[Entry] | None = None, run: RunOn | None = None,
              unlined: tuple[Sequence[Case], Sequence[Case]] | None = None
              ) -> tuple[Case, ...] | RunFailure:
    """The witnessed cases of the solver's cases, in their order, or the
    failure of the run that enumerates them. A case
    extends another when it takes that case's non-concept branches and
    more (`taken`). A case is witnessed when it is the concept case or a
    branch's model (`branch_models`), or when some recorded input
    (`recorded_inputs`, the witness file's entries) shows it giving an
    output, its grids over the tiebreak resolutions or undefined, that no
    case it extends gives, so that a case
    undefined where a case it extends gives a grid is witnessed and its
    Fit failure shown. A case other than the concept case and the
    branch models is not witnessed on the output an input shows when it
    takes two rejected branches (`rejected`) of which neither requires
    the other, a branch requiring another when every case of the solver
    that takes it takes the other. A case whose run on some recorded
    input fails or reaches a limit is witnessed, so that the failure is
    shown, and so is a case whose run on a recorded input that is a
    pair's input of the task gives a result that is no candidate of that
    pair (`matching`), whatever branches it takes, so that its Fit
    failure on the pair is shown. A recorded input that is the input of
    several pairs is judged against each of them.
    What each recorded input shows (`Shown`) is kept on disk under its
    key (`shown_key`) where no run on it failed, so that a command on an
    unchanged solver runs nothing, and one with an entry added runs the
    entry's input alone.

    The recorded inputs are those of `entries`, entries of `file`, else of
    the solver's witness file; the runs on them come from `run`, else from
    `outcomes_on`.

    `unlined` is given for the solver with a line a survey proposes
    added: the cases and the witnessed cases of the solver without it. A
    case of both solvers keeps its standing there, unchanged by the line;
    of the cases that take the new branch, the witnessed ones are judged
    as above."""
    every = cases_of(solver, engine, limits)
    if not isinstance(every, tuple):
        return every
    if entries is None:
        entries = () if solver.witness_file is None \
            else solver.witness_file.entries
        file = WitnessFileRole.TASK
    from solver.names import name
    inputs = recorded_inputs(engine, solver, entries, file)
    base = witnessed_base(solver, limits)
    keys = [shown_key(base, g, a) for g, a in inputs]
    by_name = {name(solver, c): c for c in every}
    shown = [held_shown(k, by_name) for k in keys]
    lacking = [i for i, s in enumerate(shown) if s is None]
    took = {c: taken(solver, c) for c in every}
    found: dict[int, Shown] = {}
    if lacking:
        on = [inputs[i] for i in lacking]
        got = run(every, on) if run is not None \
            else outcomes_on(engine, solver, every, on, limits)
        extends = extended(took)
        at = pairs_at(solver.task)
        for i, here in zip(lacking, got, strict=True):
            found[i] = shown_on(every, extends, here, at.get(inputs[i], ()))
            hold_shown(keys[i], by_name, found[i])
    out = witnessed_by(solver, every, took, [
        s if s is not None else found[i] for i, s in enumerate(shown)])
    if unlined is not None:
        before, kept, among = set(unlined[0]), set(unlined[1]), set(out)
        out = tuple(c for c in every
                    if (c in kept if c in before else c in among))
    return out
