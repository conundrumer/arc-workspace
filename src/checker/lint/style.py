"""The lint checks that read the style doc beside the checks on shapes
the corpus's edits rewrite away (`checker.lint.rewrites`):
`choice-domain`, `shared-read` and `decl-placement`."""

from dataclasses import dataclass

from checker.finding import (
    Finding,
    LintMarked,
    LintNamed,
    LintSentence,
)
from checker.judged import base_names
from checker.lint.form.sections import case_column_facts
from checker.lint.view import (
    TOP,
    lint,
    view,
)
from checker.runs import Runs
from engine.program import (
    RelationDecl,
)
from engine.quotes import quotes
from solver.category import Category
from solver.model import bases_of, Section, UnderMarker, Unmarked, Parameter
from solver.aggregate import Solver, lists_case
from solver.readers import section_at
from solver.dependence import dependence
from solver.per_case import per_case
from solver.vocabulary import (
    OUTPUT,
)
from checker.lint.rewrites import unit_section


@quotes("principles.md", "Choice points and open parameters",
        "**choice point**: an undetermined property whose possible answers "
        "are models represented by cases.")
@quotes("solver-file.md", "Alt outputs",
        "The solver enumerates a tiebreak's resolutions through a trailing "
        "`out` column of type `TiebreakResolution`.")
def check_choice_domain(solver: Solver, runs: Runs) -> list[Finding]:
    """A `choice-domain` declaration in program code: the relation keeps
    one arbitrary tuple per key, so which one it keeps is a choice the
    program does not state. Serves the concept's form: every choice the
    model makes is stated (principles.md, under
    "Choice points and open parameters")."""
    v = view(solver, runs)
    return [lint(d.span.first, LintNamed(
                Category.CHOICE_DOMAIN, LintSentence.CHOICE_DOMAIN,
                (d.name,), d.choice_domain))
            for d in v.program_relations() if d.choice_domain]


@quotes("solver-file.md", "Cases",
        "**Case markers.** Cases do not interleave: each case's Params and "
        "clauses are under its marker.")
@quotes("style.md", "Params",
        "A parameter that every case reads is declared above the case "
        "markers, and so are its facts when it has no case column. A "
        "parameter that some case never reads goes under the marker of the "
        "cases that read it.")
@quotes("solver-file.md", "Params",
        "Each of its facts stands under the marker of the case its case "
        "column holds.")
def check_shared_read(solver: Solver, runs: Runs) -> list[Finding]:
    """A parameter under a marker that lists no case, below a marker that
    lists one; a fact under a marker of a shared parameter with no case
    column (`solver.per_case.per_case`); a fact of a parameter with a case
    column outside the marker of its case (`case_column_facts`); and a
    shared parameter some case of the solver never reads
    (`solver.dependence.Dependence.reads_parameter`), or that no case reads,
    which no marker of a case is the place of. The last two are judged
    where the run that enumerates the solver's cases gives a result. A
    marker that lists no case above every marker that lists one leaves the
    parameters under it shared. Every relation `Params` declares is read, a
    derived one too, since the rule is about what cases share, whatever
    feeds the relation. Where one stands is `Parameter.section` or
    `DerivedRelation.section`. Serves the concept's form."""
    v = view(solver, runs)
    choice = solver.choice
    if choice is None:
        return []
    written = {d.id: d for d in v.written_relations}
    out: list[Finding] = []
    shared: list[tuple[str, RelationDecl]] = []
    for p in (*solver.params.parameters, *solver.params.derived):
        d = written.get(p.declaration)
        if d is None:
            continue
        match p.section:
            case Unmarked():
                shared.append((p.name, d))
                if isinstance(p, Parameter) and \
                        per_case(solver, p.name) is None:
                    out += [lint(line, LintMarked(
                        Category.SHARED_READ, LintSentence.SHARED_FACT_MARKED,
                        d.name, m))
                        for _u, line, m in v.marked_facts(d) if m is not None]
            case UnderMarker(marker=m) if not lists_case(solver, m):
                out.append(lint(d.span.first, LintMarked(
                    Category.SHARED_READ, LintSentence.MARKER_LISTS_NO_CASE,
                    d.name, m)))
            case UnderMarker():
                pass
    every = runs.solver_cases
    if not isinstance(every, tuple):
        return out
    out += case_column_facts(solver, v, every)
    bases = bases_of(every)
    rd = dependence(runs.engine, solver, bases)
    for name, d in sorted(shared, key=lambda s: s[1].name):
        unread = [b for b in bases if not rd.reads_parameter(b, name)]
        if len(unread) == len(bases):
            out.append(lint(d.span.first, LintMarked(
                Category.SHARED_READ, LintSentence.SHARED_NO_READER, d.name,
                None)))
        elif unread:
            out.append(lint(d.span.first, LintMarked(
                Category.SHARED_READ, LintSentence.SHARED_UNREAD_BY_ONE
                if len(unread) == 1 else LintSentence.SHARED_UNREAD, d.name,
                None, cases=base_names(solver, unread, bases))))
    return out


@dataclass(frozen=True)
class InComp:
    """The clauses of a component."""

    comp: str


@dataclass(frozen=True)
class InSection:
    """A top-level section (`solver.readers.section_at`)."""

    section: Section


type Spot = InComp | InSection
"""Where a relation's references stand."""


@quotes("style.md", "Layout",
        "a file takes its block order and layout from it.")
def check_decl_placement(solver: Solver, runs: Runs) -> list[Finding]:
    """A top-level declaration whose every reference stands in one section
    or comp it is not in: move it there. `out` is the interface, declared
    under `Choice`. Serves readability."""
    v = view(solver, runs)
    out: list[Finding] = []
    for d in v.written_relations:
        if d.scope != TOP or d.name == OUTPUT.name:
            continue
        spots: set[Spot] = set()
        units = [*v.defs(d), *(u for u, _a, _n in v.uses(d))]
        for u in units:
            if u.scope != TOP:
                spots.add(InComp(u.scope.components[0]))
            else:
                spots.add(InSection(unit_section(v, u)))
        if len(spots) != 1:
            continue
        spot = spots.pop()
        if spot == InSection(Unmarked()) \
                or spot == InSection(section_at(solver, TOP, d.span.first)):
            continue
        out.append(lint(d.span.first, LintMarked(
            Category.DECL_PLACEMENT, LintSentence.DECL_PLACEMENT, d.name,
            spot.section.marker if isinstance(spot, InSection)
            and isinstance(spot.section, UnderMarker) else None,
            spot.comp if isinstance(spot, InComp) else None)))
    return out
