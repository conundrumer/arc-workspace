"""The lint checks on the components a solver holds: a component with
no entry, and a `Parse` that `Determine` does not share."""

from collections.abc import Sequence

from checker.finding import (
    Finding,
    LintNamed,
    LintSentence,
)
from checker.judged import (
    concept_among,
    reading_names,
)
from checker.lint.view import (
    STOCK_COMPS,
    TOP,
    View,
    atoms_read,
    lint,
    spanned,
    view,
)
from checker.runs import Runs
from engine import (
    Resolved,
    checkout,
)
from engine.program import (
    FunctorDecl,
)
from engine.quotes import quotes
from solver.category import Category
from solver.model import (
    bases_of,
)
from solver.aggregate import (
    Solver,
)
from solver.dependence import (
    dependence,
    dependent_bases,
)
from solver.vocabulary import (
    DETERMINE,
    DETERMINE_SCOPE,
    PARSE,
)


@quotes("style.md", "Components",
        "A proposal comp with no entry is a hint.")
@quotes("solver-file.md", "Components",
        "A comp outside `Params`, `Determine`, and `Parse` is lib code, and a "
        "solver writes one only as a proposal comp")
@quotes("lib-protocol.md", "In the pass",
        "**Proposal comp.** If those relations need a banned form and the "
        "concept case reads them, place them in a proposal comp")
@quotes("style.md", "Components",
        "**Proposal comps.** The program-style checks skip a proposal comp.")
def check_comp_without_entry(solver: Solver, runs: Runs) -> list[Finding]:
    """A proposal comp with no entry under docs/wf-solver/proposals/, a
    hint. Serves the purest form: the comp is lib code on its way out of the
    solver. A proposal comp whose relations no derivation of the concept
    case reads (`solver.dependence.dependence`) is a `proposal comp` lint in
    place of that hint, naming through `cover` the cases whose derivations
    read them."""
    v = view(solver, runs)
    comps = [c for c in v.own_components
             if c.scope == TOP and c.name not in STOCK_COMPS]
    dependents = _comp_dependents(solver, runs, [c.name for c in comps])
    out: list[Finding] = []
    for c in comps:
        line = spanned(c.span).first
        got = dependents.get(c.name)
        if got is not None:
            out.append(lint(line, LintNamed(
                Category.PROPOSAL_COMP, LintSentence.PROPOSAL_UNREAD,
                (c.name, *got))))
        elif not checkout.proposal_entry(c.name).is_file():
            out.append(lint(line, LintNamed(
                Category.COMP_WITHOUT_ENTRY, LintSentence.NO_PROPOSAL_ENTRY,
                (c.name,))))
    return out


def _comp_dependents(solver: Solver, runs: Runs, comps: Sequence[str]
                     ) -> dict[str, tuple[str, ...]]:
    """Each of `comps` whose units no derivation of the concept case
    depends on (`solver.dependence.dependence`), with the fewest names that
    cover the cases whose derivations depend on one of them; none where
    the run that enumerates the solver's cases gives no result."""
    every = runs.solver_cases
    if not comps or not isinstance(every, tuple):
        return {}
    bases = bases_of(every)
    rd = dependence(runs.engine, solver, bases)
    out: dict[str, tuple[str, ...]] = {}
    for name in comps:
        reading = dependent_bases(rd, (u.id for u in solver.program.units
                                       if u.scope.components[:1] == (name,)))
        if concept_among(solver, reading) is not None:
            continue
        out[name] = reading_names(solver, every, reading)
    return out


@quotes("solver-file.md", "Parse",
        "A `.comp Parse<Key>` contains a derivation that the program and the "
        "Determine comp share.")
@quotes("style.md", "Components",
        "**Shared comp instances.** A comp instance is shared exactly when "
        "its case-specific versions differ only in the case name.")
def check_parse_unshared_with_determine(solver: Solver, runs: Runs
                                        ) -> list[Finding]:
    """A `Parse` comp that no `Determine` comp reads. Serves the purest
    form."""
    v = view(solver, runs)
    parse = next((c for c in v.own_components if c.name == PARSE), None)
    if parse is None:
        return []
    determine = next((c for c in v.own_components if c.name == DETERMINE),
                     None)
    if determine is not None and _reads_parse(v):
        return []
    return [lint(spanned(parse.span).first, LintNamed(
        Category.PARSE_UNSHARED_WITH_DETERMINE, LintSentence.PARSE_UNREAD,
        ()))]


def _reads_parse(v: View) -> bool:
    """`Determine` holds a `Parse` instance, or a clause of it reads a
    relation `Parse` declares."""
    if any(i.component == PARSE and i.scope == DETERMINE_SCOPE
           for i in v.program.instances):
        return True
    for u in v.own_units:
        if u.scope.components[:1] != (DETERMINE,):
            continue
        for a in atoms_read(u):
            r = v.index.resolve(a.relation, u.scope)
            if isinstance(r, Resolved):
                d = v.decls.get(r.declaration)
                if d is not None and not isinstance(d, FunctorDecl) \
                        and d.scope.components[:1] == (PARSE,):
                    return True
    return False
