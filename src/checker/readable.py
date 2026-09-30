"""The model's faults as findings."""

from checker.finding import (
    AtEntry,
    AtFile,
    AtLine,
    Finding,
    Kind,
    FaultPayload,
    Where,
    WholeFile,
    WitnessFileRole,
)
from checker.runs import Runs
from solver.model import Solver
from solver.problems import InSolver, InWitnessFile, Fault


def where_of(problem: Fault) -> Where:
    """Where a fault stands, as a finding's location."""
    match problem.place:
        case InSolver(line=line):
            return AtLine(line)
        case InWitnessFile(entry=entry):
            if entry is None:
                return AtFile(WholeFile.WITNESS_FILE)
            return AtEntry(entry, WitnessFileRole.TASK)


def finding_of(problem: Fault) -> Finding:
    """A fault as a finding (`check_faults`)."""
    return Finding(Kind(problem.kind), where_of(problem),
                   FaultPayload(problem))


def check_faults(solver: Solver, runs: Runs) -> list[Finding]:
    """A finding for each of the model's faults, so that every
    command reports them the same way (plan §D5; the problems are those of
    plan §D4 `Fault`). A fault's finding kind is its own kind
    (`Kind(problem.kind)`): the undecided one outside `FAILING`, every
    other inside it."""
    return [finding_of(p) for p in solver.problems]
