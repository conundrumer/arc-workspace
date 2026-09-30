"""The sweep survey: for each parameter, the values of its domain that
reproduce every train pair, and what the test pairs say of the others."""

import itertools
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from checker.domains import enumerable, param_domains, row_key
from checker.drop_one import stored_facts
from checker.runs import Runs
from checker.variants import (
    Entry,
    Fails,
    OnTest,
    Profile,
    TestVerdict,
    TimedOut,
    pairs_of,
    parallel,
    profile,
    test_reference,
    test_verdicts,
    with_program,
    workers,
)
from engine import Program, Row, RunFailure
from solver.annotations import CaseMarker
from solver.model import (
    Case,
    DerivedRelation,
    Parameter,
    Solver,
    UnderMarker,
    Unmarked,
    lists_case,
)
from solver.names import lists
from solver.names import name as case_label
from solver.solve import (
    Determined,
    FixParam,
    determine,
    rigid_charts,
    variation,
)
from solver.solve import candidates as pair_candidates
from solver.vocabulary import NUMBER

MAX_CANDIDATES = 256
"""The most candidates tried per parameter; beyond it, only the
candidates one change from the stored facts."""
TIME_LIMIT_SECONDS = 180.0


class NotSwept(StrEnum):
    """Why a parameter is not swept, where no run is the reason."""

    DERIVED = "derived"
    NO_FACTS = "0 facts"
    NON_ENUMERABLE = "non-enumerable"
    TIME_LIMIT = "time limit"
    FAILS_TRAIN = "stored value fails train"


@dataclass(frozen=True)
class RunFailed:
    """A run the sweep of a parameter needs failed."""

    failure: RunFailure


type SkipReason = NotSwept | RunFailed | TimedOut


@dataclass(frozen=True)
class Skipped:
    parameter: str
    types: tuple[str, ...]
    reason: SkipReason


@dataclass(frozen=True)
class Near:
    """A sweep of the candidates one change from the stored facts: `swept`
    of the `whole` candidate set."""

    swept: int
    whole: int


@dataclass(frozen=True)
class Cut:
    """A sweep the time limit cut: `ran` of the `whole` candidates."""

    ran: int
    whole: int


type SetValue = frozenset[Row]


@dataclass(frozen=True)
class Gaps[V]:
    """The values the pairs reproduce only because no case the marker
    marks is defined on every train pair: the marker, and each such value
    with whether those cases give nothing on every pair."""

    marker: CaseMarker
    undefined: tuple[tuple[V, bool], ...]


@dataclass(frozen=True)
class Extras[V]:
    """The values train admits beyond the stored ones, in order, each with
    its test verdict."""

    verdicts: tuple[tuple[V, TestVerdict], ...]

    @property
    def values(self) -> list[V]:
        return [v for v, _ in self.verdicts]

    def group(self, on: OnTest) -> list[V]:
        return [v for v, t in self.verdicts if t == on]

    @property
    def timed(self) -> list[tuple[V, TimedOut]]:
        return [(v, t) for v, t in self.verdicts if isinstance(t, TimedOut)]


@dataclass(frozen=True)
class ValueSweep:
    """A parameter swept value by value: each value is one row."""

    parameter: str
    types: tuple[str, ...]
    fitting: tuple[Row, ...]
    stored: tuple[Row, ...]
    extras: Extras[Row]
    scope: Near | Cut | None
    gaps: Gaps[Row] | None
    timed: tuple[tuple[Row, TimedOut], ...]

    def admits_stored_alone(self) -> bool:
        """The values the pairs admit are the stored rows: a value is
        admitted where the program under it gives the stored program's
        profile (`checker.variants.profile`), which is no Fit judgment."""
        return set(self.fitting) == set(self.stored)

    def settles(self) -> bool:
        return (self.admits_stored_alone() and self.scope is None
                and not self.timed and not self.extras.timed)


@dataclass(frozen=True)
class SetSweep:
    """A parameter whose facts fit only together, swept as one set."""

    parameter: str
    types: tuple[str, ...]
    fitting: tuple[SetValue, ...]
    stored: tuple[Row, ...]
    extras: Extras[SetValue]
    scope: Near | Cut | None
    gaps: Gaps[SetValue] | None
    timed: tuple[tuple[SetValue, TimedOut], ...]

    def admits_stored_alone(self) -> bool:
        """The one set the pairs admit is the stored set (`ValueSweep`)."""
        return set(self.fitting) == {frozenset(self.stored)}

    def settles(self) -> bool:
        return (self.admits_stored_alone() and self.scope is None
                and not self.timed and not self.extras.timed)


@dataclass(frozen=True)
class CaseSets:
    """A parameter every case reads, whose cases admit different values:
    each case's admitted values, and the candidates run."""

    parameter: str
    types: tuple[str, ...]
    per_case: tuple[tuple[Case, frozenset[Row]], ...]
    domain: frozenset[Row]


@dataclass(frozen=True)
class NoCaseMarker:
    """A marker in `Params` that lists no case, with the parameters under
    it (solver-file.md:104-107)."""

    marker: CaseMarker
    parameters: tuple[str, ...]


type SweepEntry = ValueSweep | SetSweep | CaseSets | Skipped | NoCaseMarker


@dataclass(frozen=True)
class SweepReport:
    """The entries in declaration order; the parameters whose
    determination reproduces the stored value; the time limit and the
    seconds the sweep took."""

    entries: tuple[SweepEntry, ...]
    determined: frozenset[str]
    time_limit: float
    elapsed: float


class _Clock:
    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self.start = time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self.start

    def spent(self) -> bool:
        return self.elapsed() >= self.seconds


def _passing(entry: Entry, accepted: Sequence[frozenset[object]]
             ) -> frozenset[Case]:
    """The branchless cases whose grids are a candidate of the pair."""
    return frozenset(c for c, g in entry
                     if not c.branches and frozenset(g) in accepted)


def _coordinate(stored: list[Row], domains: list[list[object]], limit: int
                ) -> list[Row]:
    """The rows one column change from the stored rows, the stored rows
    first, one per (stored row, column) in turn, `limit` at most."""
    rows = list(dict.fromkeys(stored))
    seen = set(rows)
    slices = [[row[:i] + (value,) + row[i + 1:] for value in domain]
              for row in rows for i, domain in enumerate(domains)]
    for step in itertools.zip_longest(*slices):
        for row in step:
            if row is None or row in seen:
                continue
            if len(rows) >= limit:
                return rows
            rows.append(row)  # type: ignore[arg-type]
            seen.add(row)  # type: ignore[arg-type]
    return rows


def _neighborhood(stored: list[Row], singles: list[Row], limit: int
                  ) -> list[SetValue]:
    """The sets one row change from the stored set, `limit` at most."""
    stored_set = frozenset(stored)
    sets = [stored_set]
    seen = {stored_set}
    changes: list[list[SetValue]] = []
    for row in dict.fromkeys(stored):
        rest = stored_set - {row}
        changes.append([rest] + [rest | {v} for v in singles])
    changes.append([stored_set | {v} for v in singles])
    for step in itertools.zip_longest(*changes):
        for value in step:
            if not value or value in seen:
                continue
            if len(sets) >= limit:
                return sets
            sets.append(value)
            seen.add(value)
    return sets


def _marked(solver: Solver, marker: CaseMarker, solver_cases: Sequence[Case]
            ) -> frozenset[Case]:
    """The solver's cases a marker marks: those whose base a part of it
    lists (`solver.names.lists`)."""
    return frozenset(c for c in solver_cases
                     if any(lists(solver, p, c.base) for p in marker.parts))


class _Sweeper:
    def __init__(self, solver: Solver, runs: Runs, clock: _Clock) -> None:
        self.solver = solver
        self.runs = runs
        self.engine = runs.engine
        self.limits = runs.limits
        self.clock = clock
        self.train = pairs_of(solver, ("train",))
        self.accepted = [[a for _, a in pair_candidates(ex)]
                         for _, ex in self.train]
        self._test_ref: Profile | Fails | TimedOut | None = None

    def test_ref(self) -> Profile | Fails | TimedOut:
        if self._test_ref is None:
            self._test_ref = test_reference(self.engine, self.solver,
                                            self.limits)
        return self._test_ref

    def program(self, param: str, rows: Sequence[Row]) -> Program:
        return variation(self.engine, self.solver,
                         FixParam(param, tuple(rows)))

    def run(self, param: str, rows: Sequence[Row], reference: Profile,
            keep_all: bool) -> Profile | Fails | TimedOut:
        return profile(self.engine,
                       with_program(self.solver, self.program(param, rows)),
                       self.train, self.limits,
                       None if keep_all else reference, held=False)

    def chunks[V](self, values: list[V], fn: Callable[[V], object],
                  first: bool) -> tuple[list[object], int]:
        """`fn` over `values` in order, as many at once as `parallel` runs,
        each value started only while the clock has time left, save the
        first `workers()` values where `first`; a value starts as soon as
        one before it ends, so no run waits on a slower one. The values
        that started are a prefix of `values`: their results, and their
        count."""
        size = workers()
        lock = threading.Lock()
        started = [0]
        results: list[object] = [None] * len(values)

        def claim() -> int | None:
            with lock:
                i = started[0]
                if i >= len(values):
                    return None
                if not (first and i < size) and self.clock.spent():
                    return None
                started[0] = i + 1
                return i

        def work() -> None:
            while (i := claim()) is not None:
                results[i] = fn(values[i])

        with ThreadPoolExecutor(max_workers=size) as pool:
            for f in [pool.submit(work) for _ in range(min(size, len(values)))]:
                f.result()
        return results[:started[0]], started[0]

    def gaps[V](self, marker: CaseMarker | None, extras: list[V],
                program_of: Callable[[V], Program]
                ) -> Gaps[V] | RunFailure | TimedOut | None:
        """The extras at which no case the marker marks gives grids on
        every train pair; None where the parameter stands under no marker
        or the marked cases give none on some pair at the stored value
        too."""
        if marker is None or not extras:
            return None
        solver_cases = self.runs.cases
        if not isinstance(solver_cases, tuple):
            return solver_cases
        marked = _marked(self.solver, marker, solver_cases)

        def reading(program: Program) -> list[frozenset[Case]] | Fails \
                | TimedOut:
            got = profile(self.engine, with_program(self.solver, program),
                          self.train, self.limits, held=False)
            if not isinstance(got, tuple):
                return got
            return [frozenset(c for c, _ in e if c in marked) for e in got]

        base = reading(self.solver.program)
        if isinstance(base, TimedOut):
            return base
        if isinstance(base, Fails) or not frozenset.intersection(*base):
            return None
        runs = parallel(lambda v: reading(program_of(v)), extras)
        undefined: list[tuple[V, bool]] = []
        for v, r in zip(extras, runs, strict=True):
            if isinstance(r, TimedOut):
                return r
            if isinstance(r, Fails):
                if r.failure is not None:
                    return r.failure
                continue
            if not frozenset.intersection(*r):
                undefined.append((v, not any(r)))
        return Gaps(marker, tuple(undefined)) if undefined else None


def _marker_of(p: Parameter) -> CaseMarker | None:
    return p.section.marker if isinstance(p.section, UnderMarker) else None


def survey_sweep(solver: Solver, runs: Runs,
                 max_candidates: int = MAX_CANDIDATES,
                 time_limit: float = TIME_LIMIT_SECONDS) -> SweepReport:
    """Each enumerable parameter swept one at a time, the others at their
    stored values: a value fits where it reproduces the stored program's
    profile on every train pair (principles.md:54, a stored assignment
    determined by the evidence; the audit's sweep section,
    procedure.md:138). Fitting values beyond the stored ones run on the
    test pairs. A parameter whose facts fit only together sweeps as one
    set. Above the cap, the candidates one change from the stored facts.
    The parameters run cheapest first, and a spent time limit cuts the
    parameter in flight and leaves the rest unswept. A value the pairs
    reproduce only because the cases that read the parameter give nothing
    leaves the fitting values, and the result states it. A parameter
    every case reads also reports each case's admitted values, where they
    differ."""
    clock = _Clock(time_limit)
    got = determine(runs.engine, solver, runs.limits)
    determined = frozenset(got.reproduced) if isinstance(got, Determined) \
        else frozenset()
    task = solver.task
    lib = solver.lib
    entries: list[tuple[int, int, SweepEntry]] = []
    prepared: list[tuple[int, Parameter, str,
                         tuple[str, ...], list[Row], list[Row],
                         Near | None]] = []
    no_case: dict[CaseMarker, list[tuple[int, str]]] = {}
    line = {r.id: r.span.first for r in solver.program.relations}
    declared: list[Parameter | DerivedRelation] = sorted(
        (*solver.params.parameters, *solver.params.derived),
        key=lambda x: line.get(x.declaration, 0))
    # A relation a RIGID call binds is swept through the facts of the
    # chart that holds them, under its own name; the chart, a relation
    # the engine names, is not swept on its own.
    charts = rigid_charts(solver)
    by_name = {p.name: p for p in solver.params.parameters}
    held = {c for c in charts.values() if c in by_name}
    for rank, p in enumerate(declared):
        if p.name in held:
            continue
        if isinstance(p, DerivedRelation):
            types = tuple(c.type for c in p.columns)
            entries.append((rank, 0, Skipped(p.name, types,
                                             NotSwept.DERIVED)))
            continue
        holder = by_name.get(charts.get(p.name, ""), p)
        types = tuple(c.type for c in holder.columns)
        m = _marker_of(p)
        if m is not None and not lists_case(solver, m):
            no_case.setdefault(m, []).append((rank, p.name))
        stored = stored_facts(solver, runs, holder)
        if not stored:
            entries.append((rank, 0, Skipped(p.name, types,
                                             NotSwept.NO_FACTS)))
            continue
        if not enumerable(types, lib) or task is None:
            entries.append((rank, 0, Skipped(p.name, types,
                                             NotSwept.NON_ENUMERABLE)))
            continue
        domains = param_domains(types, stored, task, lib)
        cands = sorted(set(itertools.product(*domains)) | set(stored),
                       key=row_key)
        scope: Near | None = None
        if len(cands) > max_candidates:
            whole = len(cands)
            cands = _coordinate(stored, [list(d) for d in domains],
                                max_candidates)
            if len(cands) < whole:
                scope = Near(len(cands), whole)
        prepared.append((rank, p, holder.name, types, stored, cands, scope))
    for m, under in no_case.items():
        entries.append((under[-1][0], 2,
                        NoCaseMarker(m, tuple(n for _r, n in under))))

    sw = _Sweeper(solver, runs, clock)
    shared = {p.name for p in solver.params.parameters
              if isinstance(p.section, Unmarked)}
    reference: Profile | None = None
    base_cases: frozenset[Case] = frozenset()
    ran = False
    for rank, p, fix, types, stored, cands, scope in sorted(
            prepared, key=lambda x: (len(x[5]), x[0])):
        name = p.name
        if ran and clock.spent():
            entries.append((rank, 0, Skipped(name, types,
                                             NotSwept.TIME_LIMIT)))
            continue
        if reference is None:
            ref = profile(runs.engine, solver, sw.train, runs.limits)
            ran = True
            if isinstance(ref, TimedOut):
                entries.append((rank, 0, Skipped(name, types, ref)))
                continue
            if isinstance(ref, Fails):
                entries.append((rank, 0, Skipped(name, types,
                                                 NotSwept.FAILS_TRAIN)))
                continue
            reference = ref
            passing = [_passing(e, a) for e, a in zip(ref, sw.accepted,
                                                      strict=True)]
            base_cases = frozenset.intersection(*passing) if passing \
                else frozenset()
        refp: Profile = reference
        cases_wanted = name in shared and len(base_cases) > 1 \
            and len(stored) == 1
        results, n_run = sw.chunks(
            cands, lambda v: sw.run(fix, (v,), refp, cases_wanted), True)
        ran = True
        fitting: list[Row] = []
        timed: list[tuple[Row, TimedOut]] = []
        admits: dict[Row, frozenset[Case]] = {}
        for v, r in zip(cands, results):
            if isinstance(r, TimedOut):
                timed.append((v, r))
                continue
            if isinstance(r, tuple) and r == refp:
                fitting.append(v)
            if cases_wanted:
                if isinstance(r, tuple):
                    per = [_passing(e, a) for e, a in zip(r, sw.accepted,
                                                          strict=True)]
                    admits[v] = frozenset.intersection(*per) if per \
                        else frozenset()
                else:
                    admits[v] = frozenset()
        gaps: Gaps[Row] | None = None
        if n_run < len(cands) or set(stored) <= set(fitting):
            beyond = sorted(set(fitting) - set(stored), key=row_key)
            g = sw.gaps(_marker_of(p), beyond,
                        lambda v, fix=fix: sw.program(fix, (v,)))
            if isinstance(g, TimedOut):
                entries.append((rank, 0, Skipped(name, types, g)))
                continue
            if isinstance(g, Gaps):
                gaps = g
                gone = {v for v, _ in g.undefined}
                fitting = [v for v in fitting if v not in gone]
            elif g is not None:
                entries.append((rank, 0, Skipped(name, types, RunFailed(g))))
                continue
        extras = sorted(set(fitting) - set(stored), key=row_key)
        if n_run < len(cands):
            entries.append((rank, 0, ValueSweep(
                name, types, tuple(fitting), tuple(stored),
                Extras(tuple((e, OnTest.NOT_RUN) for e in extras)),
                Cut(n_run, len(cands)), gaps, tuple(timed))))
            continue
        case_sets = None
        if cases_wanted:
            per_case = tuple(
                (c, frozenset(v for v, a in admits.items() if c in a))
                for c in sorted(base_cases,
                                key=lambda c: case_label(solver, c)))
            if len({s for _, s in per_case}) > 1:
                case_sets = CaseSets(name, types, per_case, frozenset(cands))
        if not set(stored) <= set(fitting):
            entries.append((rank, 0, _set_sweep(
                sw, p, fix, types, stored, cands, refp, max_candidates)))
            if case_sets:
                entries.append((rank, 1, case_sets))
            continue
        verdicts = test_verdicts(
            runs.engine, solver, runs.limits, extras,
            lambda v, fix=fix: sw.program(fix, (v,)),
            sw.test_ref()) if extras else {}
        entries.append((rank, 0, ValueSweep(
            name, types, tuple(fitting), tuple(stored),
            Extras(tuple((e, verdicts[e]) for e in extras)), scope, gaps,
            tuple(timed))))
        if case_sets:
            entries.append((rank, 1, case_sets))
    return SweepReport(
        tuple(e for _, _, e in sorted(entries, key=lambda e: e[:2])),
        determined, time_limit, clock.elapsed())


def _set_sweep(sw: _Sweeper, p: Parameter, fix: str,
               types: tuple[str, ...], stored: list[Row], singles: list[Row],
               reference: Profile, max_candidates: int
               ) -> SetSweep | Skipped:
    """A parameter whose facts fit only together, swept as one set: the
    non-empty subsets of the single candidates, or above the cap the sets
    one row change from the stored set. Zero is absence, so a 0 in a
    number column stands only where a stored fact already holds one
    there."""
    name = p.name
    blank = {i for i, t in enumerate(types)
             if t == NUMBER and all(s[i] != 0 for s in stored)}
    singles = [v for v in singles if all(v[i] != 0 for i in blank)]
    n_sets = 2 ** len(singles) - 1
    scope: Near | None = None
    if n_sets > max_candidates:
        subsets = _neighborhood(stored, singles, max_candidates)
        if len(subsets) < n_sets:
            scope = Near(len(subsets), n_sets)
    else:
        subsets = [frozenset(c) for r in range(1, len(singles) + 1)
                   for c in itertools.combinations(singles, r)]
    stored_set = frozenset(stored)

    def ordered(v: SetValue) -> list[Row]:
        return sorted(v, key=row_key)

    results, n_run = sw.chunks(
        subsets, lambda v: sw.run(fix, ordered(v), reference, False), False)
    fitting: list[SetValue] = []
    timed: list[tuple[SetValue, TimedOut]] = []
    for v, r in zip(subsets, results):
        if isinstance(r, TimedOut):
            timed.append((v, r))
        elif isinstance(r, tuple) and r == reference:
            fitting.append(v)

    def set_key(v: SetValue) -> list[tuple[object, ...]]:
        return [row_key(r) for r in ordered(v)]

    gaps: Gaps[SetValue] | None = None
    if n_run < len(subsets) or stored_set in fitting:
        beyond = sorted(set(fitting) - {stored_set}, key=set_key)
        g = sw.gaps(_marker_of(p), beyond,
                    lambda v: sw.program(fix, ordered(v)))
        if isinstance(g, TimedOut):
            return Skipped(name, types, g)
        if isinstance(g, Gaps):
            gaps = g
            gone = {v for v, _ in g.undefined}
            fitting = [f for f in fitting if f not in gone]
        elif g is not None:
            return Skipped(name, types, RunFailed(g))
    extras = sorted(set(fitting) - {stored_set}, key=set_key)
    if n_run < len(subsets):
        return SetSweep(name, types, tuple(fitting), tuple(stored),
                        Extras(tuple((e, OnTest.NOT_RUN) for e in extras)),
                        Cut(n_run, len(subsets)), gaps, tuple(timed))
    verdicts: dict[SetValue, TestVerdict] = {}
    if extras and stored_set in fitting:
        verdicts = test_verdicts(sw.engine, sw.solver, sw.limits, extras,
                                 lambda v: sw.program(fix, ordered(v)),
                                 sw.test_ref())
    elif extras:
        verdicts = dict.fromkeys(extras, OnTest.NOT_RUN)
    return SetSweep(name, types, tuple(fitting), tuple(stored),
                    Extras(tuple((e, verdicts[e]) for e in extras)), scope,
                    gaps, tuple(timed))

