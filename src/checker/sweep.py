"""The sweep survey: for each parameter, the values of its domain that
reproduce every train pair, and what the test pairs say of the others."""

import itertools
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum, auto

from checker.domains import candidate_rows, enumerable, param_domains
from checker.runs import NoCases, Runs
from checker.variants import (
    Entry,
    Fails,
    OnTest,
    Profile,
    TestVerdict,
    TimedOut,
    pairs_of,
    profile,
    test_verdicts,
    with_program,
    workers,
)
from engine import Engine, Grid, Program, Row, RunFailure
from engine.quotes import quotes
from solver.annotations import CaseMarker
from solver.model import (
    Base,
    Case,
    base_case,
    bases_of,
    DerivedRelation,
    Parameter,
    UnderMarker,
    Unmarked,
    derived_parameters,
)
from solver.aggregate import Solver, lists_case
from solver.readers import declaration_of
from solver.columns import ColumnTypes
from solver.dependence import dependence
from solver.names import marker_lists
from solver.names import name as case_label
from solver.outcome import Grids
from solver.determine import stored_facts, Determined, rigid_charts
from solver.variations import FixParam, variation
from solver.pair_runs import (
    PairId,
    fits_pairs,
    matches_every,
    Candidate,
    TaskSection,
)
from solver.group_runs import at_once
from solver.per_case import PerCase, parameter_reading, by_base, with_rows_at
from solver.value_order import row_key
from solver.pair_runs import candidates as pair_candidates
from solver.vocabulary import NUMBER
from solver.witness import Undefined

MAX_CANDIDATES = 256
"""The most candidates tried per parameter; beyond it, only the
candidates one change from the stored facts."""
TIME_LIMIT_SECONDS = 300.0


class NotSwept(Enum):
    """Why a parameter is not swept, where no run is the reason."""

    DERIVED = auto()
    NO_FACTS = auto()
    NON_ENUMERABLE = auto()
    TIME_LIMIT = auto()
    FAILS_TRAIN = auto()


@dataclass(frozen=True)
class RunFailed:
    """A run the sweep of a parameter needs failed."""

    failure: RunFailure


type SkipReason = NotSwept | RunFailed | NoCases | TimedOut


@dataclass(frozen=True)
class GivingValues:
    """A parameter that holds several values at a case that gives no
    output on a train pair (`values_giving`): the case, the first train
    pair on which it gives none, the parameter, its value's column types
    (`solver.per_case.PerCase.value_types`), the values it holds at the
    case, those of them under which alone the case gives its train
    outputs, in the order of `held`, and each value whose run failed.
    `giving` is short of `held`, and empty only where a run failed."""

    case: Case
    pair: PairId
    parameter: str
    types: tuple[str, ...]
    held: tuple[Row, ...]
    giving: tuple[Row, ...]
    failed: tuple[tuple[Row, RunFailure], ...]


@dataclass(frozen=True)
class Skipped:
    parameter: str
    types: tuple[str, ...]
    """The value's column types as the declaration writes them."""
    reason: SkipReason
    case: Case | None = None
    """The case whose value of a parameter that stores a value per case
    is not swept; None for the parameter's one value."""
    giving: tuple[GivingValues, ...] = ()
    """Where the stored program fails a train pair
    (`NotSwept.FAILS_TRAIN`), the parameter at each case of `case`, or at
    every case where `case` is None, that gives no output on a train pair
    while the parameter holds several values there (`values_giving`)."""


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


def set_rows(v: SetValue) -> list[Row]:
    """A set value's rows, in order (`row_key`)."""
    return sorted(v, key=row_key)


def set_key(v: SetValue) -> list[tuple[object, ...]]:
    """The order of set values: by their rows in order (`set_rows`)."""
    return [row_key(r) for r in set_rows(v)]


@dataclass(frozen=True)
class Gaps[V]:
    """The values the pairs reproduce only because no case the marker
    marks is defined on every train pair: the marker, and each such value
    with whether those cases give nothing on every pair."""

    marker: CaseMarker
    undefined: tuple[tuple[V, bool], ...]


def beyond_stored(admitted: Iterable[Row], stored: Iterable[Row]
                  ) -> list[Row]:
    """The admitted values beyond the stored ones, in order (`row_key`)."""
    return sorted(set(admitted) - set(stored), key=row_key)


@dataclass(frozen=True)
class Extras[V]:
    """The values train admits beyond the stored ones (`beyond_stored`), each with
    its test verdict: values the pairs do not separate from the stored
    ones, none of them a value to store."""

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
    case: Case | None = None
    """The case whose value of a parameter that stores a value per case
    is swept (`_Fix`); None for the parameter's one value."""
    per_case: "CaseSets[Row] | None" = None
    """Where the bases admit different values, each base's admitted
    values (`CaseSets`)."""

    @property
    def cases_differ(self) -> bool:
        """The bases admit different values (`per_case`)."""
        return self.per_case is not None

    def admits_stored_alone(self) -> bool:
        """The values the pairs admit are the stored rows: a value is
        admitted where the program under it gives the stored program's
        profile (`checker.variants.profile`), which is no Fit judgment."""
        return set(self.fitting) == set(self.stored)

    def settles(self) -> bool:
        return _settles(self.admits_stored_alone(), self.cases_differ,
                        self.scope, (*self.timed, *self.extras.timed))


@dataclass(frozen=True)
class SetSweep:
    """A parameter whose value is a set of rows, no stored fact alone
    giving the stored program's profile: the one set it stores, swept by
    the single-row changes of that set (`_neighborhood`): how many of
    them also give the stored program's profile on every train pair, so
    that the pairs do not pin the set where any does. None of those sets
    is a value to store."""

    parameter: str
    types: tuple[str, ...]
    stored: tuple[Row, ...]
    unpinned: int
    """The single-row changes of the stored set that give the stored
    program's profile on every train pair, less those of `gaps`."""
    scope: Near | Cut | None
    gaps: Gaps[SetValue] | None
    timed: tuple[tuple[SetValue, TimedOut], ...]
    case: Case | None = None
    """As `ValueSweep.case`."""
    per_case: "SetCases | Uncompared | None" = None
    """Where the cases differ in which changes give their train outputs,
    the count per case, which stands in place of `unpinned`; `Uncompared`
    where the time limit cut the sweep before the cases were compared."""

    def admits_stored_alone(self) -> bool:
        """No single-row change of the stored set gives the stored
        program's profile (`ValueSweep`)."""
        return self.unpinned == 0

    @property
    def cases_differ(self) -> bool:
        """The cases differ in which changes give their train outputs, or
        were not compared (`per_case`)."""
        return self.per_case is not None

    def settles(self) -> bool:
        return _settles(self.admits_stored_alone(), self.cases_differ,
                        self.scope, self.timed)


def _settles(admits_stored_alone: bool, cases_differ: bool,
             scope: Near | Cut | None, timed: Sequence[object]) -> bool:
    """A sweep settles its parameter: the pairs admit the stored value
    alone, the cases do not differ in what they admit, every candidate
    ran, and no run reached a limit."""
    return admits_stored_alone and not cases_differ and scope is None \
        and not timed


@dataclass(frozen=True)
class CaseSets[V: (Row, SetValue)]:
    """A parameter above the case markers, whose bases admit different
    values: each base's admitted values, at its base case
    (`solver.model.base_case`, `_passing_every`), the candidates run, and the
    cases the program never reads the parameter under
    (`solver.dependence.Dependence.reads_parameter`). A value
    is a row (`ValueSweep`), or a set of rows (`SetSweep`), whose entry is
    `SetCases`."""

    parameter: str
    types: tuple[str, ...]
    per_case: tuple[tuple[Case, frozenset[V]], ...]
    domain: frozenset[V]
    unread: frozenset[Case]

    @property
    def never_read(self) -> frozenset[Case]:
        """The cases that admit every candidate run (`domain`) and that
        the program never reads the parameter under (`unread`): the
        cases that never read it."""
        return frozenset(c for c, s in self.per_case
                         if c in self.unread and s == self.domain)

    @property
    def common(self) -> frozenset[V]:
        """The values every case admits, which the cases line reads
        (`checker.render.surveys.COMMON`)."""
        return frozenset.intersection(*(s for _c, s in self.per_case))


@dataclass(frozen=True)
class SetCases:
    """A set parameter (`SetSweep`) above the case markers, whose bases
    differ in which single-row changes of the stored set give their train
    outputs: per base case, how many of those changes do (`CaseSets`), of
    the `swept` changes, and the cases at which every swept change does and
    which the program never reads the parameter under
    (`solver.dependence.Dependence.reads_parameter`)."""

    per_case: tuple[tuple[Case, int], ...]
    swept: int
    unread: frozenset[Case]


@dataclass(frozen=True)
class Uncompared:
    """A set parameter (`SetSweep`) that several cases read, whose cases
    were not compared, since the time limit cut the sweep before every
    change ran."""


def _set_cases(sets: CaseSets[SetValue]) -> SetCases:
    """The set form of `sets`, whose values are the single-row changes of
    a stored set."""
    return SetCases(tuple((c, len(s)) for c, s in sets.per_case),
                    len(sets.domain), sets.never_read)


@dataclass(frozen=True)
class NoCaseMarker:
    """A marker in `Params` that lists no case, with the parameters under
    it (solver-file.md, under "Cases")."""

    marker: CaseMarker
    parameters: tuple[str, ...]


type SweepEntry = ValueSweep | SetSweep | Skipped | NoCaseMarker


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


def _passing_every(got: Profile,
                   cands: Sequence[Sequence[tuple[Candidate, frozenset[Grid]]]]
                   ) -> frozenset[Case]:
    """The base cases (`solver.model.base_case`) whose grids are a
    candidate of every pair of the profile `got`
    (`solver.pair_runs.matches_every`), `cands` those pairs' candidates in
    order."""
    if not got:
        return frozenset()
    per = [dict(e) for e in got]
    every = frozenset.intersection(*(frozenset(d) for d in per))
    return frozenset(c for c in every if c.is_base_case and matches_every(
        cands, [Grids(d[c]) for d in per]))


def _split[V](values: Sequence[V], results: Sequence[object],
              reference: Profile
              ) -> tuple[list[V], list[tuple[V, TimedOut]]]:
    """The values whose run gives the reference profile, and those whose
    run reached a limit, each in the order of `values`."""
    fitting: list[V] = []
    timed: list[tuple[V, TimedOut]] = []
    for v, r in zip(values, results):
        if isinstance(r, TimedOut):
            timed.append((v, r))
        elif isinstance(r, tuple) and r == reference:
            fitting.append(v)
    return fitting, timed


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


def _neighborhood(stored: list[Row], singles: list[Row]) -> list[SetValue]:
    """The non-empty sets one row change from the stored set: a stored row
    removed, replaced by a single, or a single added, one change per
    stored row in turn, so that a prefix spreads over the stored rows."""
    stored_set = frozenset(stored)
    sets: list[SetValue] = []
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
            sets.append(value)
            seen.add(value)
    return sets


def _marked(solver: Solver, marker: CaseMarker, solver_cases: Sequence[Case]
            ) -> frozenset[Case]:
    """The solver's cases a marker marks: those whose base a part of it
    lists (`solver.names.lists`)."""
    return frozenset(c for c in solver_cases
                     if marker_lists(solver, marker, c.base))


def _case_sets[V: (Row, SetValue)](
        sw: "_Sweeper", p: Parameter, types: tuple[str, ...],
        cases: frozenset[Case], values: Sequence[V],
        results: Sequence[object]) -> CaseSets[V] | None:
    """Each case's admitted values among `values`, from their runs read
    per case (`_Sweeper.run` with `cases`): a case admits a value whose run
    gives that case's grids as a candidate of every train pair
    (`_Sweeper.passing`).
    None where `cases` is empty, since the runs were then read as one
    profile, and where every case admits the same values."""
    if not cases:
        return None
    admits: dict[V, frozenset[Case]] = {}
    for v, r in zip(values, results):
        if not isinstance(r, TimedOut):
            admits[v] = sw.passing(r) if isinstance(r, tuple) \
                else frozenset()
    solver = sw.solver
    per_case = tuple(
        (c, frozenset(v for v, a in admits.items() if c in a))
        for c in sorted(cases, key=lambda c: case_label(solver, c)))
    if len({s for _, s in per_case}) <= 1:
        return None
    rd = dependence(sw.runs.engine, solver, bases_of(c for c, _s in per_case))
    return CaseSets(
        p.name, types, per_case, frozenset(values),
        frozenset(c for c, _s in per_case
                  if not rd.reads_parameter(c.base, p.name)))


@dataclass(frozen=True)
class _Fix:
    """The relation a sweep fixes and how a candidate value is written
    into it: as the relation's rows, or, for a parameter that stores a
    value per case, at a base (`_AtBase`)."""

    relation: str
    at: "_AtBase | None" = None

    @property
    def case(self) -> Case | None:
        """The base case of the base (`solver.model.base_case`); None
        for the parameter's one value."""
        return None if self.at is None else base_case(self.at.base)

    def rows(self, solver: Solver, values: Sequence[Row]) -> tuple[Row, ...]:
        if self.at is None:
            return tuple(values)
        return with_rows_at(solver, self.at.per_case, self.at.stored,
                            self.at.base, values)

    def program(self, engine: Engine, solver: Solver, values: Sequence[Row]
                ) -> Program:
        """The solver's program with the relation holding `values` where
        the fix writes them (`rows`)."""
        return variation(engine, solver,
                         FixParam(self.relation, self.rows(solver, values)))

    def applies_at(self, case: Case) -> bool:
        """Whether the fix writes the value `case` reads: the parameter's
        one value, or its value at the case's base."""
        return self.at is None or self.at.base == case.base


@dataclass(frozen=True)
class _AtBase:
    """Where a sweep of a parameter that stores a value per case
    (`solver.per_case.PerCase`) writes a candidate: at `base`, with the rows
    of `stored` that hold at another base kept."""

    base: Base
    per_case: PerCase
    stored: tuple[Row, ...]


class _Sweeper:
    def __init__(self, solver: Solver, runs: Runs, clock: _Clock) -> None:
        self.solver = solver
        self.runs = runs
        self.engine = runs.engine
        self.limits = runs.limits
        self.clock = clock
        self.train = pairs_of(solver, (TaskSection.TRAIN,))
        self.accepted = [pair_candidates(ex) for _, ex in self.train]

    def program(self, fix: _Fix, rows: Sequence[Row]) -> Program:
        return fix.program(self.engine, self.solver, rows)

    @property
    def within(self) -> Profile | None:
        """The stored program's train profile, whose runs limit a
        variant's (`checker.variants.profile`); None where it has none."""
        got = self.runs.train_profile
        return got if isinstance(got, tuple) else None

    def run(self, fix: _Fix, rows: Sequence[Row], reference: Profile,
            by_case: frozenset[Case]) -> Profile | Fails | TimedOut:
        """The profile under `rows`, read until it differs from
        `reference`; with `by_case`, read instead until no case of
        `by_case` passes every pair read (`_passing_every`)."""
        program = with_program(self.solver, self.program(fix, rows))
        if not by_case:
            return profile(self.engine, program, self.runs.cases, self.train,
                           self.limits, reference, held=False)
        return profile(
            self.engine, program, self.runs.cases, self.train, self.limits,
            held=False,
            stop=lambda read: not by_case & self.passing(tuple(read)),
            within=self.within)

    def passing(self, read: Profile) -> frozenset[Case]:
        """The cases that pass every pair the profile `read` reads, the
        first pairs of the train pairs (`_passing_every`)."""
        return _passing_every(read, self.accepted[:len(read)])

    def chunks[V](self, values: list[V], fn: Callable[[V], object],
                  first: bool) -> tuple[list[object], int]:
        """`fn` over `values` in order, as many at once as `workers()`,
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

    def without_gaps[V](self, p: Parameter, fitting: list[V],
                        beyond: list[V], program_of: Callable[[V], Program]
                        ) -> tuple[list[V], "Gaps[V] | None"] | SkipReason:
        """`fitting` less the values `gaps` finds among `beyond`, with
        those gaps; where a run reached a limit or failed, why the
        parameter is skipped."""
        g = self.gaps(_marker_of(p), beyond, program_of)
        if isinstance(g, TimedOut):
            return g
        if isinstance(g, Gaps):
            gone = {v for v, _ in g.undefined}
            return [v for v in fitting if v not in gone], g
        if g is not None:
            return RunFailed(g)
        return fitting, None

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

        def marked_of(got: Profile | Fails | TimedOut
                      ) -> list[frozenset[Case]] | Fails | TimedOut:
            if not isinstance(got, tuple):
                return got
            return [frozenset(c for c, _ in e if c in marked) for e in got]

        def reading(program: Program) -> list[frozenset[Case]] | Fails \
                | TimedOut:
            return marked_of(profile(
                self.engine, with_program(self.solver, program),
                self.runs.cases, self.train, self.limits, held=False,
                within=self.within))

        base = marked_of(self.runs.train_profile)
        if isinstance(base, TimedOut):
            return base
        if isinstance(base, Fails) or not frozenset.intersection(*base):
            return None
        runs = at_once(lambda v: reading(program_of(v)), extras)
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


@quotes("procedure.md", "Determine",
        "Run the sweep (`uv run python scripts/run_dl.py sweep <task_id>`), "
        "and store a value it reports for a parameter beyond the stored "
        "values only where the concept leaves that parameter's value free, "
        "as [Choice points and open parameters]"
        "(docs/handbook/principles.md#choice-points-and-open-parameters) "
        "defines an open parameter, unless "
        "[Principles](docs/handbook/principles.md) make that parameter a "
        "choice point.")
def survey_sweep(solver: Solver, runs: Runs,
                 max_candidates: int = MAX_CANDIDATES,
                 time_limit: float = TIME_LIMIT_SECONDS) -> SweepReport:
    """Each enumerable parameter swept one at a time, the others at their
    stored values: a value fits where it reproduces the stored program's
    profile on every train pair (principles.md, under "Models and tasks", a
    stored assignment determined by the evidence). Fitting values beyond the
    stored ones (`Extras`) run on the test pairs. A parameter whose value
    is a set of rows stores its one set, and its sweep counts the
    single-row changes of that set that also fit (`SetSweep`). Above the
    cap, the candidates one change from the stored facts.
    The parameters run cheapest first, and a spent time limit cuts the
    parameter in flight and leaves the rest unswept. A value the pairs
    reproduce only because the cases that read the parameter give nothing
    leaves the fitting values, and the result states it. A parameter
    every case reads also reports each case's admitted values, where they
    differ. A parameter that stores a value per case sweeps each case's
    value, the other cases' facts at their stored values (`_fixes`). A
    solver with no task file raises `ValueError`; the command refuses it
    first."""
    clock = _Clock(time_limit)
    got = runs.determined
    determined = frozenset(got.reproduced) if isinstance(got, Determined) \
        else frozenset()
    task = solver.given_task
    lib = solver.lib
    entries: list[tuple[int, int, int, SweepEntry]] = []
    prepared: list[tuple[int, int, Parameter, _Fix,
                         ColumnTypes, list[Row], list[Row],
                         Near | None]] = []
    no_case: dict[CaseMarker, list[tuple[int, str]]] = {}
    declared = _declared(solver, (*solver.params.parameters,
                                  *solver.params.derived))
    holders = _holders(solver)
    for rank, p in enumerate(declared):
        if isinstance(p, DerivedRelation):
            types = parameter_reading(solver, p.name).as_written
            entries.append((rank, 0, 0, Skipped(p.name, types,
                                                NotSwept.DERIVED)))
            continue
        holder = holders.get(p.name)
        if holder is None:
            continue
        reading = parameter_reading(solver, holder.name)
        m = _marker_of(p)
        if m is not None and not lists_case(solver, m):
            no_case.setdefault(m, []).append((rank, p.name))
        stored = stored_facts(runs.engine, solver, holder)
        if not stored:
            entries.append((rank, 0, 0, Skipped(p.name, reading.as_written,
                                                NotSwept.NO_FACTS)))
            continue
        fixes = _fixes(solver, runs, holder.name, stored)
        if not isinstance(fixes, list):
            entries.append((rank, 0, 0, Skipped(p.name, reading.as_written,
                                                NoCases(fixes))))
            continue
        columns = reading.value_columns
        for order, (fix, at_case) in enumerate(fixes):
            case = fix.case
            if not at_case:
                entries.append((rank, 0, order, Skipped(
                    p.name, columns.written, NotSwept.NO_FACTS, case)))
                continue
            if not enumerable(columns.types, solver.lib):
                entries.append((rank, 0, order, Skipped(
                    p.name, columns.written, NotSwept.NON_ENUMERABLE, case)))
                continue
            domains = param_domains(columns.types, at_case, task, lib)
            cands = candidate_rows(domains, at_case)
            scope: Near | None = None
            if len(cands) > max_candidates:
                whole = len(cands)
                cands = _coordinate(at_case, [list(d) for d in domains],
                                    max_candidates)
                if len(cands) < whole:
                    scope = Near(len(cands), whole)
            prepared.append((rank, order, p, fix, columns, at_case,
                             cands, scope))
    for m, under in no_case.items():
        entries.append((under[-1][0], 2, 0,
                        NoCaseMarker(m, tuple(n for _r, n in under))))

    sw = _Sweeper(solver, runs, clock)
    shared = {p.name for p in solver.params.parameters
              if isinstance(p.section, Unmarked)}
    reference: Profile | None = None
    giving: tuple[GivingValues, ...] | None = None
    base_cases: frozenset[Case] = frozenset()
    ran = False
    for rank, order, p, fix, columns, stored, cands, scope in sorted(
            prepared, key=lambda x: (len(x[6]), x[0], x[1])):
        name = p.name
        types, written = columns.types, columns.written
        case = fix.case
        if ran and clock.spent():
            entries.append((rank, 0, order, Skipped(
                name, written, NotSwept.TIME_LIMIT, case)))
            continue
        if reference is None:
            ref = runs.train_profile
            ran = True
            if isinstance(ref, TimedOut):
                entries.append((rank, 0, order, Skipped(name, written, ref,
                                                        case)))
                continue
            if isinstance(ref, Fails):
                if giving is None:
                    giving = values_giving(solver, runs)
                entries.append((rank, 0, order, Skipped(
                    name, written, NotSwept.FAILS_TRAIN, case,
                    tuple(g for g in giving if g.parameter == name
                          and fix.applies_at(g.case)))))
                continue
            reference = ref
            base_cases = sw.passing(ref)
        refp: Profile = reference
        by_case = base_cases if name in shared and len(base_cases) > 1 \
            and fix.at is None else frozenset()
        results, n_run = sw.chunks(
            cands, lambda v: sw.run(fix, (v,), refp, by_case), True)
        ran = True
        fitting, timed = _split(cands, results, refp)
        gaps: Gaps[Row] | None = None
        if n_run < len(cands) or set(stored) <= set(fitting):
            beyond = beyond_stored(fitting, stored)
            got = sw.without_gaps(p, fitting, beyond,
                                  lambda v, fix=fix: sw.program(fix, (v,)))
            if not isinstance(got, tuple):
                entries.append((rank, 0, order, Skipped(name, written, got,
                                                        case)))
                continue
            fitting, gaps = got
        extras = beyond_stored(fitting, stored)
        if n_run < len(cands):
            entries.append((rank, 0, order, ValueSweep(
                name, types, tuple(fitting), tuple(stored),
                Extras(tuple((e, OnTest.NOT_RUN) for e in extras)),
                Cut(n_run, len(cands)), gaps, tuple(timed), case)))
            continue
        case_sets: CaseSets[Row] | None = None
        if not set(stored) <= set(fitting):
            entries.append((rank, 0, order, _set_sweep(
                sw, p, fix, columns, stored, cands, refp, max_candidates,
                by_case)))
        else:
            case_sets = _case_sets(sw, p, types, by_case, cands, results)
            verdicts = test_verdicts(
                runs.engine, solver, runs.cases, runs.limits, extras,
                lambda v, fix=fix: sw.program(fix, (v,)),
                runs.test_profile) if extras else {}
            entries.append((rank, 0, order, ValueSweep(
                name, types, tuple(fitting), tuple(stored),
                Extras(tuple((e, verdicts[e]) for e in extras)), scope, gaps,
                tuple(timed), case, case_sets)))
    return SweepReport(
        tuple(e for *_k, e in sorted(entries, key=lambda e: e[:3])),
        determined, time_limit, clock.elapsed())


def _declared[P: (Parameter, Parameter | DerivedRelation)](
        solver: Solver, relations: Sequence[P]) -> list[P]:
    """`relations` of `Params` in the order the program declares them."""
    return sorted(relations,
                  key=lambda x: declaration_of(solver.program, x).span.first)


def _holders(solver: Solver) -> dict[str, Parameter]:
    """Each parameter the sweep reads, with the parameter that holds its
    facts: a relation a RIGID call binds is read through the facts of the
    chart that holds them, under its own name, and the chart, a relation
    the engine names, is not read on its own, so it has no entry. The
    call declares each chart in `Params`, where its facts make it a
    parameter."""
    charts = rigid_charts(solver)
    by_name = {p.name: p for p in solver.params.parameters}
    held = frozenset(charts.values())
    return {p.name: by_name[charts[p.name]] if p.name in charts else p
            for p in solver.params.parameters if p.name not in held}


@quotes("solver-file.md", "Params",
        "A case stores its base's values of each open parameter it stores, "
        "and those are that parameter's open values under the case "
        "of that base that takes the concept branch at every `@derive` and "
        "`@store` point.")
@quotes("principles.md", "Open parameters",
        "The output contains a grid exactly when every open value produces "
        "that grid.")
def values_giving(solver: Solver, runs: Runs) -> tuple[GivingValues, ...]:
    """For each case that gives no output on a train pair, each parameter
    its base reads (`solver.dependence.dependence`) as stored, its case taking
    no `@derive` branch on it, that holds several values at the case
    (`_fixes`): which of those values alone, the parameter's other cases
    at their stored values, give the case an output that is a candidate
    of every train pair: by the quoted passages, those are the open values
    the case keeps. A parameter is reported only where keeping some of its values is open
    to the reader: some value gives the train outputs and another does
    not, or a value's run failed. The cases in the order the pairs' runs
    give them, each case's parameters in declaration order; none where
    the run that enumerates the cases failed."""
    got = runs.pairs
    if not isinstance(got, tuple):
        return ()
    first: dict[Case, PairId] = {}
    for pr in got:
        if pr.pair.section is not TaskSection.TRAIN:
            continue
        for c in pr.cases:
            if isinstance(c.outcome, Undefined):
                first.setdefault(c.case, pr.pair)
    if not first:
        return ()
    engine, limits = runs.engine, runs.limits
    read = dependence(engine, solver, bases_of(first))
    holders = _holders(solver)
    train = pairs_of(solver, (TaskSection.TRAIN,))
    work: list[tuple[Case, PairId, str, _Fix, tuple[str, ...],
                     tuple[Row, ...]]] = []
    for case, pair in first.items():
        derived = derived_parameters(case.branches)
        for p in _declared(solver, solver.params.parameters):
            holder = holders.get(p.name)
            if holder is None or p.name in derived \
                    or not read.reads_parameter(case.base, p.name):
                continue
            fixes = _fixes(solver, runs, holder.name,
                           stored_facts(engine, solver, holder))
            if not isinstance(fixes, list):
                raise ValueError("the cases the pairs ran have no bases")
            at = [(f, vs) for f, vs in fixes if f.applies_at(case)]
            if not at:
                raise ValueError("a case the pairs ran has no base the "
                                 "checks read")
            ((fix, held),) = at
            if len(held) > 1:
                work.append((case, pair, p.name, fix, parameter_reading(
                    solver, holder.name).value_types, tuple(held)))

    def gives(item: tuple[_Fix, Case, Row]) -> bool | RunFailure:
        fix, case, value = item
        return fits_pairs(engine, with_program(
            solver, fix.program(engine, solver, (value,))), case, train,
            limits)

    tried = [(fix, case, v) for case, _p, _n, fix, _t, held in work
             for v in held]
    results = iter(at_once(gives, tried))
    out: list[GivingValues] = []
    for case, pair, name, _fix, types, held in work:
        each = [(v, next(results)) for v in held]
        giving = tuple(v for v, r in each if r is True)
        failed = tuple((v, r) for v, r in each if not isinstance(r, bool))
        if len(giving) == len(held) or not giving and not failed:
            continue
        out.append(GivingValues(case, pair, name, types, held, giving,
                                failed))
    return tuple(out)


def _fixes(solver: Solver, runs: Runs, relation: str, stored: list[Row]
           ) -> list[tuple[_Fix, list[Row]]] | RunFailure:
    """What a sweep of the parameter `relation` fixes, each with the
    stored value it compares against: the parameter's rows, or, where it
    stores a value per case, its value at each base of the cases the
    checks read (`solver.per_case.by_base`); the failure of the run that
    enumerates the cases where it fails."""
    pc = parameter_reading(solver, relation)
    got = by_base(solver, pc, stored, runs.bases)
    if not isinstance(got, list):
        return got
    return [(_Fix(relation, None if base is None
                  else _AtBase(base, pc, tuple(stored))),
             list(pc.values(at)))
            for base, at in got]


def _set_sweep(sw: _Sweeper, p: Parameter, fix: _Fix,
               columns: ColumnTypes, stored: list[Row], singles: list[Row],
               reference: Profile, max_candidates: int,
               by_case: frozenset[Case]) -> SetSweep | Skipped:
    """A parameter whose value is a set of rows, swept by the single-row
    changes of its stored set (`_neighborhood`), the first `max_candidates`
    of them above the cap. Zero is absence, so a 0 in a number column
    stands only where a stored fact already holds one there. Where
    `by_case` holds cases and every change ran, also how many changes each
    of those cases admits, where the cases differ (`_case_sets`,
    `SetSweep.per_case`)."""
    name, types = p.name, columns.types
    blank = {i for i, t in enumerate(types)
             if t == NUMBER and all(s[i] != 0 for s in stored)}
    singles = [v for v in singles if all(v[i] != 0 for i in blank)]
    changes = _neighborhood(stored, singles)
    scope: Near | Cut | None = None
    if len(changes) > max_candidates:
        scope = Near(max_candidates, len(changes))
        changes = changes[:max_candidates]
    results, n_run = sw.chunks(
        changes, lambda v: sw.run(fix, set_rows(v), reference, by_case),
        False)
    fitting, timed = _split(changes, results, reference)
    got = sw.without_gaps(p, fitting, sorted(fitting, key=set_key),
                          lambda v: sw.program(fix, set_rows(v)))
    if not isinstance(got, tuple):
        return Skipped(name, columns.written, got, fix.case)
    fitting, gaps = got
    per_case: SetCases | Uncompared | None = None
    if n_run < len(changes):
        scope = Cut(n_run, len(changes))
        if by_case:
            per_case = Uncompared()
    elif (case_sets := _case_sets(sw, p, types, by_case, changes,
                                  results)) is not None:
        per_case = _set_cases(case_sets)
    return SetSweep(name, types, tuple(stored), len(fitting), scope, gaps,
                    tuple(timed), fix.case, per_case)
