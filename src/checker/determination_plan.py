"""The determination plan: which parameters need a determination relation,
from the proposer probe."""

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from checker.derive import proposers
from checker.domains import (
    ColumnDomain,
    candidate_rows,
    column_domain,
    enumerable,
    param_domains,
)
from checker.drop_one import stored_facts
from checker.finding import AtLine
from checker.lint.bans import check_params_data
from checker.runs import Runs
from checker.variants import (
    Fails,
    TimedOut,
    pairs_of,
    same_profile,
    with_program,
)
from engine import Program, Row, RunFailure, Value
from engine.quotes import quotes
from solver.model import Solver, proposers_program, resolved_types
from solver.solve import (
    FixParam,
    Proposals,
    TaskSection,
    at_once,
    probe,
    row_key,
    variation,
)
from solver.vocabulary import IDENT

ENUMERATION_LIMIT = 100
"""The joint candidate count a produce run may enumerate to settle
parameters by verification; over it, parameters move under determination
until the rest go under (procedure.md, under "Determine")."""


@dataclass(frozen=True)
class KeyedTable:
    """A relation keyed by a multiset of members, held as two tables
    joined by an id: `child` holds `(id, member fields)`, `parent` holds
    `(id, out fields)` (patterns.md, "Set-keyed relations via
    parent/child tables")."""

    child: str
    parent: str


class DomainName(StrEnum):
    """The name a parameter's domain stands under among the proposers'
    verdicts."""

    DOMAIN = "domain"
    POSITION = "position-domain"


type Subject = str | KeyedTable


@dataclass(frozen=True)
class Exact:
    """A proposal that is the stored value."""


@dataclass(frozen=True)
class Narrowed:
    """A one-column proposal that holds the stored value and is smaller
    than the column's domain: `count` candidates, the non-empty subsets of
    the proposal for a multi-fact value."""

    count: int


@dataclass(frozen=True)
class Open:
    """A one-column proposal that holds the stored value and is no smaller
    than the domain."""


@dataclass(frozen=True)
class Missed:
    """A proposal that leaves out part of the stored value, or a table
    proposal none of whose rows is stored."""


@dataclass(frozen=True)
class Empty:
    """A table proposal that holds no row."""


@dataclass(frozen=True)
class Superset:
    """A table proposal that holds every stored row and `extra` more."""

    extra: int


@dataclass(frozen=True)
class Partial:
    """A table proposal that holds some stored rows and leaves out
    others."""


type Verdict = Exact | Narrowed | Open | Missed | Empty | Superset | Partial


@dataclass(frozen=True)
class Enumerable:
    """A single-fact parameter's own value domain, of `count` values;
    `position` says a column's domain is a Box-record one."""

    count: int
    position: bool


type Candidates = Narrowed | Enumerable
type Covering = Exact | Candidates


@dataclass(frozen=True)
class ProbeResult:
    """Each proposer's verdict on one subject, in proposer name order, and
    a single-fact parameter's own domain."""

    subject: Subject
    verdicts: tuple[tuple[str, Verdict], ...]
    domain: Enumerable | None

    def entries(self) -> list[tuple[str, Verdict | Enumerable]]:
        """The verdicts, then the domain under its name."""
        out: list[tuple[str, Verdict | Enumerable]] = list(self.verdicts)
        if self.domain is not None:
            out.append((DomainName.POSITION if self.domain.position
                        else DomainName.DOMAIN, self.domain))
        return out


@dataclass(frozen=True)
class Settled:
    """One enumerated parameter's values in the joint enumeration: the
    values an assignment that reproduces every train pair holds, and each
    other value only an assignment whose run gave no result holds."""

    surviving: tuple[Row, ...]
    unjudged: tuple[Row, ...]


@dataclass(frozen=True)
class Joint:
    """The joint enumeration of the parameters whose own domain settles
    them: the assignments judged, how many reproduce every train pair,
    each parameter's values, and each assignment whose run reached a
    limit."""

    tried: int
    survived: int
    values: tuple[tuple[str, Settled], ...]
    timed_out: tuple[tuple[tuple[tuple[str, Row], ...], TimedOut], ...]


@dataclass(frozen=True)
class Plan:
    """The probe's results, the rule-derived parameters that hold data,
    the determined parameters, the column types of each parameter, and
    the joint enumeration: None where none ran, the run of the stored
    values where it reached a limit."""

    results: tuple[ProbeResult, ...]
    embedded: tuple[str, ...]
    determined: frozenset[str]
    types: tuple[tuple[str, tuple[str, ...]], ...]
    joint: Joint | TimedOut | None


@dataclass(frozen=True)
class ProbeFails:
    """The proposer probe's run gave no result."""

    failure: RunFailure


type PlanResult = Plan | ProbeFails


def _column_verdict(cand: set[Row], stored: set[Row], domain: int
                    ) -> Verdict:
    if not stored <= cand:
        return Missed()
    if cand == stored:
        return Exact()
    if len(cand) < domain:
        return Narrowed(len(cand) if len(stored) == 1
                        else 2 ** len(cand) - 1)
    return Open()


def _table_verdict(cand: set[Row], stored: set[Row]) -> Verdict:
    if cand == stored:
        return Exact()
    if not cand:
        return Empty()
    if stored < cand:
        return Superset(len(cand - stored))
    if cand & stored:
        return Partial()
    return Missed()


def _keyed_tables(solver: Solver,
                  fact: dict[str, tuple[tuple[str, ...], set[Row]]]
                  ) -> list[tuple[KeyedTable, tuple[str, ...], set[Row]]]:
    """Each set-keyed relation among the fact parameters: two parameters
    whose first column is an `Ident`, which hold one set of ids no other
    parameter holds, the parent one fact per id and the child more than
    one for some id. A member's place is left out of the row where every
    id's members stand at the same places and hold other fields."""
    by_ids: dict[frozenset[Value], list[str]] = {}
    for p, (types, stored) in fact.items():
        if types and types[0] == IDENT:
            by_ids.setdefault(frozenset(r[0] for r in stored), []).append(p)
    out: list[tuple[KeyedTable, tuple[str, ...], set[Row]]] = []
    for ids, params in by_ids.items():
        if len(params) != 2:
            continue
        parents = [p for p in params if len(fact[p][1]) == len(ids)]
        if len(parents) != 1:
            continue
        parent = parents[0]
        child = next(p for p in params if p != parent)
        ctypes, crows = fact[child]
        ptypes, prows = fact[parent]
        members: dict[Value, list[Row]] = {}
        for row in sorted(crows, key=row_key):
            members.setdefault(row[0], []).append(row)
        at = [i for i, t in enumerate(ctypes) if t in solver.lib.box_types]
        fields = [i for i in range(1, len(ctypes)) if i not in at]
        places = {tuple(tuple(m[i] for i in at) for m in ms)
                  for ms in members.values()}
        kept = (fields if fields and len(places) == 1
                else list(range(1, len(ctypes))))
        outs = {row[0]: row[1:] for row in prows}
        typed: set[tuple[str, ...]] = set()
        rows: set[Row] = set()
        for key, ms in members.items():
            typed.add(tuple(ctypes[i] for _m in ms for i in kept)
                      + tuple(ptypes[1:]))
            rows.add(tuple(m[i] for m in ms for i in kept) + outs[key])
        if len(typed) == 1:
            out.append((KeyedTable(child, parent), typed.pop(), rows))
    return out


def covering(result: ProbeResult) -> tuple[str, Covering] | None:
    """The verdict that covers the subject's value, with its name: the
    proposal that reads it exactly, or the smallest candidate set, the
    first on a tie; None where none covers it."""
    best: tuple[int, str, Covering] | None = None
    for name, v in result.entries():
        match v:
            case Exact():
                size = 0
            case Narrowed(count=count) | Enumerable(count=count):
                size = count
            case _:
                continue
        if best is None or size < best[0]:
            best = (size, name, v)
    return None if best is None else (best[1], best[2])


def classify(results: Sequence[ProbeResult], determined: frozenset[str]
             ) -> tuple[list[str], list[tuple[str, Candidates]], list[str],
                        list[str]]:
    """(determine, settle, done, exact): a parameter is exact when a
    proposer reads it exactly, settles when a candidate set covers it,
    needs a determination relation when neither, and is done when a
    determination relation already holds it. A keyed table a proposer
    reads exactly makes both its tables exact."""
    determine: list[str] = []
    settle: list[tuple[str, Candidates]] = []
    done: list[str] = []
    exact: list[str] = []
    for r in results:
        p = r.subject
        if isinstance(p, KeyedTable):
            continue
        if p in determined:
            done.append(p)
            continue
        cov = covering(r)
        if cov is None:
            determine.append(p)
        elif isinstance(cov[1], Exact):
            exact.append(p)
        else:
            settle.append((p, cov[1]))
    for r in results:
        t = r.subject
        if isinstance(t, KeyedTable) and any(isinstance(v, Exact)
                                             for _, v in r.verdicts):
            for part in (t.child, t.parent):
                if part in determine:
                    determine.remove(part)
                    exact.append(part)
    settle.sort(key=lambda e: (-e[1].count, e[0]))
    return sorted(determine), settle, sorted(done), sorted(exact)


@quotes("procedure.md", "Determine",
        "Run the plan (`uv run python scripts/run_dl.py determination-plan "
        "<task_id>`).")
def survey_determination_plan(solver: Solver, runs: Runs) -> PlanResult:
    """The plan: each fact parameter's stored value against each proposer of
    its type, a set-keyed relation's table against each proposer of its row
    type, and a single-fact enumerable parameter's own domain; then, where
    the parameters that their own domain settles have a joint product within
    the enumeration limit, the joint assignments that reproduce every train
    pair. A solver with no task file raises `ValueError`; the command
    refuses it first."""
    engine, limits = runs.engine, runs.limits
    task = solver.given_task
    proposals = probe(engine, task, limits)
    if not isinstance(proposals, Proposals):
        return ProbeFails(proposals)
    program = proposers_program(engine)
    if not isinstance(program, Program):
        raise ValueError("the proposers program the probe ran does not parse")
    known = {name: p.types for name, p in proposers(program).items()}

    def resolved(types: tuple[str, ...]) -> tuple[str, ...]:
        return resolved_types(solver.program, types)

    lib = solver.lib

    fact: dict[str, tuple[tuple[str, ...], set[Row]]] = {}
    for p in solver.params.parameters:
        types = tuple(c.type for c in p.columns)
        if not types:
            continue
        rows = stored_facts(solver, runs, p)
        if rows:
            fact[p.name] = (types, set(rows))
    results: list[ProbeResult] = []
    for name, (types, stored) in fact.items():
        if not enumerable(types, lib):
            results.append(ProbeResult(name, (), None))
            continue
        domains = param_domains(types, sorted(stored, key=row_key), task, lib)
        verdicts: list[tuple[str, Verdict]] = []
        for prop in sorted(proposals.values):
            if known[prop] != resolved(types):
                continue
            cand = set(proposals.values[prop])
            verdicts.append((prop, _column_verdict(cand, stored,
                                                   len(domains[0]))
                             if len(types) == 1
                             else _table_verdict(cand, stored)))
        domain = None
        if len(stored) == 1:
            domain = Enumerable(
                math.prod(len(d) for d in domains),
                any(column_domain(t, lib) == ColumnDomain.POSITION
                    for t in types))
        results.append(ProbeResult(name, tuple(verdicts), domain))
    for table, types, rows in _keyed_tables(solver, fact):
        tv = tuple((prop, _table_verdict(set(proposals.values[prop]), rows))
                   for prop in sorted(proposals.values)
                   if known.get(prop) == resolved(types))
        if tv:
            results.append(ProbeResult(table, tv, None))

    embedded = sorted(_embedded(solver, runs))
    determined = frozenset(p.name for p in solver.params.parameters
                           if p.determined)
    all_types = tuple((n, t) for n, (t, _) in fact.items())
    joint = _joint(solver, runs, results, determined, fact)
    return Plan(tuple(results), tuple(embedded), determined, all_types,
                joint)


def _embedded(solver: Solver, runs: Runs) -> set[str]:
    """The rule-derived parameters whose rules write a value as a
    literal (the lint's `params data`)."""
    fired = {uid for f in check_params_data(solver, runs)
             if isinstance(f.where, AtLine) for uid in f.where.units}
    names = {p.name for p in solver.params.parameters if p.columns}
    return {u.head.relation.name for u in solver.program.units
            if u.id in fired and not u.head.relation.instances
            and u.head.relation.name in names}


def _joint(solver: Solver, runs: Runs, results: Sequence[ProbeResult],
           determined: frozenset[str],
           fact: dict[str, tuple[tuple[str, ...], set[Row]]]
           ) -> Joint | TimedOut | None:
    """The parameters their own domain settles, enumerated jointly, as a
    produce run does; a parameter a proposer narrows keeps its stored
    value. None where none settles, where the joint product is over the
    limit, or where the stored values fail a train pair."""
    engine, limits = runs.engine, runs.limits
    task = solver.task
    assert task is not None
    _d, settle, _done, _exact = classify(results, determined)
    if not settle or math.prod(v.count for _, v in settle) \
            > ENUMERATION_LIMIT:
        return None
    own = {p for p, v in settle if isinstance(v, Enumerable)}
    enumerated: list[tuple[str, list[Row]]] = []
    for p in solver.params.parameters:
        if p.name not in own:
            continue
        types, stored = fact[p.name]
        srt = sorted(stored, key=row_key)
        domains = param_domains(types, srt, task, solver.lib)
        cands = candidate_rows(domains, srt)
        enumerated.append((p.name, cands))
    if not enumerated:
        return None
    assignments = list(itertools.product(*(c for _, c in enumerated)))
    if len(assignments) > ENUMERATION_LIMIT:
        return None
    train = pairs_of(solver, (TaskSection.TRAIN,))
    reference = runs.train_profile
    if isinstance(reference, TimedOut):
        return reference
    if isinstance(reference, Fails):
        return None
    ref = reference

    def test(a: tuple[Row, ...]) -> bool | TimedOut:
        s = solver
        for (name, _c), row in zip(enumerated, a, strict=True):
            s = with_program(s, variation(engine, s, FixParam(name, (row,))))
        return same_profile(engine, s, runs.cases, train, limits, ref)

    got = at_once(test, assignments)
    surviving = [a for a, ok in zip(assignments, got, strict=True)
                 if ok is True]
    timed = [(a, ok) for a, ok in zip(assignments, got, strict=True)
             if isinstance(ok, TimedOut)]
    values: list[tuple[str, Settled]] = []
    for i, (name, _c) in enumerate(enumerated):
        kept = {a[i] for a in surviving}
        values.append((name, Settled(
            tuple(sorted(kept, key=row_key)),
            tuple(sorted({a[i] for a, _ in timed} - kept, key=row_key)))))
    return Joint(len(assignments) - len(timed), len(surviving),
                 tuple(values),
                 tuple((tuple((n, r) for (n, _c), r
                              in zip(enumerated, a, strict=True)), t)
                       for a, t in timed))
