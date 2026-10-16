"""The lint checks on the components a solver holds: a comp that is lib
code, a `Parse` that `Determine` does not share, and a `Determine`
relation whose schema is not its parameter's."""

from dataclasses import replace

from checker.finding import (
    Finding,
    LintNamed,
    LintSentence,
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
from engine import Resolved
from engine.program import (
    POSE_COLUMN,
    FunctorDecl,
    RelationDecl,
    own,
)
from engine.quotes import quotes
from solver.category import Category
from solver.aggregate import (
    Solver,
)
from solver.determine import rigid_parameters
from solver.vocabulary import (
    DETERMINE,
    DETERMINE_SCOPE,
    PARSE,
)


@quotes("solver-file.md", "Components",
        "**Lib code.** A comp outside `Params`, `Determine`, and `Parse` is "
        "lib code, and a solver writes none.")
def check_lib_code(solver: Solver, runs: Runs) -> list[Finding]:
    """A comp the solver declares at the top level other than `Params`,
    `Determine` and `Parse`. Serves the purest form."""
    v = view(solver, runs)
    return [lint(spanned(c.span).first, LintNamed(
                Category.LIB_CODE, LintSentence.LIB_CODE, (c.name,)))
            for c in v.own_components
            if c.scope == TOP and c.name not in STOCK_COMPS]


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


@quotes("solver-file.md", "Determination",
        "`Determine` contains the determination as one relation per "
        "determined parameter, with the parameter's name and schema")
def check_determine_schema(solver: Solver, runs: Runs) -> list[Finding]:
    """A relation of `Determine` that takes a Params parameter's name and
    whose columns differ from that parameter's in name or type, the pose
    column of a parameter a RIGID call stores left out: the determination
    writes such a parameter's chart in a pose of its own (patterns.md, under
    "`RIGID` — parameter relations coupled as a rigid assembly"). Serves the
    purest form."""
    v = view(solver, runs)
    params = {p.name: p for p in solver.params.parameters}
    rigid = rigid_parameters(solver)
    out: list[Finding] = []
    for d in v.program.relations:
        p = params.get(d.name)
        if d.scope != DETERMINE_SCOPE or not own(d.span) or p is None:
            continue
        want = tuple(c for i, c in enumerate(p.columns)
                     if p.name not in rigid or i != POSE_COLUMN)
        if [(c.name, c.type.text) for c in d.columns] \
                == [(c.name, c.type.text) for c in want]:
            continue
        stored = v.decls.get(p.declaration)
        if not isinstance(stored, RelationDecl):
            raise ValueError(f"the parameter `{p.name}` has no relation "
                             "declaration")
        out.append(lint(d.span.first, LintNamed(
            Category.DETERMINE_SCHEMA, LintSentence.DETERMINE_SCHEMA,
            (solver.engine.text(replace(stored, columns=want)),))))
    return out
