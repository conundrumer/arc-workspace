"""The runs on a task's pairs: the pairs of a task, the candidate
outputs of each, and which candidates each case's runs match."""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from arc.task import Alt, Example, Task, pair_name
from engine import Engine, Grid, Limits, RunFailure
from engine.program import as_grid
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.cases import cases as cases_of
from solver.model import Case
from solver.outcome import Assignment, Grids, Outcome, first_failure
from solver.solve import outcomes_on


class TaskSection(Enum):
    """The section of the task a pair stands in."""

    TRAIN = "train"
    TEST = "test"


@quotes("principles.md", "Models and tasks",
        "**fit**: a model fits a split task at an assignment when it fits "
        "each of the task's pairs.")
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


@dataclass(frozen=True)
class Candidates:
    """A pair's candidates as sets of accepted outputs, and the section of
    the task the pair stands in, which gives how an output matches them
    (`matching`)."""

    section: TaskSection
    accepted: tuple[tuple[Candidate, frozenset[Grid]], ...]


def candidates(section: TaskSection, ex: Example) -> Candidates:
    """The candidates of `ex`, a pair of `section` (principles.md, under
    "Models and tasks"; solver-file.md, under "Alt outputs")."""
    output = as_grid(ex.output)
    if ex.alt is None:
        return Candidates(section, ((Candidate.OUTPUT, frozenset({output})),))
    alt = as_grid(ex.alt.grid)
    if alt_kind(ex.alt) is AltKind.TIEBREAK:
        return Candidates(section,
                          ((Candidate.OUTPUT, frozenset({output, alt})),))
    return Candidates(section, ((Candidate.OUTPUT, frozenset({output})),
                                (Candidate.ALT, frozenset({alt}))))


TEST_ATTEMPTS = 2
"""The most grids an output on a test pair's input holds where it fits
the pair."""


@quotes("principles.md", "Models and tasks",
        "A train pair fits when the output on its input is the pair's "
        "candidate.")
@quotes("principles.md", "Models and tasks",
        "A test pair fits when the output on its input holds at most two "
        "grids, one of them in the pair's candidate.")
def matching(cands: Candidates, outcome: Outcome) -> tuple[Candidate, ...]:
    """The candidates of `cands`, a pair's (`candidates`), that `outcome`
    matches: on a train pair, the set of its grids is the candidate's set
    of accepted outputs; on a test pair, it holds at most `TEST_ATTEMPTS`
    grids, and one of them is in the candidate's set."""
    if not isinstance(outcome, Grids):
        return ()
    got = frozenset(outcome.grids)
    if cands.section is TaskSection.TRAIN:
        return tuple(c for c, accepted in cands.accepted if got == accepted)
    if len(got) > TEST_ATTEMPTS:
        return ()
    return tuple(c for c, accepted in cands.accepted if got & accepted)


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
    from solver.witnessed_cases import task_inputs
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
    input in the order of `examples`, each case matched against the pair's
    candidates (`matching`; a `tiebreak` alt joins the output's candidate, a
    `rule` alt is a second one, solver-file.md, under "Alt outputs")."""
    return tuple(pair_on(pair, ex, cases, here)
                 for (pair, ex), here in zip(examples(task), got, strict=True))


def matches_every(cands: Sequence[Candidates],
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
    failed = first_failure(got)
    if failed is not None:
        return failed
    return matches_every([candidates(p.section, ex) for p, ex in pairs], got)


def pair_on(pair: PairId, ex: Example, cases: Sequence[Case],
            here: Mapping[Case, Outcome]) -> PairRuns:
    """One pair's runs: each of `cases` with what it gives on the pair's
    input, `here`, matched against the pair's candidates (`pair_runs`)."""
    cands = candidates(pair.section, ex)
    return PairRuns(pair, tuple(
        CaseOnPair(case, here[case], matching(cands, here[case]))
        for case in cases))
