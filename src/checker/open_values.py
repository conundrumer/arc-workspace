"""The open-values check: which stored facts of a parameter that holds
more than one at a case no input of the task or of the witness file
exercises."""

from collections.abc import Collection

from checker.drop_one import DropOneReport, removal, survey_drop_one
from checker.finding import (
    AtFile,
    AtParameter,
    Finding,
    Kind,
    RunKind,
    WholeFile,
)
from checker.judged import no_result
from checker.payloads.open_values import (
    TrainFails,
    UnexercisedPayload,
)
from checker.runs import Runs
from checker.variants import TimedOut, with_program
from engine import Grid
from engine.quotes import quotes
from solver.aggregate import Solver
from solver.outcome import Assignment, first_failure
from solver.witnessed_cases import entry_assignments, placed_inputs


def inputs_without(solver: Solver, runs: Runs, parameters: Collection[str]
                   ) -> list[tuple[Grid, Assignment]]:
    """Each pair's input at the stored assignment, and each witness entry's
    input at its assignment, less an entry whose `assign` gives one of
    `parameters` or whose assignment is a fault."""
    entries = entry_assignments(runs.engine, solver, runs.entries,
                                runs.file_role)
    return placed_inputs(solver, [
        (e, at) for e, at in entries
        if all(name not in parameters for name, _v in e.assign)])


@quotes("principles.md", "Choice points and open parameters",
        "**open values**: the values of that parameter that a reader of the "
        "concept could take, and that the pairs do not separate.")
def check_open_values(solver: Solver, runs: Runs) -> list[Finding]:
    """Each fact the drop-one survey gives as dropped
    (`checker.drop_one.survey_drop_one`) whose removal changes the
    outcome of no case on any pair's input at the stored assignment, nor
    on any witness entry's input at its assignment; an entry whose
    `assign` gives the fact's parameter, or whose assignment is a fault,
    is not read for it. A run that gives no result is its finding. Where
    the stored program fails a train pair, the check does not run, and
    its one finding says so."""
    got = survey_drop_one(solver, runs)
    if isinstance(got, TimedOut):
        return [got.finding]
    if not isinstance(got, DropOneReport):
        return [Finding(Kind.OPEN_VALUES_UNCHECKED, AtFile(WholeFile.SOLVER),
                        got)]
    cases = runs.cases
    if not isinstance(cases, tuple):
        return [no_result(cases, RunKind.CASE, None, AtFile(WholeFile.SOLVER))] \
            if got.dropped else []
    out: list[Finding] = []
    for d in got.dropped:
        f = d.fact
        inputs = inputs_without(solver, runs, {f.parameter})
        before = runs.outcomes_on(solver, cases, inputs)
        after = runs.outcomes_on(
            with_program(solver, removal(runs.engine, solver, f)),
            cases, inputs)
        failed = first_failure(o for got in after for o in got.values())
        if failed is not None:
            out.append(no_result(failed, RunKind.DELETION, None,
                                 AtParameter(f.parameter)))
        elif before == after:
            out.append(Finding(Kind.UNEXERCISED, AtParameter(f.parameter),
                               UnexercisedPayload(f)))
    return out

