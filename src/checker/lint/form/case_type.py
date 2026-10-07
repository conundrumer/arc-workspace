"""The lint checks on a solver's case type: a family's case, the case
markers, and the gloss of `Choice` and of its constructors; with the
choice ADTs and the comment block above a line, which other checks
of the form read."""


from checker.finding import (
    Finding,
    LintFamily,
    LintNamed,
    LintSentence,
)
from checker.judged import (
    parse_failure,
    representative,
)
from checker.lint.view import (
    View,
    lint,
    view,
)
from checker.runs import Runs
from engine import (
    ParseFailure,
)
from engine.program import (
    AdtType,
    DeclId,
)
from engine.quotes import quotes
from solver.category import Category
from solver.model import (
    ChoicePoint,
)
from solver.aggregate import (
    Solver,
)


@quotes("solver-file.md", "Header",
        "// @representative: <family's first-solved task id> <Case when the "
        "sibling has one case of its Choice>")
@quotes("principles.md", "Models and tasks",
        "**sibling task**: another task in the family of this task's model.")
@quotes("style.md", "Cases",
        "**Concept branch.** The concept branch is declared first in `Choice`")
def check_family_case(solver: Solver, runs: Runs) -> list[Finding]:
    """A `@representative:` case name the representative's `Choice` does not
    hold: the name denotes one case of the representative's `Choice`, so it
    stands among that type's constructors. Serves the concept's form: the
    sibling names its family's case."""
    rep = solver.annotations.representative
    if rep is None or rep.case is None:
        return []
    case = rep.case
    other = representative(solver, runs.engine)
    if other is None:
        return []

    def flag(sentence: LintSentence,
             failure: ParseFailure | None = None) -> list[Finding]:
        return [lint(rep.line, LintFamily(Category.FAMILY_CASE, sentence,
                                          rep.task_id, case, failure))]

    failed = parse_failure(other)
    if failed is not None:
        return flag(LintSentence.FAMILY_NOT_PARSED, failed)
    if other.choice is None:
        return flag(LintSentence.FAMILY_NO_CHOICE)
    if other.choice.record is not None:
        return flag(LintSentence.FAMILY_RECORD)
    top = [c.name for p in other.choice.points if not p.path
           for c in p.constructors]
    return [] if rep.case in top else flag(LintSentence.FAMILY_NO_CASE)


@quotes("solver-file.md", "Cases",
        "The comma separates names.")
@quotes("style.md", "Params",
        "A parameter that some case never reads goes under the marker of the "
        "cases that read it.")
def check_case_marker(solver: Solver, runs: Runs) -> list[Finding]:
    """A case marker whose case names are joined by `/`. Serves readability."""
    return [lint(m.line, LintNamed(Category.CASE_MARKER,
                                   LintSentence.MARKER_SLASH, ()))
            for m in solver.annotations.markers
            if any(p.slash_joined for p in m.parts)]


def choice_adts(solver: Solver, v: View
                 ) -> list[tuple[bool, ChoicePoint, AdtType]]:
    """The choice points of `Choice`, one per ADT, with whether the ADT is
    `Choice` itself, and its declaration as the model resolves it."""
    if solver.choice is None:
        return []
    out: list[tuple[bool, ChoicePoint, AdtType]] = []
    seen: set[DeclId] = set()
    for p in solver.choice.points:
        td = v.decls.get(p.declaration)
        if isinstance(td, AdtType) and p.declaration not in seen:
            seen.add(p.declaration)
            out.append((not p.path and solver.choice.record is None, p, td))
    return out


def comment_block_above(v: View, line: int) -> list[int]:
    """The lines of the own-line comments directly above `line`, nearest
    first, stopping at a case marker."""
    out: list[int] = []
    n = line - 1
    while n in v.comment_lines and n not in v.marker_lines:
        out.append(n)
        n -= 1
    return out


@quotes("style.md", "Cases",
        "**Choice gloss.** The gloss of a choice is above its type, and "
        "nowhere else.")
@quotes("principles.md", "Choice points and open parameters",
        "**branch**: one possible answer to a choice point.")
def check_gloss(solver: Solver, runs: Runs) -> list[Finding]:
    """`Choice` lacking its gloss above the type, and a constructor of a
    choice ADT that opens no line of its own. Serves readability: each
    branch's directive lines are its description."""
    v = view(solver, runs)
    marks, comments = v.marker_lines, v.comment_lines
    out: list[Finding] = []
    for is_choice, _p, td in choice_adts(solver, v):
        above = td.span.first - 1
        if is_choice and (above not in comments or above in marks):
            out.append(lint(td.span.first, LintNamed(
                Category.GLOSS, LintSentence.GLOSS_ABOVE, (td.name,))))
        for c in td.constructors:
            if not c.own_line:
                out.append(lint(td.span.first, LintNamed(
                    Category.GLOSS, LintSentence.OWN_LINE, (c.name,))))
    return out
