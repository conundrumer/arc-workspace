"""The lint checks on a solver's case sections: the facts of a case
column, a fact outside its case section, and a case section a case
does not read."""

from collections.abc import Collection, Iterator, Sequence

from checker.finding import (
    Finding,
    LintCaseValue,
    LintMarked,
    LintNamed,
    LintSentence,
)
from checker.judged import (
    base_names,
)
from checker.lint.view import (
    TOP,
    View,
    lint,
    literal_terms,
    spanned,
    subterms,
    tag_fact,
    view,
)
from checker.runs import Runs
from engine.program import (
    AtomLiteral,
    BodyLiteral,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    DeclId,
    Disjunction,
    RelationDecl,
    Term,
    Unit,
)
from engine.program import subterms as direct_subterms
from engine.quotes import quotes
from solver.annotations import (
    CaseMarker,
)
from solver.category import Category
from solver.model import (
    bases_of,
    choice_bases,
    Base,
    Case,
    other_branches,
)
from solver.aggregate import (
    Solver,
    marker_at,
    row_value,
)
from solver.graph import Node
from solver.dependence import (
    dependence,
)
from solver.names import (
    Denoted,
    cases_of,
    constructors_fixed,
    denote,
)
from solver.solve import PerCase, per_case
from checker.lint.form.case_type import choice_adts
from checker.lint.form.declared_types import all_literals
from checker.lint.form.witnesses import at_choice


def _admitting_terms(lit: BodyLiteral | None, unit: Unit) -> list[Term]:
    """The top-level terms of one literal, less those of a negated atom
    and of a `!=` comparison, which shut a case out rather than admit
    it."""
    if lit is None:
        return list(unit.head.args)
    if isinstance(lit, AtomLiteral) and lit.negated:
        return []
    if isinstance(lit, Comparison) and lit.op == ComparisonOperator.NE:
        return []
    if isinstance(lit, Disjunction):
        return [t for b in lit.branches for sub in b
                for t in _admitting_terms(sub, unit)]
    return list(literal_terms(lit))


def _case_values(term: Term, ctors: Collection[str]) -> Iterator[Term]:
    """The outermost terms in `term` that apply a constructor of `ctors`,
    left to right; none inside an aggregate, whose terms stand in its own
    body."""
    if isinstance(term, ConstructorTerm) and term.name in ctors:
        yield term
        return
    for t in direct_subterms(term):
        yield from _case_values(t, ctors)


def _marks(solver: Solver, marker: CaseMarker,
           cases: Sequence[Case]) -> list[frozenset[Case]] | None:
    """For each name of a marker that denotes cases, the cases of the
    solver it lists (`cases_of`); None where every name is prose or
    denotes nothing, so the marker marks nothing."""
    out: list[frozenset[Case]] = []
    for p in marker.parts:
        if p.prose:
            continue
        d = denote(solver, p.name)
        if not isinstance(d, Denoted):
            continue
        out.append(frozenset(cases_of(solver, d, cases)))
    return out or None


def _lists(solver: Solver, marker: CaseMarker | None, every: Sequence[Case],
           taking: frozenset[Case]) -> bool:
    """Whether a line of the cases `taking` stands under their marker:
    not above the first marker that lists a case (`marker` None), and not
    under a marker none of whose names lists cases (`cases_of`) that are
    all of `taking`. A marker whose names are prose marks nothing and is
    neutral."""
    if marker is None:
        return False
    marked = _marks(solver, marker, every)
    return marked is None or any(m and m <= taking for m in marked)


def _misplaced(solver: Solver, marker: CaseMarker | None,
               every: Sequence[Case], taking: frozenset[Case]) -> bool:
    """Whether a line of the cases `taking` stands outside their marker
    (`_lists`); a line of no case of the solver is not judged."""
    return bool(taking) and not _lists(solver, marker, every, taking)


def _case_column_parameters(solver: Solver
                            ) -> Iterator[tuple[DeclId, PerCase]]:
    """Each parameter with a case column, by its declaration, with its
    case reading (`solver.solve.per_case`)."""
    for p in solver.params.parameters:
        if (pc := per_case(solver, p.name)) is not None:
            yield p.declaration, pc


def case_column_facts(solver: Solver, v: View, every: Sequence[Case]
                      ) -> list[Finding]:
    """A fact of a parameter with a case column that stands outside the
    marker of the cases its case values hold at (`_lists`,
    `solver.solve.PerCase.holds`), a `shared-read` finding naming their
    bases, as a shared fact under a marker is. A fact whose
    value the load reads as no constant is the load's fault, and a fact
    whose case values hold at no case of the solver belongs to no case's
    marker."""
    out: list[Finding] = []
    constants = solver.lib.constants
    for decl, pc in _case_column_parameters(solver):
        d = v.decls[decl]
        assert isinstance(d, RelationDecl)
        for u, line, marker in v.marked_facts(d):
            row = row_value(u.head.args, constants)
            if row is None:
                continue
            taking = frozenset(c for c in every
                               if pc.holds(solver, c.base, row))
            if not _misplaced(solver, marker, every, taking):
                continue
            out.append(lint(line, LintNamed(
                Category.SHARED_READ, LintSentence.CASE_COLUMN_FACT,
                base_names(solver, bases_of(c for c in every
                                            if c in taking),
                           bases_of(every)))))
    return out


@quotes("solver-file.md", "Cases",
        "**Case markers.** Cases do not interleave: each case's Params and "
        "clauses are under its marker.")
@quotes("style.md", "Params",
        "A parameter that some case never reads goes under the marker of the "
        "cases that read it.")
def check_case_section(solver: Solver, runs: Runs) -> list[Finding]:
    """A top-level clause that contains a constructor of a choice ADT other
    than its type's first, and stands outside the marker of the cases its
    case value denotes (`_lists`), one hint that names its case value: the
    outermost terms that apply a choice-ADT constructor. Its case value
    denotes `cases_of` the branches of every choice-ADT constructor it
    contains, a nested one and a first one among them
    (`constructors_fixed`); where those constructors denote no case of the
    solver, the clause is a clause of no case and is not judged, above the
    first marker as under one. A constructor under a negation or a
    `!=` does not count; a clause of an enumerator, and a fact of one constructor or
    record, belong to no case. A fact of a parameter with a case column is
    judged by the `shared-read` lint (`case_column_facts`).
    The clauses on one line that give one hint give it once. Where the run that enumerates the solver's cases gives no
    result, a clause under a marker, a fact of a parameter with a case
    column among them, is not judged, and a hint at `Choice` says so with
    the run's failure. Serves readability."""
    v = view(solver, runs)
    points = [p for _, p, _td in choice_adts(solver, v)]
    ctors = {c.name for p in points for c in p.constructors}
    others = {c.name for p in points for c in other_branches(p)}
    if not others:
        return []
    enums = v.enumerators
    every = runs.solver_cases
    out: list[Finding] = []
    unjudged = False
    for u in v.own_units:
        if u.scope != TOP or (not u.head.relation.instances
                              and u.head.relation.name in enums):
            continue
        if tag_fact(u):
            continue
        values = tuple(dict.fromkeys(
            value for lit in all_literals(u)
            for top in _admitting_terms(lit, u)
            for value in _case_values(top, ctors)))
        named = list(dict.fromkeys(
            t.name for value in values for t in subterms(value)
            if isinstance(t, ConstructorTerm) and t.name in ctors))
        fixed = constructors_fixed(solver, named)
        if not any(n in others for n in named) or fixed is None \
                or u.span is None:
            continue
        marker = marker_at(solver, u.scope, u.span.first)
        if marker is not None and not isinstance(every, tuple):
            unjudged = True
            continue
        if isinstance(every, tuple):
            taking = frozenset(cases_of(solver, Denoted(fixed, ()), every))
            if not _misplaced(solver, marker, every, taking):
                continue
        out.append(lint(u.span.first, LintCaseValue(
            Category.CASE_SECTION,
            LintSentence.CASE_SECTION_BEFORE if marker is None
            else LintSentence.CASE_SECTION_UNDER, values, marker)))
    if not isinstance(every, tuple) and any(
            _case_column_parameters(solver)):
        unjudged = True
    if unjudged and solver.choice is not None \
            and not isinstance(every, tuple):
        out.append(at_choice(v, solver.choice, Category.CASE_SECTION,
                              LintSentence.CASE_SECTION_UNJUDGED, every))
    return list(dict.fromkeys(out))


@quotes("solver-file.md", "Cases",
        "**Case markers.** Cases do not interleave: each case's Params and "
        "clauses are under its marker.")
@quotes("style.md", "Params",
        "A parameter that some case never reads goes under the marker of the "
        "cases that read it.")
def check_case_section_read(solver: Solver, runs: Runs) -> list[Finding]:
    """A clause that feeds a relation some cases read, where the clause
    stands under a marker that does not list them
    (`solver.dependence.Dependence.stranded`): the program runs the clause for
    those cases, so its marker does not list every case that reads it. The
    marker finding of `solver.dependence.dependence`, which the `store` report
    prints too. One finding per solver line, relation and marker: the clauses
    on one line that feed one relation under one marker give one finding, on
    that line, naming through `cover` the cases that read any of them. Where
    the run that enumerates the solver's cases gives no result, nothing is
    judged, and a hint at `Choice` says so with the run's failure. Serves
    the purest form."""
    every = runs.solver_cases
    if solver.choice is None:
        return []
    if not isinstance(every, tuple):
        return [at_choice(view(solver, runs), solver.choice,
                           Category.CASE_SECTION,
                           LintSentence.CASE_SECTION_READ_UNJUDGED, every)]
    bases = bases_of(every)
    among = choice_bases(every)
    if not among:
        return []
    rd = dependence(runs.engine, solver, bases)
    by_id = {u.id: u for u in solver.program.units}
    lines: dict[tuple[int, Node, CaseMarker], set[Base | None]] = {}
    for (uid, node), reaching in rd.stranded.items():
        u = by_id[uid]
        line = spanned(u.span).first
        # A stranded unit stands under a marker (`Dependence.stranded`).
        marker = marker_at(solver, u.scope, line)
        if marker is None:
            raise ValueError(f"a stranded unit at line {line} under no marker")
        lines.setdefault((line, node, marker),
                         set()).update(reaching)
    return [lint(line, LintMarked(
        Category.CASE_SECTION, LintSentence.CASE_SECTION_READ, node.text,
        marker, cases=base_names(solver, [b for b in among if b in reaching],
                                 among)))
        for (line, node, marker), reaching in lines.items()]
