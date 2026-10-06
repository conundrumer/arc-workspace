"""The deletion survey: the structure of the solver whose removal changes
no pair's output and no determined value."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum

from checker.finding import Finding
from checker.judged import enumeration_failed, is_timeout
from checker.lint.idioms import Columns, enumerator_binder
from checker.lint.view import view
from checker.runs import Runs, holding
from checker.variants import (
    EVERY_SECTION,
    Fails,
    Profile,
    TimedOut,
    determines,
    pairs_of,
    profile,
    reproduces,
    restricted,
    ungrounded,
    with_program,
)
from engine import (
    Atom,
    Program,
    RemovalTarget,
    RemoveAtom,
    RemoveColumn,
    RemoveDisjunct,
    RemoveUnit,
    RunFailure,
    Scope,
    Tuples,
    UngroundedVariable,
)
from engine.program import (
    AtomLiteral,
    BodyLiteral,
    Disjunction,
    Unit,
    literal_aggregates,
    own,
)
from engine.quotes import quotes
from solver.model import bases_of, choice_bases, Case
from solver.aggregate import Solver, enumerated, enumerates, run_empty
from solver.case_types import case_columns
from solver.dependence import (
    Dependence,
    dependence,
)
from solver.solve import (
    Determined,
    NoDetermine,
    Remove,
    at_once,
    case_groups,
    variant_bound,
    variant_limits,
    variation,
)
from solver.vocabulary import DETERMINE, IMPL, OUTPUT


class DeletionKind(StrEnum):
    """What a deletion removed, or what its run showed, as the report
    prints it."""

    RULE = "rule"
    NEGATION = "negation"
    ATOM = "atom"
    DISJUNCT = "disjunct"
    BOUND_ENUMERATOR = "bound enumerator"
    """A positive `*_elem` atom whose variable another atom of its clause
    binds (prompts/run_dl.md#enumerator)."""
    COLUMN = "column"
    UNGROUNDED = "ungrounded deletion"
    """A deletion whose program ungrounds a variable, other than a case
    column's."""


@dataclass(frozen=True)
class Quoted:
    """The code a deletion row quotes: a clause's head, with the atom it
    is subsumed by where the clause is subsumptive, or a removed part and
    that head."""

    head: Atom
    dominating: Atom | None
    part: tuple[BodyLiteral, ...] | None = None


@dataclass(frozen=True)
class ColumnName:
    """A column a deletion row quotes, as `<relation>.<column>`."""

    relation: str
    column: str


type Quote = Quoted | ColumnName


@dataclass(frozen=True)
class Deletion:
    """One deletion: the solver line it reports under, its kind, what it
    quotes, and what it removes."""

    line: int
    kind: DeletionKind
    quote: Quote
    targets: tuple[RemovalTarget, ...]
    determine: bool
    """It removes part of the Determine comp, which the determination run
    alone judges."""
    case_column: bool = False
    """It removes a column whose type is `Choice` or an ADT that stands in
    it."""


@dataclass(frozen=True)
class DeletionRow:
    """A deletion that changes nothing, or one no run judged.
    `determination` says the determination run alone judged it."""

    line: int
    kind: DeletionKind
    quote: Quote
    determination: bool


@dataclass(frozen=True)
class TimedOutDeletion:
    """A deletion whose run reached a limit, which is no result."""

    line: int
    kind: DeletionKind
    quote: Quote
    finding: Finding


@dataclass(frozen=True)
class DeletionReport:
    judged: int
    rows: tuple[DeletionRow, ...]
    timed_out: tuple[TimedOutDeletion, ...]
    no_determine: bool = False
    """The solver has no Determine comp, so no deletion's determination
    was checked: its rows hold on the pairs alone."""


@dataclass(frozen=True)
class BaselineFails:
    """The stored program fails a train or test pair."""


type DeletionResult = DeletionReport | BaselineFails | TimedOut


def _in_determine(scope: Scope) -> bool:
    return scope.components[:1] == (DETERMINE,)


@dataclass(frozen=True)
class _Part:
    """A literal of a clause's body: its removal path, whether it stands
    alone in its conjunction, which has no form without it, and whether
    it stands in an aggregate's body."""

    path: tuple[int, ...]
    literal: BodyLiteral
    alone: bool
    in_aggregate: bool


def _parts(body: tuple[BodyLiteral, ...], path: tuple[int, ...],
           in_aggregate: bool = False, skip: int = 0) -> Iterator[_Part]:
    """Every literal of a body past its first `skip`: after a literal's
    index, a disjunction's step is (branch, literal) and any other
    literal's is (aggregate, literal), the aggregate by its place among
    the literal's aggregates, left to right."""
    for i, lit in enumerate(body):
        if i < skip:
            continue
        here = (*path, i)
        yield _Part(here, lit, len(body) - skip == 1, in_aggregate)
        if isinstance(lit, Disjunction):
            for b, branch in enumerate(lit.branches):
                yield from _parts(branch, (*here, b), in_aggregate)
        else:
            for k, agg in enumerate(literal_aggregates(lit)):
                yield from _parts(agg.body, (*here, k), True)


def _clauses(solver: Solver) -> list[tuple[Unit, tuple[Unit, ...]]]:
    """The solver's own rules, one per clause: a clause with several heads
    comes once, as its first unit, with every unit of it."""
    groups: dict[tuple[int, int, object], list[Unit]] = {}
    for u in solver.program.units:
        if not own(u.span) or u.body is None or u.span is None:
            continue
        groups.setdefault((u.span.first, u.span.last, u.body), []).append(u)
    return [(us[0], tuple(us)) for (_first, _last, _body), us in
            sorted(groups.items(), key=lambda kv: kv[0][0])]


def deletions(solver: Solver, runs: Runs) -> list[Deletion]:
    """The structural deletions, rules first by line: the whole clause;
    each negated atom, in an aggregate's body too; each positive atom
    outside an aggregate, a bound enumerator apart; and each branch of a
    disjunction; then each column of a top-level relation of two or more
    columns. A literal that stands alone in its conjunction is not
    removed."""
    v = view(solver, runs)
    cols = Columns(v)
    out: list[Deletion] = []
    for first, units in _clauses(solver):
        assert first.span is not None and first.body is not None
        line = first.span.first
        det = _in_determine(first.scope)
        lead = first.body[0] if first.subsumptive and first.body else None
        dominating = lead.atom if isinstance(lead, AtomLiteral) else None
        skip = 0 if dominating is None else 1
        out.append(Deletion(line, DeletionKind.RULE,
                            Quoted(first.head, dominating),
                            tuple(RemoveUnit(u.id) for u in units), det))

        def head(part: tuple[BodyLiteral, ...]) -> Quoted:
            return Quoted(first.head, dominating, part)

        parts = list(_parts(first.body, (), skip=skip))
        for p in parts:
            lit = p.literal
            if isinstance(lit, AtomLiteral) and lit.negated and not p.alone:
                out.append(Deletion(
                    line, DeletionKind.NEGATION, head((lit,)),
                    (RemoveAtom(first.id, p.path),), det))
        for p in parts:
            lit = p.literal
            if isinstance(lit, AtomLiteral) and not lit.negated \
                    and not p.alone and not p.in_aggregate:
                bound = enumerator_binder(v, cols, first, lit.atom) is not None
                out.append(Deletion(
                    line, DeletionKind.BOUND_ENUMERATOR if bound
                    else DeletionKind.ATOM, head((lit,)),
                    (RemoveAtom(first.id, p.path),), det))
        for p in parts:
            lit = p.literal
            if isinstance(lit, Disjunction):
                for b, branch in enumerate(lit.branches):
                    out.append(Deletion(
                        line, DeletionKind.DISJUNCT, head(branch),
                        (RemoveDisjunct(first.id, (*p.path, b)),), det))
    for decl in solver.program.relations:
        if decl.scope.components or not own(decl.span) \
                or decl.name == OUTPUT.name or len(decl.columns) < 2:
            continue
        case = case_columns(solver, decl.scoped_name)
        for i, col in enumerate(decl.columns):
            out.append(Deletion(decl.span.first, DeletionKind.COLUMN,
                                ColumnName(decl.name, col.name),
                                (RemoveColumn(decl.id, i),), False,
                                i in case))
    return out


def _program(solver: Solver, runs: Runs, d: Deletion) -> Program | None:
    """The solver's program without the deletion's targets; None where
    the program has no form without them."""
    s = solver
    try:
        for t in d.targets:
            s = with_program(s, variation(runs.engine, s, Remove(t)))
    except ValueError:
        return None
    return s.program


def _depending(solver: Solver, groups: Sequence[tuple[Case, ...]],
               read: Dependence, d: Deletion) -> tuple[Case, ...]:
    """The cases of each of `groups` that holds a case whose derivation of
    `out` depends on a unit or a column the deletion removes (`read`,
    `solver.dependence.dependence`): a unit it removes or removes a part of,
    or the relation a column of which it removes."""
    bases: set[object] = set()
    for t in d.targets:
        match t:
            case RemoveUnit(unit=u) | RemoveAtom(unit=u) \
                    | RemoveDisjunct(unit=u):
                bases.update(read.units.get(u, ()))
            case RemoveColumn(relation=decl):
                rel = solver.program.declared_relation(decl)
                bases.update(read.relations.get(
                    rel.scoped_name, ()))
            case _:
                raise ValueError(f"a deletion removes {t}")
    return tuple(holding(groups, lambda c: c.base in bases))


def _cases_agree(reference: Profile) -> bool:
    """The pairs never part the `Choice` values, which a case column
    carries: on every pair, two or more cases that take no `@derive` or
    `@store` branch give grids, and all give the same grids."""
    for e in reference:
        bases = [(c, g) for c, g in e if c.is_base_case]
        if len({c for c, _ in bases}) < 2 or len({g for _, g in bases}) > 1:
            return False
    return True


@dataclass(frozen=True)
class _LeftOut:
    """A case column whose drop ungrounds a variable, which no row
    reports."""


@quotes("procedure.md", "Simplify",
        "Run `uv run python scripts/run_dl.py deletions <task_id>`.")
def survey_deletions(solver: Solver, runs: Runs) -> DeletionResult:
    """Structural deletions that change no pair's output and no determined
    value. A deletion outside the Determine comp holds when the program
    without it gives the stored program's profile of the witnessed cases on
    every pair, run on the groups of those cases that hold a case that
    depends on what it removes (`_depending`), a deletion on which no
    witnessed case depends holding on the pairs with no run, where its
    `impl_choice` still enumerates every base of the solver's cases
    (`_enumerates`), and, where the stored program's determination
    reproduces the stored values, the determination still does; a deletion
    inside the Determine comp holds when the determination still does. Where
    the solver has no Determine comp, the report says that no determination
    was checked. A row of `out` at a value that is no case counts for
    nothing. A deletion whose run fails for an ungrounded variable
    measured nothing, and a run that reached a limit is no result. Where the
    cases agree on every pair (`_cases_agree`), no case column is run;
    elsewhere a case column reads as any other column, and one whose drop
    ungrounds a variable is left out. A deletion left out or not run counts
    in no total."""
    engine, limits = runs.engine, runs.limits
    pairs = pairs_of(solver)
    cases = runs.cases
    reference = runs.profile(EVERY_SECTION)
    if isinstance(reference, Fails):
        return BaselineFails()
    if isinstance(reference, TimedOut):
        return reference
    determined = runs.determined
    base = reproduces(determined)
    if isinstance(base, TimedOut):
        return base
    stored_holds = base is True
    measured = determined.cpu_seconds \
        if isinstance(determined, Determined) else None
    agreed = _cases_agree(reference)
    dels = [d for d in deletions(solver, runs)
            if (not d.determine or stored_holds)
            and not (d.case_column and agreed)]
    dels = [d for d in dels if d.determine] + [d for d in dels
                                              if not d.determine]
    ref: Profile = reference
    assert isinstance(cases, tuple)
    bases = frozenset(choice_bases(cases)) \
        if enumerates(solver.program) else frozenset()

    own_enumeration = None
    if bases:
        own_enumeration = run_empty(engine, solver.program, [IMPL], limits)
        if not isinstance(own_enumeration, Tuples):
            raise ValueError("the solver's cases ran, and its own run of "
                             "`impl_choice` gives no rows")

    def _enumerates(variant: Solver, bases: frozenset[object]
                    ) -> bool | TimedOut | RunFailure:
        """Whether the variant's `impl_choice` still enumerates each of
        `bases`, the bases of the solver's cases, on the empty input; a
        variant that loses a case changes something. The run takes
        `variant_limits` of the solver's own run of `impl_choice`. The
        failure of that run where it fails."""
        if not bases:
            return True
        assert own_enumeration is not None
        spent = own_enumeration.cpu_seconds
        got = enumerated(engine, variant.program,
                         variant_limits(limits, spent))
        if not isinstance(got, tuple):
            return TimedOut(enumeration_failed(got, variant_bound(spent))) \
                if is_timeout(got) else got
        return bases <= set(got)

    groups = case_groups(solver, cases)
    read = dependence(engine, solver, bases_of(cases))
    built = [(d, p) for d in dels
             if (p := _program(solver, runs, d)) is not None]

    def judge(item: tuple[Deletion, Program]
              ) -> DeletionRow | TimedOutDeletion | _LeftOut | None:
        d, program = item
        variant = with_program(solver, program)

        def row(kind: DeletionKind, determination: bool) -> DeletionRow:
            return DeletionRow(d.line, kind, d.quote, determination)

        def timed(x: TimedOut) -> TimedOutDeletion:
            return TimedOutDeletion(d.line, d.kind, d.quote, x.finding)

        def ungrounded_row() -> DeletionRow | _LeftOut:
            """The outcome of a deletion whose run ungrounds a variable, so
            that it measured nothing."""
            return _LeftOut() if d.case_column \
                else row(DeletionKind.UNGROUNDED, False)

        if not d.determine:
            kept = _enumerates(variant, bases)
            if isinstance(kept, TimedOut):
                return timed(kept)
            if isinstance(kept, UngroundedVariable):
                return ungrounded_row()
            if kept is not True:
                return None
            depending = _depending(solver, groups, read, d)
            if depending:
                sub = restricted(ref, depending)
                got = profile(engine, variant, depending, pairs, limits, sub)
                if isinstance(got, TimedOut):
                    return timed(got)
                if got != sub:
                    if ungrounded(got):
                        return ungrounded_row()
                    return None
            if not stored_holds:
                return row(d.kind, False)
        holds = determines(engine, variant, limits, measured)
        if isinstance(holds, TimedOut):
            return timed(holds)
        return row(d.kind, d.determine) if holds is True else None

    outcomes = at_once(judge, built)
    rows = [r for r in outcomes if isinstance(r, DeletionRow)]
    timed = tuple(r for r in outcomes if isinstance(r, TimedOutDeletion))
    judged = (len(built) - len(timed)
              - sum(r.kind == DeletionKind.UNGROUNDED for r in rows)
              - sum(isinstance(r, _LeftOut) for r in outcomes))
    return DeletionReport(judged, tuple(rows), timed,
                          isinstance(base, NoDetermine))

