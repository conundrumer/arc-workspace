"""What the witness checks and the case conditions read of the runs and of
the witness file."""

from collections.abc import Sequence

from checker.branches.witnesses import shows_apart
from checker.finding import (
    AtEntry,
    AtPair,
    Finding,
    RunKind,
    Where,
)
from checker.judged import (
    differ,
    is_timeout,
    no_result,
)
from checker.payloads.witness import (
    CaseSet,
)
from checker.runs import Runs
from solver.group_runs import at_once
from solver.model import (
    Case,
)
from solver.names import (
    cover,
    name,
)
from solver.outcome import Grids, Outcome, is_result
from solver.pair_runs import PairRuns, examples, pairs, task_inputs
from solver.problems import (
    Fault,
)
from solver.witness import (
    Entry,
    GroupGrid,
    NoOutput,
    RejectedOutput,
    Resolutions,
    Undefined,
)


def entry_at(runs: Runs, entry: Entry) -> AtEntry:
    return AtEntry(entry.id, runs.file_role)


def is_shown(runs: Runs, case: Case) -> bool:
    """A case whose findings the runs show: every case of the solver, and under the
    `witness --every-case` form a case whose base the solver's own
    `impl_choice` holds."""
    return runs.kept is None or any(k.base == case.base for k in runs.kept)


def shown_cases(runs: Runs, cases: Sequence[Case] | None = None
                ) -> list[Case]:
    """The cases of `cases`, the cases the checks read where None, whose
    findings the runs show (`is_shown`)."""
    return [c for c in (runs.cases_or_none if cases is None else cases)
            if is_shown(runs, c)]


def emits_nothing(o: object) -> bool:
    """A run that gives no cell at the case."""
    return isinstance(o, Undefined) and isinstance(o.reason, NoOutput)


def defined(o: object) -> bool:
    return isinstance(o, Grids)


def records(expected: GroupGrid, got: Outcome) -> bool:
    """A group's grid records the outcome: its grid, its list of grids, one
    per resolution (history 1119), or null for undefined."""
    match expected:
        case Undefined():
            return isinstance(got, Undefined)
        case Resolutions(grids=gs):
            return isinstance(got, Grids) and got.grids == gs
        case _:
            return isinstance(got, Grids) and got.grids == (expected,)


def judged_entries(runs: Runs) -> list[tuple[Entry, RejectedOutput]]:
    """The entries the checks read that hold a judged output
    (solver-file.md, under "Witness file") at an assignment the model places,
    each with that output."""
    return [(e, e.output) for e in runs.entries
            if isinstance(e.output, RejectedOutput)
            and not isinstance(runs.assignment(e), Fault)]


def gives(output: RejectedOutput) -> Grids:
    """The outcome of a case that gives the judged output `output`: its
    one grid."""
    return Grids((output.grid,))


type Inputs = list[dict[Case, Outcome]]
"""The inputs a pair of cases is compared on, each as the outcome of every
case of the solver there."""


def recorded_outcomes(runs: Runs) -> Inputs:
    """What every case of the solver gives on each recorded input
    (`Runs.recorded`)."""
    return runs.outcomes_at(runs.cases_or_none, runs.recorded)


def _outcomes_of(runs: Runs, case: Case) -> list[Outcome]:
    """What `case` gives on each input `recorded_outcomes` reads, in its order."""
    return [runs.grid_outcome(g, a, case) for g, a in runs.recorded]


def alone_outcomes(runs: Runs, cases: Sequence[Case]
                   ) -> dict[Case, list[Outcome]]:
    """`_outcomes_of` each case on its own (`Runs.alone`), the runs of
    every case on every input made at once."""
    alone = [runs.alone(a) for a in cases]
    at_once(lambda r: r.cases, alone)
    items = [(r, a, g, at) for a, r in zip(cases, alone, strict=True)
             for g, at in r.recorded]
    at_once(lambda i: i[0].grid_outcome(i[2], i[3], i[1]), items)
    return {a: _outcomes_of(r, a) for a, r in zip(cases, alone, strict=True)}


def reads_inputs(runs: Runs) -> bool:
    """The equivalence and subsumption checks compare cases over the
    inputs of the task's witness file: a solver with no witness file
    compares none, and neither do the runs of a given file (`witness
    --file`), whose report has only the findings at its witnesses."""
    return runs.given is None and runs.solver.witness_file is not None


def no_result_findings(got: Sequence[tuple[Case, Outcome | Fault]],
                       run: RunKind, where: Where) -> list[Finding]:
    """The runs on one input that gave no result: a timeout per case whose
    run reached a limit, and the first failure of another kind, once per
    input."""
    out: list[Finding] = []
    failed = False
    for c, o in got:
        if is_timeout(o):
            out.append(no_result(o, run, c, where))
        elif not isinstance(o, Grids | Undefined | Fault) and not failed:
            failed = True
            out.append(no_result(o, run, None, where))
    return out


def pair_failures(runs: Runs) -> list[Finding]:
    """The runs of the solver's cases on the task's pairs, at the stored
    assignment, that gave no result, each at its pair."""
    solver_cases = runs.cases_or_none
    task = runs.solver.given_task
    return [f for (pair, _ex), (g, a) in zip(examples(task), task_inputs(task),
                                            strict=True)
            for f in no_result_findings([(c, runs.grid_outcome(g, a, c))
                                for c in solver_cases],
                               RunKind.PAIR, AtPair(pair))]


def case_pairs(runs: Runs, case: Case) -> tuple[PairRuns, ...]:
    """`case` on every train and test pair at the stored assignment
    (`solver.pair_runs.pairs`)."""
    got = pairs(runs.engine, runs.solver, runs.limits, [case],
                runs.outcomes_at)
    if not isinstance(got, tuple):
        raise ValueError("`pairs` of given cases enumerates no case")
    return got


def _agree(inputs: Inputs, a: Case, b: Case) -> bool | None:
    """Whether `a` and `b` agree on every input; None where a run of either
    gave no result on an input where they do not already differ, so no
    input is known to separate them."""
    unknown = False
    for got in inputs:
        x, y = got[a], got[b]
        if not is_result(x) or not is_result(y):
            unknown = True
            continue
        if differ(x, y):
            return False
    return None if unknown else True


def subsumes(inputs: Inputs, a: Case, b: Case) -> bool:
    """No input shows `a` defined and differing from `b` (`shows_apart`),
    and some input shows `a` undefined where `b` is defined, so the two
    are not equivalent there (principles.md, under "Equivalence and
    subsumption"). An input with no result for either shows nothing, and
    then no subsumption is found."""
    apart = False
    for got in inputs:
        x, y = got[a], got[b]
        if not is_result(x) or not is_result(y):
            return False
        if shows_apart(x, y):
            return False
        if not defined(x) and defined(y):
            apart = True
    return apart


def unseparated_pairs(runs: Runs, inputs: Inputs) -> list[tuple[Case, Case]]:
    """Each unordered pair of cases of the solver that agree on every input, in the
    order of the solver's cases. A solver with no witness file compares no
    pair."""
    if not reads_inputs(runs):
        return []
    solver_cases = runs.cases_or_none
    return [(a, b) for i, a in enumerate(solver_cases) for b in solver_cases[i + 1:]
            if _agree(inputs, a, b) is True]


def case_set(runs: Runs, cases: Sequence[Case]) -> CaseSet:
    """`cases` with the names that print them: a lone case's name, else
    the fewest names that denote exactly them among the solver's cases
    (`solver.names.cover`)."""
    solver = runs.solver
    names = (name(solver, cases[0]),) if len(cases) == 1 \
        else cover(solver, cases, runs.cases_or_none)
    return CaseSet(tuple(cases), names)
