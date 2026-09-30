"""The deletion survey: the structure of the solver whose removal changes
no pair's output and no determined value."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from enum import StrEnum

from checker.finding import Finding
from checker.lint.idioms import Columns, enumerator_binder
from checker.lint.view import view
from checker.runs import Runs
from checker.variants import (
    Fails,
    Profile,
    TimedOut,
    determines,
    pairs_of,
    parallel,
    profile,
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
    Scope,
)
from engine.program import (
    Aggregate,
    AtomLiteral,
    BinaryTerm,
    BodyLiteral,
    Cast,
    Comparison,
    ConstructorTerm,
    Disjunction,
    FunctorCall,
    IntrinsicCall,
    RecordTerm,
    Term,
    UnaryTerm,
    Unit,
)
from solver.model import Solver
from solver.solve import NoDetermine, Remove, variation
from solver.vocabulary import CHOICE, DETERMINE, OUTPUT


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
    CASE_COLUMN = "case column"
    """A column whose type is `Choice` or an ADT that stands in it."""
    UNPROBED_CASE = "unprobed case column"
    """A case column whose drop ungrounds a variable."""
    UNGROUNDED = "ungrounded deletion"
    """Any other deletion whose program ungrounds a variable."""
    UNEXERCISED_CASES = "unexercised cases"
    """The solver's `Choice`, where the pairs never part its cases and no
    case column stood in for them."""


UNMEASURED = frozenset({DeletionKind.UNPROBED_CASE, DeletionKind.UNGROUNDED})
"""The kinds of a deletion whose run measured nothing."""


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


@dataclass(frozen=True)
class TypeName:
    name: str


type Quote = Quoted | ColumnName | TypeName



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


@dataclass(frozen=True)
class DeletionRow:
    """A deletion that changes nothing, one no run judged, or the solver's
    unexercised cases. `determination` says the determination run alone
    judged it."""

    line: int
    kind: DeletionKind
    quote: Quote
    determination: bool

    @property
    def label(self) -> str:
        """The kind as the report prints it."""
        if self.determination:
            return f"determination {self.kind}"
        return str(self.kind)


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


def _own(u: Unit) -> bool:
    return u.span is not None and u.span.file is None


def _in_determine(scope: Scope) -> bool:
    return scope.components[:1] == (DETERMINE,)


def _term_aggregates(term: Term) -> list[Aggregate]:
    """The aggregates a term holds, left to right, not those inside
    another aggregate."""
    match term:
        case Aggregate():
            return [term]
        case ConstructorTerm(args=args) | RecordTerm(args=args) \
                | IntrinsicCall(args=args) | FunctorCall(args=args):
            return [a for x in args for a in _term_aggregates(x)]
        case UnaryTerm(arg=arg) | Cast(term=arg):
            return _term_aggregates(arg)
        case BinaryTerm(lhs=lhs, rhs=rhs):
            return _term_aggregates(lhs) + _term_aggregates(rhs)
        case _:
            return []


def _aggregates(lit: BodyLiteral) -> list[Aggregate]:
    """The aggregates a literal's terms hold, left to right, in the order
    a removal path counts them."""
    match lit:
        case AtomLiteral(atom=atom):
            return [a for t in atom.args for a in _term_aggregates(t)]
        case Comparison(lhs=lhs, rhs=rhs):
            return _term_aggregates(lhs) + _term_aggregates(rhs)
        case _:
            return []


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
            for k, agg in enumerate(_aggregates(lit)):
                yield from _parts(agg.body, (*here, k), True)


def _clauses(solver: Solver) -> list[tuple[Unit, tuple[Unit, ...]]]:
    """The solver's own rules, one per clause: a clause with several heads
    comes once, as its first unit, with every unit of it."""
    groups: dict[tuple[object, ...], list[Unit]] = {}
    for u in solver.program.units:
        if not _own(u) or u.body is None or u.span is None:
            continue
        groups.setdefault((u.span.first, u.span.last, u.body), []).append(u)
    return sorted(((us[0], tuple(us)) for us in groups.values()),
                  key=lambda g: (g[0].span.first if g[0].span else 0))


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
    case_types = {CHOICE} | ({p.type for p in solver.choice.points}
                             if solver.choice is not None else set())
    for decl in solver.program.relations:
        if decl.scope.components or decl.span.file is not None \
                or decl.name == OUTPUT.name or len(decl.columns) < 2:
            continue
        for i, col in enumerate(decl.columns):
            kind = DeletionKind.CASE_COLUMN if col.type in case_types \
                else DeletionKind.COLUMN
            out.append(Deletion(decl.span.first, kind,
                                ColumnName(decl.name, col.name),
                                (RemoveColumn(decl.id, i),), False))
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


def _cases_agree(reference: Profile) -> bool:
    """The pairs never part the `Choice` values, which a case column
    carries: on every pair, two or more cases that take no `@derive` or
    `@store` branch give grids, and all give the same grids."""
    for e in reference:
        bases = [(c, g) for c, g in e if not c.branches]
        if len({c for c, _ in bases}) < 2 or len({g for _, g in bases}) > 1:
            return False
    return True


def survey_deletions(solver: Solver, runs: Runs) -> DeletionResult:
    """Structural deletions that change no pair's output and no determined
    value (procedure.md:138, the audit's deletion section,
    prompts/run_dl.md). A deletion outside the Determine comp holds when
    the program without it gives the stored program's profile on every
    pair and, where the stored program's determination reproduces the
    stored values, the determination still does; a deletion inside the
    Determine comp holds when the determination still does. Where the
    solver has no Determine comp, the report says that no determination
    was checked. A deletion
    whose run fails for an ungrounded variable measured nothing, and a
    run that reached a limit is no result. A case column's rows stand
    apart; where the pairs part the cases, a case column reads as any
    other column, and an unprobed one is left out. Where the solver has
    two or more cases of the solver, no case column stood for them, and the pairs
    never part them, the `Choice` reports as unexercised."""
    engine, limits = runs.engine, runs.limits
    pairs = pairs_of(solver)
    reference = profile(engine, solver, pairs, limits)
    if isinstance(reference, Fails):
        return BaselineFails()
    if isinstance(reference, TimedOut):
        return reference
    base = determines(engine, solver, limits)
    if isinstance(base, TimedOut):
        return base
    reproduces = base is True
    dels = [d for d in deletions(solver, runs)
            if not d.determine or reproduces]
    dels = [d for d in dels if d.determine] + [d for d in dels
                                              if not d.determine]
    ref: Profile = reference
    built = [(d, p) for d in dels
             if (p := _program(solver, runs, d)) is not None]

    def judge(item: tuple[Deletion, Program]
              ) -> DeletionRow | TimedOutDeletion | None:
        d, program = item
        variant = with_program(solver, program)

        def row(kind: DeletionKind, determination: bool) -> DeletionRow:
            return DeletionRow(d.line, kind, d.quote, determination)

        if not d.determine:
            got = profile(engine, variant, pairs, limits, ref)
            if isinstance(got, TimedOut):
                return TimedOutDeletion(d.line, d.kind, d.quote, got.finding)
            if got != ref:
                if ungrounded(got):
                    return row(DeletionKind.UNPROBED_CASE
                               if d.kind == DeletionKind.CASE_COLUMN
                               else DeletionKind.UNGROUNDED, False)
                return None
            if not reproduces:
                return row(d.kind, False)
        holds = determines(engine, variant, limits)
        if isinstance(holds, TimedOut):
            return TimedOutDeletion(d.line, d.kind, d.quote, holds.finding)
        return row(d.kind, d.determine) if holds is True else None

    outcomes = parallel(judge, built)
    rows = [r for r in outcomes if isinstance(r, DeletionRow)]
    timed = tuple(r for r in outcomes if isinstance(r, TimedOutDeletion))
    judged = (len(built) - len(timed)
              - sum(r.kind in UNMEASURED for r in rows))
    rows = _case_rows(solver, rows, _cases_agree(ref))
    return DeletionReport(judged, tuple(rows), timed,
                          isinstance(base, NoDetermine))


def _case_rows(solver: Solver, rows: list[DeletionRow], agreed: bool
               ) -> list[DeletionRow]:
    """The rows with the cases settled by the pairs: where a case column
    fired, and some pair parts the cases, a case column reads as any other
    column and an unprobed one is left out; where none fired, the solver
    has two or more cases, and no pair parts them, the `Choice` reports as
    unexercised."""
    if any(r.kind in (DeletionKind.CASE_COLUMN, DeletionKind.UNPROBED_CASE)
           for r in rows):
        if agreed:
            return rows
        return [replace(r, kind=DeletionKind.COLUMN)
                if r.kind == DeletionKind.CASE_COLUMN else r
                for r in rows if r.kind != DeletionKind.UNPROBED_CASE]
    choice = solver.choice
    if choice is not None and agreed:
        decl = next((t for t in solver.program.types
                     if t.id == choice.declaration), None)
        if decl is not None:
            return [*rows, DeletionRow(decl.span.first,
                                       DeletionKind.UNEXERCISED_CASES,
                                       TypeName(decl.name), False)]
    return rows
