"""What `record` computes for an entry: the `witness --try` survey."""

from dataclasses import dataclass, replace

from checker.branches.witnesses import groups_of
from checker.case_conditions import subsumed_findings, unseparated_findings
from checker.finding import (
    Finding,
    Kind,
)
from checker.payloads.witness import (
    SubsumedPayload,
    UnseparatedPayload,
)
from checker.runs import Runs
from engine import (
    RunFailure,
)
from engine.quotes import quotes
from solver.aggregate import (
    Solver,
)
from solver.model import (
    Case,
)
from solver.problems import (
    Fault,
)
from solver.witness import (
    Entry,
    Groups,
    WitnessFile,
)

TRY_ID = "try"
"""The id of the candidate entry `witness --try` runs."""


@dataclass(frozen=True)
class Narrowed:
    """A finding of the `witness` report on the pairs of one branch
    difference, and how many of its pairs stay as they are with a
    candidate witness in the file."""

    finding: Finding
    left: int


@dataclass(frozen=True)
class TryResult:
    """What a candidate witness would change (`survey_witness_try`): the entry as
    `record` would write it, the cases its groups were built from, the
    unseparated and the subsumed branch differences of the report whose
    pairs it would reduce."""

    entry: Entry
    cases: tuple[Case, ...]
    of: int
    """How many cases the solver has."""
    unseparated: tuple[Narrowed, ...]
    subsumed: tuple[Narrowed, ...]


@quotes("procedure.md", "Witness",
        "The cases' clauses differ and some input separates them: build the "
        "witness that shows it.")
def survey_witness_try(solver: Solver, runs: Runs, entry: Entry
                       ) -> TryResult | RunFailure | Fault:
    """The `witness --try` survey: the report's unseparated and subsumed
    branch differences (`check_equivalence`, `check_subsumption`), each
    with the count of its pairs that stay with `entry` added to the
    witness file, where that is fewer than it has; the entry's groups as
    `record` builds them. It writes nothing. The first run on the entry
    that gives no result, where one does.
    It serves the Witness step that resolves a pair no witness separates or a
    subsumed case by building "the witness that shows it" (procedure.md, under
    "Witness"): it shows whether a candidate input would."""
    solver_cases = runs.cases_or_none
    groups = groups_of(solver, [(c, runs.outcome(entry, c))
                                for c in solver_cases])
    if not isinstance(groups, Groups):
        return groups
    entry = replace(entry, output=groups)
    tried = replace(solver, witness_file=WitnessFile(
        solver.task_id, (*runs.entries, entry)))
    after = runs.sharing(tried, kept=runs.kept)
    before_u = unseparated_findings(solver, runs)
    after_u = unseparated_findings(tried, after, every=True)
    before_s = subsumed_findings(solver, runs)
    after_s = subsumed_findings(tried, after, every=True)

    def narrowed(before: list[Finding], now: list[Finding]
                 ) -> tuple[Narrowed, ...]:
        left: dict[tuple[object, object], int] = {}
        for f in now:
            p = f.payload
            assert isinstance(p, UnseparatedPayload | SubsumedPayload)
            left[(p.a, p.b)] = len(p.contexts.cases)
            if f.kind is Kind.UNSEPARATED:
                left[(p.b, p.a)] = len(p.contexts.cases)
        out: list[Narrowed] = []
        for f in before:
            p = f.payload
            assert isinstance(p, UnseparatedPayload | SubsumedPayload)
            n = left.get((p.a, p.b), 0)
            if n < len(p.contexts.cases):
                out.append(Narrowed(f, n))
        return tuple(out)

    return TryResult(entry, tuple(solver_cases), runs.case_count,
                     narrowed(before_u, after_u), narrowed(before_s, after_s))
