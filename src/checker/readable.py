"""The model's faults as findings."""

from checker.finding import (
    AtEntry,
    AtFile,
    AtLine,
    FaultPayload,
    Finding,
    Kind,
    Where,
    WholeFile,
)
from checker.runs import Runs
from solver.model import Solver
from solver.problems import Fault, InSolver, InWitnessFile


def where_of(problem: Fault) -> Where:
    """Where a fault stands, as a finding's location."""
    match problem.place:
        case InSolver(line=line):
            return AtLine(line)
        case InWitnessFile(entry=entry, file=file):
            if entry is None:
                return AtFile(WholeFile.WITNESS_FILE)
            return AtEntry(entry, file)


def finding_of(problem: Fault) -> Finding:
    """A fault as a finding."""
    return Finding(Kind(problem.kind), where_of(problem),
                   FaultPayload(problem))


def fault_findings(solver: Solver, runs: Runs) -> list[Finding]:
    """A finding for each of the model's faults, so that every
    command reports them the same way. It is no check and carries no
    `quotes`. A fault's finding kind is its own kind
    (`Kind(problem.kind)`): the undecided one outside `FAILING`, every
    other inside it."""
    return [finding_of(p) for p in solver.problems]
