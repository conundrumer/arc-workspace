"""What `record` computes for an entry: the `witness --try` survey."""

from dataclasses import dataclass, replace

from checker.branches.witnesses import runs_with_entry, solver_with_entry
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
from solver.witness import Entry
from solver.witness_groups import grouped

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
    `record` would write it, the cases its groups were built from, which
    are the cases witnessed with it, the unseparated and the subsumed
    branch differences of the report whose pairs it would reduce, and the
    subsumed branch differences the cases it newly witnesses bring."""

    entry: Entry
    cases: tuple[Case, ...]
    of: int
    """How many cases the solver has."""
    unseparated: tuple[Narrowed, ...]
    subsumed: tuple[Narrowed, ...]
    brought: tuple[Finding, ...]
    """The subsumed branch differences `witness` reports with the entry in
    the file, each subsumed case with its nearest subsumer, whose pair no
    subsumed branch difference without it has."""


@quotes("procedure.md", "Witness",
        "The cases' clauses differ and some input separates them: build the "
        "witness that shows it.")
def survey_witness_try(solver: Solver, runs: Runs, entry: Entry
                       ) -> TryResult | RunFailure | Fault:
    """The `witness --try` survey: the report's unseparated and subsumed
    branch differences (`check_equivalence`, `check_subsumption`), each
    with the count of its pairs that stay with `entry` added to the
    witness file, where that is fewer than it has; the subsumed branch
    differences with `entry` added whose pair none without it has; the
    entry's groups as `record` builds them, on the cases witnessed with
    it. It writes nothing. The first run on the entry that gives no
    result, where one does.
    It serves the Witness step that resolves a pair no witness separates or a
    subsumed case by building "the witness that shows it"
    (docs/handbook/procedure.md#witness): it shows whether a candidate input
    would."""
    with_entry, outcomes = runs_with_entry(runs, entry)
    if not isinstance(outcomes, tuple):
        return outcomes
    entry = replace(entry, output=grouped(solver, outcomes))
    tried = solver_with_entry(solver, entry)
    after = with_entry.sharing(tried, kept=runs.kept)
    before_u = unseparated_findings(solver, runs)
    after_u = unseparated_findings(tried, after, every=True)
    before_s = subsumed_findings(solver, runs)
    after_s = subsumed_findings(tried, after, every=True)

    def pair(f: Finding) -> tuple[object, object]:
        p = f.payload
        assert isinstance(p, UnseparatedPayload | SubsumedPayload)
        return (p.a, p.b)

    def pairs(f: Finding) -> int:
        p = f.payload
        assert isinstance(p, UnseparatedPayload | SubsumedPayload)
        return len(p.contexts.cases)

    def narrowed(before: list[Finding], now: list[Finding]
                 ) -> tuple[Narrowed, ...]:
        left: dict[tuple[object, object], int] = {}
        for f in now:
            a, b = pair(f)
            left[(a, b)] = pairs(f)
            if f.kind is Kind.UNSEPARATED:
                left[(b, a)] = pairs(f)
        out: list[Narrowed] = []
        for f in before:
            n = left.get(pair(f), 0)
            if n < pairs(f):
                out.append(Narrowed(f, n))
        return tuple(out)

    held = {pair(f) for f in subsumed_findings(solver, runs, every=True)}
    return TryResult(entry, tuple(c for c, _g in outcomes), after.case_count,
                     narrowed(before_u, after_u), narrowed(before_s, after_s),
                     tuple(f for f in subsumed_findings(tried, after)
                           if pair(f) not in held))
