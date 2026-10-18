"""The lint checks on a solver's witnesses and claims: each branch's
witness, a solver of one case, and the scene claims; with the hint at
`Choice` that the run of the cases gave no result."""


from checker.finding import (
    Finding,
    LintLabeled,
    LintNamed,
    LintRun,
    LintSentence,
)
from checker.judged import (
    is_timeout,
    representative,
)
from checker.lint.view import (
    STOCK_COMPS,
    TOP,
    View,
    lint,
    spanned,
    view,
)
from checker.runs import Runs
from engine import (
    RunFailure,
)
from engine.program import (
    own,
)
from engine.quotes import quotes
from solver.annotations import (
    DirectiveWord,
    Plausibility,
)
from solver.category import Category
from solver.model import (
    Choice,
    concept_branch,
)
from solver.aggregate import Solver, branch_witnesses
from solver.readers import choice_line
from solver.vocabulary import (
    PARSE,
)
from checker.lint.form.case_type import choice_adts, comment_block_above


@quotes("principles.md", "Witnesses",
        "`ordinary`: readily, breaking no scene claim of the concept case.")
@quotes("procedure.md", "Witness",
        "`@relaxed` for the scene claim it breaks, which rules out `ordinary`")
@quotes("procedure.md", "Witness",
        "A witness of the concept case stands under the branch its verdict "
        "denotes, and with verdict `other` under an `@approximated:` line of "
        "the rule whose approximation disagrees on it.")
@quotes("principles.md", "Witnesses",
        "A branch's witnesses are divergence witnesses between its model and "
        "the concept branch's model.")
def check_witness(solver: Solver, runs: Runs) -> list[Finding]:
    """A `@witness`, `@derive` or `@store` line at `ordinary` that holds
    `@relaxed`; a concept branch that holds a `@witness` line, and a
    `@witness` line under neither a branch nor an `@approximated:` line.
    Serves the concept's form."""
    v = view(solver, runs)
    ann = solver.annotations
    out: list[Finding] = []
    labeled = (
        [(w.line, LintLabeled(Category.WITNESS, LintSentence.ORDINARY_RELAXED,
                              DirectiveWord.WITNESS, w.id, tuple(w.relaxed)),
          w.plausibility) for w in ann.witnesses]
        + [(d.line, LintLabeled(Category.WITNESS,
                                LintSentence.ORDINARY_RELAXED,
                                DirectiveWord.DERIVE, d.proposer,
                                tuple(d.relaxed)), d.plausibility)
           for d in ann.derives]
        + [(s.line, LintLabeled(Category.WITNESS,
                                LintSentence.ORDINARY_RELAXED,
                                DirectiveWord.STORE, None, tuple(s.relaxed)),
            s.plausibility) for s in ann.stores])
    for line, payload, plausibility in labeled:
        if plausibility == Plausibility.ORDINARY and payload.relaxed:
            out.append(lint(line, payload))
    for _is_choice, p, _td in choice_adts(solver, v):
        first = concept_branch(p)
        if not first.own_line:
            continue
        if branch_witnesses(solver, first.name):
            out.append(lint(first.line, LintNamed(
                Category.WITNESS, LintSentence.CONCEPT_WITNESS,
                (first.name,))))
    for w in ann.witnesses:
        if w.constructor is None and w.approximates is None:
            out.append(lint(w.line, LintNamed(
                Category.WITNESS, LintSentence.WITNESS_PLACE, ())))
    return out


@quotes("solver-file.md", "Cases",
        "A solver with one case has no `Choice`, case markers, or case column "
        "on `out`.")
@quotes("principles.md", "Choice points and open parameters",
        "Each case takes one branch at each choice point at the concept, and "
        "at each under a branch it takes.")
def check_one_case(solver: Solver, runs: Runs) -> list[Finding]:
    """`Choice` in a solver with one case. Where the run that gives the
    solver's cases fails, whether it has one case is unknown, and the
    finding says so. Serves the purest form."""
    choice = solver.choice
    if choice is None:
        return []
    v = view(solver, runs)
    line = _choice_line(v, choice)
    solver_cases = runs.solver_cases
    if not isinstance(solver_cases, tuple):
        sentence = LintSentence.ONE_CASE_UNKNOWN_TIMEOUT \
            if is_timeout(solver_cases) else LintSentence.ONE_CASE_UNKNOWN_FAILED
        return [at_choice(v, choice, Category.ONE_CASE, sentence,
                           solver_cases)]
    if len(solver_cases) != 1:
        return []
    return [lint(line, LintRun(Category.ONE_CASE, LintSentence.ONE_CASE,
                               solver_cases[0]))]


def at_choice(v: View, choice: Choice, category: Category,
               sentence: LintSentence, failure: RunFailure) -> Finding:
    """The hint at `Choice` that the run that enumerates the solver's
    cases gave no result, so what `category` judges is unknown."""
    return lint(_choice_line(v, choice), LintRun(category, sentence, failure))


def _choice_line(v: View, choice: Choice) -> int:
    """The line `Choice`'s declaration starts on."""
    return choice_line(v.program, choice)


def _constructions(v: View) -> frozenset[str]:
    """The lib components whose `.comp` line ends with `// @construction`
    (solver-file.md, under "Program"): an instance of one builds a term the model
    reads through, and serves no claim of its own."""
    trailing = {(c.file, c.line) for c in v.program.comments
                if not c.own_line and c.text.strip()
                .startswith("@construction")}
    return frozenset(c.name for c in v.program.components
                     if c.span is not None and not own(c.span)
                     and (c.span.file, c.span.first) in trailing)


@quotes("solver-file.md", "Program",
        "**`@claim` directive.** At program scope or inside `Parse`, an "
        "instance of a component without an `@construction` mark has the "
        "directive, one line per instance, listing the claims the instance "
        "serves.")
@quotes("solver-file.md", "Program",
        "Each slug denotes a claim.")
@quotes("solver-file.md", "Cases",
        "`@claim` under the concept branch's constructor denotes the header "
        "claim the choice point turns on")
@quotes("encoding.md", "Component instances",
        "In the program, an instance of a component that is not a "
        "construction implements a claim and asserts that the task has that "
        "claim.")
@quotes("principles.md", "The concept",
        "**claim**: a statement about the task, of one of these kinds:")
def check_claim(solver: Solver, runs: Runs) -> list[Finding]:
    """A `@claim` line whose slug no header claim states; in a solver whose
    header states claims, an instance at program scope or inside `Parse` of
    a component without `@construction` that holds no `@claim` line, and a
    concept branch with no `@claim` line; and a branch's claim that holds
    `@approximated:`. Serves the concept's form."""
    v = view(solver, runs)
    ann = solver.annotations
    out: list[Finding] = []
    branch_claims = [c for c in ann.claims if c.constructor is not None]
    for c in branch_claims:
        if c.approximated:
            out.append(lint(c.line, LintNamed(
                Category.CLAIM, LintSentence.BRANCH_APPROXIMATED,
                (c.kind, c.slug))))
    header = [c for c in ann.claims if c.constructor is None]
    stated = {c.slug for c in header}
    if not header and ann.representative is not None:
        other = representative(solver, runs.engine)
        if other is None:
            return out
        header = [c for c in other.annotations.claims
                  if c.constructor is None]
        stated = {c.slug for c in header}
    stated |= {c.slug for c in branch_claims}
    for ref in ann.claim_lines:
        for slug in ref.slugs:
            if slug not in stated:
                out.append(lint(ref.line, LintNamed(
                    Category.CLAIM, LintSentence.CLAIM_UNSTATED, (slug,))))
    if not [c for c in ann.claims if c.constructor is None]:
        return out
    claimed = {ref.above for ref in ann.claim_lines}
    claim_lines = {ref.line for ref in ann.claim_lines}
    built = _constructions(v) | frozenset(STOCK_COMPS)
    for i in v.own_instances:
        if i.scope not in (TOP,) and i.scope.components != (PARSE,):
            continue
        if i.component in built or i.id in claimed:
            continue
        out.append(lint(spanned(i.span).first, LintNamed(
            Category.CLAIM, LintSentence.INSTANCE_UNCLAIMED, (i.name,))))
    for _is_choice, p, _td in choice_adts(solver, v):
        first = concept_branch(p)
        if not first.own_line:
            continue
        if not set(comment_block_above(v, first.line)) & claim_lines:
            out.append(lint(first.line, LintNamed(
                Category.CLAIM, LintSentence.CONCEPT_UNCLAIMED,
                (first.name,))))
    return out
