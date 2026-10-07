"""The runs on a task's pairs, and the witnessed cases: the inputs the
witness file records, the branches a case takes, and what the runs show
on those inputs."""

import hashlib
import json
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from arc.task import Alt, Example, Task, pair_name
from engine import (
    Engine,
    Grid,
    Limits,
    RunFailure,
    checkout,
)
from engine.memo import write_whole
from engine.program import as_grid
from engine.quotes import quotes
from solver.aggregate import (
    Solver,
    branch_witnesses,
    is_concept_case,
)
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
from solver.outcome import Assignment, Grids, Outcome, is_result
from solver.problems import (
    WitnessFileRole,
)
from solver.solve import assignment, outcomes_on
from solver.witness import (
    Entry,
    same_output,
)

if TYPE_CHECKING:
    from solver.names import Denoted


# Pairs


class TaskSection(Enum):
    """The section of the task a pair stands in."""

    TRAIN = "train"
    TEST = "test"


@quotes("principles.md", "Models and tasks",
        "**fit**: a model fits a split task at an assignment when its output "
        "on each pair's input is that pair's candidate, including for the "
        "test pairs.")
@dataclass(frozen=True)
class PairId:
    """A pair of the task, by section and index."""

    section: TaskSection
    index: int

    @property
    def text(self) -> str:
        """The pair as every command writes it (`arc.task.pair_name`)."""
        return pair_name(self.section.value, self.index)


@quotes("solver-file.md", "Alt outputs",
        "An alt with kind `rule` gives the pair a second candidate. An alt "
        "with kind `tiebreak` gives resolutions within one candidate.")
class AltKind(Enum):
    """How a pair's alt output differs from its output: a `rule` alt is a
    second candidate, a `tiebreak` alt another resolution within the
    output's."""

    RULE = "rule"
    TIEBREAK = "tiebreak"


def alt_kind(alt: Alt) -> AltKind:
    """The kind the task file gives `alt`."""
    return AltKind(alt.kind)


@quotes("principles.md", "Models and tasks",
        "**candidate**: a set of a pair's accepted outputs that differ only "
        "in a tiebreak.")
class Candidate(Enum):
    """A pair's candidate outputs: its output and its alt."""

    OUTPUT = "output"
    ALT = "alt"


@dataclass(frozen=True)
class CaseOnPair:
    """What a case gives on a pair, and the candidates its grids match."""

    case: Case
    outcome: Outcome
    matches: tuple[Candidate, ...]


@dataclass(frozen=True)
class PairRuns:
    """Every case of the solver's run on one pair."""

    pair: PairId
    cases: tuple[CaseOnPair, ...]


def examples(task: Task) -> Iterator[tuple[PairId, Example]]:
    """The task's pairs, train then test, each with its id."""
    for i, ex in enumerate(task.train):
        yield PairId(TaskSection.TRAIN, i), ex
    for i, ex in enumerate(task.test):
        yield PairId(TaskSection.TEST, i), ex


def candidates(ex: Example) -> tuple[tuple[Candidate, frozenset[Grid]], ...]:
    """A pair's candidates as sets of accepted outputs (principles.md, under
    "Models and tasks"; solver-file.md, under "Alt outputs")."""
    output = as_grid(ex.output)
    if ex.alt is None:
        return ((Candidate.OUTPUT, frozenset({output})),)
    alt = as_grid(ex.alt.grid)
    if alt_kind(ex.alt) is AltKind.TIEBREAK:
        return ((Candidate.OUTPUT, frozenset({output, alt})),)
    return ((Candidate.OUTPUT, frozenset({output})),
            (Candidate.ALT, frozenset({alt})))


def matching(cands: Sequence[tuple[Candidate, frozenset[Grid]]],
             outcome: Outcome) -> tuple[Candidate, ...]:
    """The candidates of `cands`, a pair's (`candidates`), that `outcome`
    matches: the set of its grids is the candidate's set of accepted outputs
    (principles.md, under "Models and tasks")."""
    if not isinstance(outcome, Grids):
        return ()
    got = frozenset(outcome.grids)
    return tuple(c for c, accepted in cands if got == accepted)


type RunOn = Callable[[Sequence[Case], Sequence[tuple[Grid, Assignment]]],
                      Sequence[Mapping[Case, Outcome]]]
"""What each of the cases gives on each input at its assignment, in the
order of the inputs, as `outcomes_on` gives it: a caller that holds runs
gives its own, so that a run it holds is not made again."""


def pairs(engine: Engine, solver: Solver, limits: Limits,
          cases: Sequence[Case] | None = None, run: RunOn | None = None
          ) -> tuple[PairRuns, ...] | RunFailure:
    """Per train and test pair, per case: the run and the judged profile
    (`pair_runs`), of `cases`, else of the solver's cases, from `run`,
    else from `outcomes_on`. Where the run that enumerates the solver's
    cases fails, its failure. It never gives empty pairs: it raises
    `ValueError` where the solver has no task (`Solver.given_task`)."""
    task = solver.given_task
    if cases is None:
        every = cases_of(solver, engine, limits)
        if not isinstance(every, tuple):
            return every
        cases = every
    inputs = task_inputs(task)
    got = run(cases, inputs) if run is not None \
        else outcomes_on(engine, solver, cases, inputs, limits)
    return pair_runs(task, cases, got)


def pair_runs(task: Task, cases: Sequence[Case],
              got: Sequence[Mapping[Case, Outcome]]) -> tuple[PairRuns, ...]:
    """`pairs` of `cases`, from `got`, what each case gives on each pair's
    input in the order of `examples`. A case matches a candidate when the set
    of its grids is the candidate's set of accepted outputs (`matching`; a
    `tiebreak` alt joins the output's candidate, a `rule` alt is a second one,
    solver-file.md, under "Alt outputs")."""
    return tuple(pair_on(pair, ex, cases, here)
                 for (pair, ex), here in zip(examples(task), got, strict=True))


def matches_every(cands: Sequence[Sequence[tuple[Candidate, frozenset[Grid]]]],
                  given: Sequence[Outcome]) -> bool:
    """Whether each of `given`, one case's outcome on each of a run of
    pairs, is a candidate of its pair, `cands` the pairs' candidates in
    the same order (`matching`)."""
    return all(matching(c, o) for c, o in zip(cands, given, strict=True))


def fits_pairs(engine: Engine, solver: Solver, case: Case,
               pairs: Sequence[tuple[PairId, Example]], limits: Limits
               ) -> bool | RunFailure:
    """Whether `case` gives on each of `pairs` an output that is a
    candidate of the pair (`matches_every`), its runs on every pair made at
    once (`outcomes_on`); the failure of a run where one fails."""
    got = [o[case] for o in outcomes_on(
        engine, solver, (case,),
        [(as_grid(ex.input), Assignment(())) for _p, ex in pairs], limits)]
    failed = next((o for o in got if not is_result(o)), None)
    if failed is not None:
        return failed
    return matches_every([candidates(ex) for _p, ex in pairs], got)


def pair_on(pair: PairId, ex: Example, cases: Sequence[Case],
            here: Mapping[Case, Outcome]) -> PairRuns:
    """One pair's runs: each of `cases` with what it gives on the pair's
    input, `here`, matched against the pair's candidates (`pair_runs`)."""
    cands = candidates(ex)
    return PairRuns(pair, tuple(
        CaseOnPair(case, here[case], matching(cands, here[case]))
        for case in cases))


# Witnessed cases


def recorded_inputs(engine: Engine, solver: Solver, entries: Sequence[Entry],
                    file: WitnessFileRole
                    ) -> list[tuple[Grid, Assignment]]:
    """The recorded inputs: the task's inputs, train then test, at the
    stored assignment, then each of `entries`', entries of `file`, inputs
    at its entry's assignment, each once. An entry whose assignment the
    model cannot place (`assignment`) gives none."""
    out: list[tuple[Grid, Assignment]] = []
    if solver.task is not None:
        out += task_inputs(solver.task)
    out += [(e.input, at)
            for e, at in entry_assignments(engine, solver, entries, file)]
    return list(dict.fromkeys(out))


def task_inputs(task: Task) -> list[tuple[Grid, Assignment]]:
    """The task's inputs, train then test (`examples`), each at the stored
    assignment."""
    return [(as_grid(ex.input), Assignment(())) for _pair, ex in examples(task)]


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
    the cases whose run on it fails, and the cases whose output on it no
    case they extend gives."""

    failed: frozenset[Case]
    differing: frozenset[Case]


def shown_on(cases: Sequence[Case],
             extends: Mapping[Case, Sequence[Case]],
             got: Mapping[Case, Outcome]) -> Shown:
    """What one recorded input shows of `cases` (`Shown`), from `got`,
    what each of them gives on it, `extends` giving the cases each
    extends."""
    failed = frozenset(c for c in cases if not is_result(got[c]))
    return Shown(failed, frozenset(
        c for c in cases if c not in failed
        and all(not same_output(got[d], got[c]) for d in extends[c])))


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
        failed |= one.failed
        differing |= one.differing
    return tuple(c for c in cases if c in failed or c in kept or (
        not stacked(took[c]) and c in differing))


WITNESSED_DIR = "witnessed"
"""The directory under the run cache that holds, for each recorded input,
what it shows of the solver's cases (`witnessed`)."""

SHOWN_FIELD = "differing"
"""The field of a kept record (`hold_shown`) that names the cases whose
output on the input no case they extend gives (`Shown.differing`)."""


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
    picked = got.get(SHOWN_FIELD) if isinstance(got, dict) else None
    if not isinstance(picked, list):
        return None
    if not all(isinstance(n, str) and n in by_name for n in picked):
        return None
    return Shown(frozenset(), frozenset(by_name[n] for n in picked))


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
    write_whole(path, json.dumps({SHOWN_FIELD: [
        n for n, c in by_name.items() if c in shown.differing]}).encode())


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
    output, its grids over the tiebreak resolutions or undefined with its
    reason and cells, that no case it extends gives, so that a case
    undefined where a case it extends gives a grid is witnessed and its
    Fit failure shown. A case other than the concept case and the
    branch models is not witnessed on what an input shows when it takes
    two rejected branches (`rejected`) of which neither requires the
    other, a branch requiring another when every case of the solver that
    takes it takes the other. A case whose run on some recorded input
    fails or reaches a limit is witnessed, so that the failure is shown.
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
        for i, here in zip(lacking, got, strict=True):
            found[i] = shown_on(every, extends, here)
            hold_shown(keys[i], by_name, found[i])
    out = witnessed_by(solver, every, took, [
        s if s is not None else found[i] for i, s in enumerate(shown)])
    if unlined is not None:
        before, kept, among = set(unlined[0]), set(unlined[1]), set(out)
        out = tuple(c for c in every
                    if (c in kept if c in before else c in among))
    return out
