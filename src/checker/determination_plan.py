"""The determination plan: which parameters need a determination relation,
from the proposer probe."""

import itertools
import math
from collections.abc import Iterable, Sequence
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
from checker.finding import AtLine
from checker.lint.bans import check_params_data
from checker.runs import BaseOrder, NoCases, NoTask, Runs, base_order
from checker.sweep import beyond_stored
from checker.variants import (
    Fails,
    TimedOut,
    pairs_of,
    same_profile,
    with_program,
)
from engine import Program, Row, RunFailure, Value
from engine.program import grid_lists
from engine.quotes import quotes
from solver.model import Base, Case, base_case
from solver.aggregate import Solver
from solver.readers import proposers_program
from arc.task import Example
from checker.judged import concept_case, verdict_case
from solver.annotations import VerdictWord
from solver.determine import (
    Determined,
    NoDetermine,
    determine,
    rigid_charts,
    stored_facts,
)
from solver.outcome import Grids
from solver.probe import Proposals, probe
from solver.variations import FixParam, variation
from solver.pair_runs import TaskSection
from solver.group_runs import at_once
from solver.per_case import parameter_reading, per_case, by_base, with_rows_at
from solver.value_order import row_key
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
    parent/child tables"); for parameters that store a value per case,
    their values at one case."""

    child: "PlanValue"
    parent: "PlanValue"


class DomainName(StrEnum):
    """The name a parameter's domain stands under among the proposers'
    verdicts."""

    DOMAIN = "domain"
    POSITION = "position-domain"


@dataclass(frozen=True)
class AtCase:
    """The value of a parameter that stores a value per case
    (`solver.per_case.PerCase`) at `base`; `order` is where the base stands
    among the bases (`checker.runs.base_order`)."""

    parameter: str
    base: Base
    order: BaseOrder

    @property
    def name(self) -> str:
        """The name of the base case of `base` (`solver.names.name`)."""
        return self.order.name

    @property
    def case(self) -> Case:
        """The base case of `base` (`solver.model.base_case`)."""
        return base_case(self.base)


type PlanValue = str | AtCase
"""A parameter's one value, by the parameter's name, or its value at a
case."""

type Subject = PlanValue | KeyedTable


def parameter_of(v: PlanValue) -> str:
    """The parameter a value is of."""
    return v if isinstance(v, str) else v.parameter


def by_parameter(values: Iterable[PlanValue]
                 ) -> dict[str, tuple[AtCase, ...] | None]:
    """Each parameter among `values`, in order of its first value, with
    its values at cases where it stores a value per case; None for a
    parameter's one value."""
    at: dict[str, list[AtCase] | None] = {}
    for v in values:
        if isinstance(v, str):
            at[v] = None
        else:
            held = at.setdefault(v.parameter, [])
            assert held is not None
            held.append(v)
    return {p: None if vs is None else tuple(vs) for p, vs in at.items()}


def at_case(solver: Solver, parameter: str, base: Base) -> AtCase:
    """The value of `parameter`, which stores a value per case, at
    `base`."""
    return AtCase(parameter, base, base_order(solver, base))


def value_order(v: PlanValue) -> tuple[str, BaseOrder | None]:
    """The order values are listed in: by parameter, and a parameter's
    values at its cases in the order of the bases
    (`checker.runs.base_order`). A parameter's values are all its one
    value or all values at cases."""
    if isinstance(v, str):
        return v, None
    return v.parameter, v.order


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


@dataclass(frozen=True)
class MultiFact:
    """A parameter value whose stored value holds more than one fact, so
    the plan gives it no domain of its own."""


type Candidates = Narrowed | Enumerable
type Covering = Exact | Candidates


@dataclass(frozen=True)
class ProbeResult:
    """Each proposer's verdict on one subject, in proposer name order, and
    a single-fact parameter's own domain; `None` where the subject is a
    single-fact value of types that are not enumerable, or a keyed
    table."""

    subject: Subject
    verdicts: tuple[tuple[str, Verdict], ...]
    domain: Enumerable | MultiFact | None

    def entries(self) -> list[tuple[str, Verdict | Enumerable]]:
        """The verdicts, then the domain under its name."""
        out: list[tuple[str, Verdict | Enumerable]] = list(self.verdicts)
        if isinstance(self.domain, Enumerable):
            out.append((DomainName.POSITION if self.domain.position
                        else DomainName.DOMAIN, self.domain))
        return out


@dataclass(frozen=True)
class Settled:
    """One enumerated parameter's values in the joint enumeration: its
    stored rows, the values an assignment that reproduces every train pair
    holds, and each other value only an assignment whose run gave no result
    holds."""

    stored: tuple[Row, ...]
    surviving: tuple[Row, ...]
    unjudged: tuple[Row, ...]

    def extras(self) -> list[Row]:
        """The surviving values beyond the stored rows (`beyond_stored`)."""
        return beyond_stored(self.surviving, self.stored)


@dataclass(frozen=True)
class Joint:
    """The joint enumeration of the parameters whose own domain settles
    them: the assignments judged, how many reproduce every train pair,
    each parameter's values, and each assignment whose run reached a
    limit."""

    tried: int
    survived: int
    values: tuple[tuple[PlanValue, Settled], ...]
    timed_out: tuple[tuple[tuple[tuple[PlanValue, Row], ...], TimedOut], ...]


@dataclass(frozen=True)
class Plan:
    """The probe's results, the rule-derived parameters that hold data,
    the determined parameters with the chart of each that a RIGID call
    binds (`solver.determine.rigid_charts`), the column types of each
    parameter, and
    the joint enumeration: None where none ran, the run of the stored
    values where it reached a limit."""

    results: tuple[ProbeResult, ...]
    embedded: tuple[str, ...]
    determined: frozenset[str]
    differing: frozenset[PlanValue] | RunFailure
    """The values the determination run gives other than as stored
    (`_differing`); the run's failure where it gives no result."""
    types: tuple[tuple[PlanValue, tuple[str, ...]], ...]
    joint: Joint | TimedOut | None
    moved: "tuple[Moved, ...] | RunFailure"
    """The witnesses whose pair moves a determined value
    (`_moved_by_witnesses`); the failure of a determination run where one
    gives no result."""


@dataclass(frozen=True)
class ProbeFails:
    """The proposer probe's run gave no result."""

    failure: RunFailure


type PlanResult = Plan | ProbeFails | NoCases


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
                  fact: dict[PlanValue, tuple[tuple[str, ...], set[Row]]]
                  ) -> list[tuple[KeyedTable, tuple[str, ...], set[Row]]]:
    """Each set-keyed relation among the fact parameters: two values
    whose first column is an `Ident`, each a parameter's one value or its
    value at one case (`PlanValue`), which hold one set of ids no other
    value at that case holds, the parent one fact per id and the child
    more than one for some id. A member's place is left out of the row
    where every id's members stand at the same places and hold other
    fields."""
    by_ids: dict[tuple[Case | None, frozenset[Value]], list[PlanValue]] = {}
    for p, (types, stored) in fact.items():
        if types and types[0] == IDENT:
            case = None if isinstance(p, str) else p.case
            by_ids.setdefault((case, frozenset(r[0] for r in stored)),
                              []).append(p)
    out: list[tuple[KeyedTable, tuple[str, ...], set[Row]]] = []
    for (_case, ids), params in by_ids.items():
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


@dataclass(frozen=True)
class Classes:
    """The values of a plan by what each needs (`classify`)."""

    determine: list[PlanValue]
    settle: list[tuple[PlanValue, Candidates]]
    done: list[PlanValue]
    exact: list[PlanValue]
    unknown: list[PlanValue]
    undecided: list[PlanValue]


@quotes("solver-file.md", "Determination",
        "The determination relation of a parameter with a case column gives "
        "the rows of every case.")
def classify(results: Sequence[ProbeResult], determined: frozenset[str],
             differing: frozenset[PlanValue] | RunFailure) -> Classes:
    """A value is exact when a proposer reads it exactly, and settles when a
    candidate set covers it; when neither does, it needs a determination
    relation where its stored value is one fact, and is undecided where
    that value holds more, since the fit gives it; and it is done when a
    determination relation gives it. A value of a determined parameter
    that its relation gives other than as stored (`differing`) needs the
    relation, a value the parameter does not store among them; where the
    determination run gave no result, a value of a determined parameter is
    unknown. A keyed table a proposer reads exactly makes both its tables
    exact. A parameter has one determination relation, which gives the
    rows of every case: where one of its values needs it, each of its
    values needs it."""
    differs = differing if isinstance(differing, frozenset) else None
    determine: list[PlanValue] = []
    settle: list[tuple[PlanValue, Candidates]] = []
    done: list[PlanValue] = []
    exact: list[PlanValue] = []
    unknown: list[PlanValue] = []
    undecided: list[PlanValue] = []
    for r in results:
        p = r.subject
        if isinstance(p, KeyedTable):
            continue
        if parameter_of(p) in determined:
            (unknown if differs is None else determine if p in differs
             else done).append(p)
            continue
        cov = covering(r)
        if cov is None:
            (undecided if isinstance(r.domain, MultiFact)
             else determine).append(p)
        elif isinstance(cov[1], Exact):
            exact.append(p)
        else:
            settle.append((p, cov[1]))
    for r in results:
        t = r.subject
        if isinstance(t, KeyedTable) and any(isinstance(v, Exact)
                                             for _, v in r.verdicts):
            for part in (t.child, t.parent):
                for held in (determine, undecided):
                    if part in held:
                        held.remove(part)
                        exact.append(part)
    determine += [v for v in differs or () if v not in determine]
    whole = by_parameter(determine)
    determine += [v for v in (*exact, *(v for v, _c in settle), *done,
                              *undecided)
                  if parameter_of(v) in whole]
    exact = [v for v in exact if v not in determine]
    settle = [e for e in settle if e[0] not in determine]
    done = [v for v in done if v not in determine]
    undecided = [v for v in undecided if v not in determine]
    settle.sort(key=lambda e: (-e[1].count, value_order(e[0])))
    return Classes(sorted(determine, key=value_order), settle,
                   sorted(done, key=value_order),
                   sorted(exact, key=value_order),
                   sorted(unknown, key=value_order),
                   sorted(undecided, key=value_order))


@quotes("procedure.md", "Determine",
        "Run the plan (`uv run python scripts/run_dl.py determination-plan "
        "<task_id>`).")
def survey_determination_plan(solver: Solver, runs: Runs) -> PlanResult:
    """The plan: each fact parameter's stored value against each proposer of
    its type, a set-keyed relation's table against each proposer of its row
    type, and a single-fact enumerable parameter's own domain; then, where
    the parameters that their own domain settles have a joint product within
    the enumeration limit, the joint assignments that reproduce every train
    pair. A parameter that stores a value per case gives a subject per
    case, its value there (`AtCase`). A solver with no task file raises
    `ValueError`; the command refuses it first."""
    engine, limits = runs.engine, runs.limits
    task = solver.given_task
    proposals = probe(engine, task, limits)
    if not isinstance(proposals, Proposals):
        return ProbeFails(proposals)
    program = proposers_program(engine)
    if not isinstance(program, Program):
        raise ValueError("the proposers program the probe ran does not parse")
    known = {name: p.types for name, p in proposers(engine, program).items()}

    lib = solver.lib

    fact: dict[PlanValue, tuple[tuple[str, ...], set[Row]]] = {}
    bases = runs.bases
    for p in solver.params.parameters:
        pc = parameter_reading(solver, p.name)
        if not pc.types:
            continue
        got = by_base(solver, pc, stored_facts(runs.engine, solver, p), bases)
        if not isinstance(got, list):
            return NoCases(got)
        for base, at in got:
            if at:
                key = p.name if base is None else at_case(solver, p.name, base)
                fact[key] = (pc.value_types, set(pc.values(at)))
    results: list[ProbeResult] = []
    for name, (types, stored) in fact.items():
        single = len(stored) == 1
        if not enumerable(types, lib):
            results.append(ProbeResult(name, (),
                                       None if single else MultiFact()))
            continue
        domains = param_domains(types, sorted(stored, key=row_key), task, lib)
        verdicts: list[tuple[str, Verdict]] = []
        for prop in sorted(proposals.values):
            if known[prop] != types:
                continue
            cand = set(proposals.values[prop])
            verdicts.append((prop, _column_verdict(cand, stored,
                                                   len(domains[0]))
                             if len(types) == 1
                             else _table_verdict(cand, stored)))
        domain = Enumerable(
            math.prod(len(d) for d in domains),
            any(column_domain(t, lib) == ColumnDomain.POSITION
                for t in types)) if single else MultiFact()
        results.append(ProbeResult(name, tuple(verdicts), domain))
    for table, types, rows in _keyed_tables(solver, fact):
        tv = tuple((prop, _table_verdict(set(proposals.values[prop]), rows))
                   for prop in sorted(proposals.values)
                   if known.get(prop) == types)
        if tv:
            results.append(ProbeResult(table, tv, None))

    embedded = sorted(_embedded(solver, runs))
    charts = rigid_charts(solver)
    placed = frozenset(p.name for p in solver.params.parameters
                       if p.determined)
    determined = placed | {charts[n] for n in placed if n in charts}
    differing = _differing(solver, runs, determined, charts)
    if isinstance(differing, NoCases):
        return differing
    all_types = tuple((n, t) for n, (t, _) in fact.items())
    joint = _joint(solver, runs, results, determined, differing, fact)
    return Plan(tuple(results), tuple(embedded), determined, differing,
                all_types, joint, _moved_by_witnesses(solver, runs))


@dataclass(frozen=True)
class Moved:
    """A witness whose pair, added to the train pairs, gives `parameter`'s
    determination a value other than the stored one."""

    witness: str
    parameter: str


def _concept_pairs(solver: Solver, runs: Runs) -> list[tuple[str, Example]]:
    """Each witness, once, in the order of its first line, that stands at
    the stored assignment (no `assign`), whose verdict on some line
    denotes the concept case's model or is `any`, and on whose input the
    concept case gives one grid: its id, and its input with that grid."""
    concept = concept_case(solver, runs.cases_or_none)
    if concept is None:
        return []
    out: list[tuple[str, Example]] = []
    for w in solver.annotations.witnesses:
        entry = runs.entry(w.id)
        if entry is None or entry.assign or any(i == w.id for i, _ in out):
            continue
        if w.verdict != VerdictWord.ANY and verdict_case(
                solver, w.verdict, runs.cases_or_none, None) != concept:
            continue
        got = runs.outcome(entry, concept)
        if isinstance(got, Grids) and len(got.grids) == 1:
            out.append((w.id, Example(grid_lists(entry.input),
                                            grid_lists(got.grids[0]))))
    return out


def _moved_by_witnesses(solver: Solver, runs: Runs
                        ) -> tuple[Moved, ...] | RunFailure:
    """The determination run with every concept pair (`_concept_pairs`)
    added to the train pairs; where it moves a determined value, one run
    per pair, each pair and parameter whose value it moves."""
    pairs = _concept_pairs(solver, runs)
    if not pairs:
        return ()

    def diffs(added: Sequence[Example]) -> list[str] | RunFailure | None:
        got = determine(runs.engine, solver, runs.limits, added=added)
        if isinstance(got, NoDetermine):
            return None
        if not isinstance(got, Determined):
            return got
        return [d.parameter for d in got.diffs]

    every = diffs([p for _, p in pairs])
    if not isinstance(every, list):
        return () if every is None else every
    if not every:
        return ()
    moved: list[Moved] = []
    for wid, pair in pairs:
        one = diffs([pair])
        if not isinstance(one, list):
            return () if one is None else one
        moved += [Moved(wid, param) for param in one]
    return tuple(moved)


def _differing(solver: Solver, runs: Runs, determined: frozenset[str],
               charts: dict[str, str]
               ) -> frozenset[PlanValue] | RunFailure | NoCases:
    """The values of the determined parameters that the determination
    run gives other than as stored, a diff of a relation a RIGID call
    binds under its chart of `charts`: a parameter's one value, or its value
    at each base where a row of its diff holds
    (`checker.runs.Runs.differing_bases`), a base it stores no rows at
    among them; the run's failure where it gives no result, and the
    failure of the run that enumerates the solver's cases, which those
    bases are read from, where that run gives none. Raises
    `ValueError` where a determined parameter stands and the run reports
    no `Determine` comp or no task file, which the parameter and the
    command's refusal rule out."""
    if not determined:
        return frozenset()
    got = runs.determined
    if isinstance(got, (NoDetermine, NoTask)):
        raise ValueError(f"{solver.stem}: a determined parameter and no "
                         "determination run")
    if not isinstance(got, Determined):
        return got
    out: set[PlanValue] = set()
    for d in got.diffs:
        name = charts.get(d.parameter, d.parameter)
        bases = runs.differing_bases(d)
        if bases is None:
            out.add(name)
            continue
        if not isinstance(bases, tuple):
            return NoCases(bases)
        out |= {at_case(solver, name, b) for b in bases}
    return frozenset(out)


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
           differing: frozenset[PlanValue] | RunFailure,
           fact: dict[PlanValue, tuple[tuple[str, ...], set[Row]]]
           ) -> Joint | TimedOut | None:
    """The parameters their own domain settles, enumerated jointly, as a
    produce run does; a parameter a proposer narrows keeps its stored
    value. None where none settles, where the joint product is over the
    limit, or where the stored values fail a train pair."""
    engine, limits = runs.engine, runs.limits
    task = solver.task
    assert task is not None
    settle = classify(results, determined, differing).settle
    if not settle or math.prod(v.count for _, v in settle) \
            > ENUMERATION_LIMIT:
        return None
    own = {p for p, v in settle if isinstance(v, Enumerable)}
    enumerated: list[tuple[PlanValue, list[Row]]] = []
    stored_rows: dict[PlanValue, tuple[Row, ...]] = {}
    for key in fact:
        if key not in own:
            continue
        types, stored = fact[key]
        srt = sorted(stored, key=row_key)
        stored_rows[key] = tuple(srt)
        domains = param_domains(types, srt, task, solver.lib)
        cands = candidate_rows(domains, srt)
        enumerated.append((key, cands))
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
        for name, rows in _written(solver, runs, [
                (key, row) for (key, _c), row
                in zip(enumerated, a, strict=True)]).items():
            s = with_program(s, variation(engine, s, FixParam(name, rows)))
        return same_profile(engine, s, runs.cases, train, limits, ref)

    got = at_once(test, assignments)
    surviving = [a for a, ok in zip(assignments, got, strict=True)
                 if ok is True]
    timed = [(a, ok) for a, ok in zip(assignments, got, strict=True)
             if isinstance(ok, TimedOut)]
    values: list[tuple[PlanValue, Settled]] = []
    for i, (name, _c) in enumerate(enumerated):
        kept = {a[i] for a in surviving}
        values.append((name, Settled(
            stored_rows[name],
            tuple(sorted(kept, key=row_key)),
            tuple(sorted({a[i] for a, _ in timed} - kept, key=row_key)))))
    return Joint(len(assignments) - len(timed), len(surviving),
                 tuple(values),
                 tuple((tuple((n, r) for (n, _c), r
                              in zip(enumerated, a, strict=True)), t)
                       for a, t in timed))


def _written(solver: Solver, runs: Runs, values: Sequence[tuple[PlanValue, Row]]
             ) -> dict[str, tuple[Row, ...]]:
    """The rows each parameter holds under an assignment of `values`: a
    parameter's one value as its one row, and its values at cases written
    into its stored rows, each at its case's base (`with_rows_at`)."""
    out: dict[str, tuple[Row, ...]] = {}
    for key, row in values:
        if isinstance(key, str):
            out[key] = (row,)
            continue
        pc = per_case(solver, key.parameter)
        p = solver.params.parameter(key.parameter)
        assert pc is not None and p is not None
        held = out.get(key.parameter,
                       tuple(stored_facts(runs.engine, solver, p)))
        out[key.parameter] = with_rows_at(solver, pc, held, key.base,
                                          (row,))
    return out
