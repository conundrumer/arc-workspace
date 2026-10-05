"""The lint checks on the solver's form: the header, the case type and its
glosses, witnesses and claims, markers and sections, the components a
solver holds, and the types it may declare."""

import re
from collections.abc import Collection, Iterator, Mapping, Sequence
from pathlib import Path

from checker.finding import (
    Finding,
    LintCaseValue,
    LintFamily,
    LintLabeled,
    LintMarked,
    LintNamed,
    LintRun,
    LintSentence,
)
from checker.judged import (
    base_names,
    concept_among,
    is_timeout,
    parse_failure,
    reading_names,
    representative,
)
from checker.lint.view import (
    STOCK_COMPS,
    TOP,
    View,
    atoms_read,
    from_lib,
    lint,
    literal_terms,
    spanned,
    subterms,
    tag_fact,
    type_refs,
    view,
)
from checker.runs import Runs
from engine import (
    ParseFailure,
    Resolved,
    RunFailure,
    checkout,
)
from engine.program import (
    AdtType,
    AtomLiteral,
    BodyLiteral,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    DeclId,
    Disjunction,
    FunctorDecl,
    RecordTerm,
    RecordType,
    RelationDecl,
    Scope,
    Term,
    TypeDecl,
    Unit,
    Variable,
    Wildcard,
    own,
)
from engine.program import subterms as direct_subterms
from engine.quotes import quotes
from solver.annotations import (
    DirectiveWord,
    HEADER_RANK,
    REVIEW_RANK,
    SIBLING_DROPS,
    CaseMarker,
    ClaimKind,
    HeaderWord,
    Plausibility,
)
from solver.category import Category
from solver.model import (
    bases_of,
    choice_bases,
    choice_line,
    Base,
    Case,
    Choice,
    ChoicePoint,
    Node,
    Solver,
    branch_witnesses,
    concept_branch,
    dependence,
    marker_at,
    row_value,
    other_branches,
    dependent_bases,
)
from solver.names import (
    Denoted,
    cases_of,
    constructors_fixed,
    denote,
)
from solver.solve import PerCase, per_case
from solver.vocabulary import (
    CHOICE,
    DEMONSTRATED,
    DEMONSTRATED_CHOICE,
    DEMONSTRATION_CONSISTENCY,
    DETERMINE,
    DETERMINE_SCOPE,
    PARSE,
    TIEBREAK_RESOLUTION,
)


def keywords_doc() -> Path:
    """The handbook's list of keywords a solver header may name."""
    return checkout.handbook() / "keywords.md"


KEYWORD_BULLET = re.compile(r"^- `([^`]+)`")




def doc_keywords(written: str) -> dict[str, list[str]]:
    """The keywords of keywords.md, in doc order, per `##` section: the
    leading code span of each bullet."""
    out: dict[str, list[str]] = {}
    section: list[str] = []
    for line in written.splitlines():
        if line.startswith("## "):
            section = out.setdefault(line[3:].strip(), [])
        elif m := KEYWORD_BULLET.match(line):
            section.append(m.group(1))
    return out


def known_keywords() -> frozenset[str]:
    """Every keyword keywords.md lists (`doc_keywords`)."""
    return frozenset(w for words in doc_keywords(
        keywords_doc().read_text()).values() for w in words)


def header_keywords(solver: Solver) -> tuple[int, tuple[str, ...]] | None:
    """The line of the solver's `@keywords:` field and its words, every
    line of the field read; None where the header has none."""
    fields = sorted((f for f in solver.annotations.header
                     if f.word == HeaderWord.KEYWORDS), key=lambda f: f.line)
    return None if not fields else (fields[0].line, fields[0].words)


@quotes("solver-file.md", "Header",
        "`@scene` and `@rule` are in dependency order.")
@quotes("solver-file.md", "Header",
        "A `// review <kind>: <text>` line stands last in the header.")
@quotes("principles.md", "The concept",
        "**concept statement**: the claims that express the concept.")
@quotes("style.md", "Header",
        "`@scene` is only included when `@claim` or `@relaxed` denotes it")
def check_header(solver: Solver, runs: Runs) -> list[Finding]:
    """The header lines that break its grammar, and the fields it lacks.
    Serves readability: the header is what a reader of the corpus reads
    first."""
    ann = solver.annotations
    out: list[Finding] = []

    def flag(line: int, sentence: LintSentence, *names: str) -> None:
        out.append(lint(line, LintNamed(Category.HEADER, sentence, names)))

    if ann.task_id is None:
        return [lint(1, LintNamed(Category.HEADER, LintSentence.NO_TASK_ID,
                                  ()))]
    placed = sorted(
        [(f.line, HEADER_RANK[f.word]) for f in ann.header]
        + [(c.line, HEADER_RANK[c.kind]) for c in ann.claims
           if c.constructor is None]
        + [(r.line, REVIEW_RANK) for r in ann.reviews])
    last = -1
    for line, rank in placed:
        if rank < last:
            flag(line, LintSentence.HEADER_ORDER)
        last = max(last, rank)
    seen: set[HeaderWord] = set()
    for f in sorted(ann.header, key=lambda f: f.line):
        if f.word == HeaderWord.DRAFT:
            if f.line > 2:
                flag(f.line, LintSentence.DRAFT_PLACE)
            continue
        if f.word in seen:
            flag(f.line, LintSentence.FIELD_TWICE, f.word)
        elif (f.word in SIBLING_DROPS and HeaderWord.REPRESENTATIVE in seen
              or f.word == HeaderWord.REPRESENTATIVE
              and not seen.isdisjoint(SIBLING_DROPS)):
            flag(f.line, LintSentence.SIBLING_DROPS)
        seen.add(f.word)
    for r in ann.reviews:
        if not r.kind:
            flag(r.line, LintSentence.REVIEW_KIND)
    slugs: set[str] = set()
    for c in ann.claims:
        if c.constructor is not None:
            continue
        if c.slug in slugs:
            flag(c.line, LintSentence.SLUG_TWICE, c.slug)
        slugs.add(c.slug)
    for c in ann.header_prose[:1]:
        flag(c.line, LintSentence.HEADER_PROSE)
    if not seen & {HeaderWord.KEYWORDS, HeaderWord.REPRESENTATIVE}:
        flag(1, LintSentence.NO_KEYWORDS)
    elif (HeaderWord.KEYWORDS in seen and HeaderWord.OUTPUT not in seen
          and not any(c.kind == ClaimKind.RULE for c in ann.claims
                      if c.constructor is None)):
        flag(1, LintSentence.NO_RULE)
    return out


@quotes("solver-file.md", "Header",
        "`@keywords` carries the keywords any case claims.")
def check_keyword(solver: Solver, runs: Runs) -> list[Finding]:
    """A word of the `@keywords:` line that keywords.md does not list, a
    hint: a session adds the keyword it needs and proposes it in its review.
    Serves readability: keywords index the corpus."""
    got = header_keywords(solver)
    if got is None:
        return []
    line, words = got
    known = known_keywords()
    return [lint(line, LintNamed(
                Category.KEYWORD, LintSentence.UNKNOWN_KEYWORD, (w,)))
            for w in words if w not in known]


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


def _choice_adts(solver: Solver, v: View
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


def _comment_block_above(v: View, line: int) -> list[int]:
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
    for is_choice, _p, td in _choice_adts(solver, v):
        above = td.span.first - 1
        if is_choice and (above not in comments or above in marks):
            out.append(lint(td.span.first, LintNamed(
                Category.GLOSS, LintSentence.GLOSS_ABOVE, (td.name,))))
        for c in td.constructors:
            if not c.own_line:
                out.append(lint(td.span.first, LintNamed(
                    Category.GLOSS, LintSentence.OWN_LINE, (c.name,))))
    return out


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
    """A `@witness`, `@derive` or `@store` line at `ordinary` that carries
    `@relaxed`; a concept branch that carries a `@witness` line, and a
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
    for _is_choice, p, _td in _choice_adts(solver, v):
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
        return [_at_choice(v, choice, Category.ONE_CASE, sentence,
                           solver_cases)]
    if len(solver_cases) != 1:
        return []
    return [lint(line, LintRun(Category.ONE_CASE, LintSentence.ONE_CASE,
                               solver_cases[0]))]


def _at_choice(v: View, choice: Choice, category: Category,
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
    a component without `@construction` that carries no `@claim` line, and a
    concept branch with no `@claim` line; and a branch's claim that carries
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
    for _is_choice, p, _td in _choice_adts(solver, v):
        first = concept_branch(p)
        if not first.own_line:
            continue
        if not set(_comment_block_above(v, first.line)) & claim_lines:
            out.append(lint(first.line, LintNamed(
                Category.CLAIM, LintSentence.CONCEPT_UNCLAIMED,
                (first.name,))))
    return out


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
    case reads (`solver.model.dependence`) is a `proposal comp` lint in
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
    depends on (`solver.model.dependence`), with the fewest names that
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


@quotes("style.md", "Types",
        "lists the types a solver may define, and any other type is banned.")
@quotes("solver-file.md", "Types",
        "a record used as a type argument of a generic comp")
@quotes("solver-file.md", "Types",
        "`DemonstratedChoice`, per [Demonstrated choice]")
@quotes("solver-file.md", "Demonstrated choice",
        "`DemonstratedChoice` is the `Demonstrated` type argument of a "
        "`DemonstrationConsistency` instance.")
def check_banned_type(solver: Solver, runs: Runs) -> list[Finding]:
    """A type the solver declares that is none of the types a solver may
    define: the types `Choice` and `TiebreakResolution` reach, the types
    `DemonstratedChoice` reaches where an instance of the lib's
    `DemonstrationConsistency` takes it as its `Demonstrated` type
    argument, and the records an instance takes as a type argument with
    the records their fields reach. Only the types at the top level and
    in `Determine` and `Parse` are flagged. Serves the purest form."""
    v = view(solver, runs)
    scoped = [(t, t.scope == TOP or t.scope.components[:1] in
               ((DETERMINE,), (PARSE,))) for t in v.own_types]
    own_types = {t.id: t for t, _ in scoped}

    def resolved(name: str, scope: Scope) -> TypeDecl | None:
        return _type_among(runs, name, scope, own_types)

    def refs(t: TypeDecl) -> list[TypeDecl]:
        return [d for r in type_refs(t)
                if (d := resolved(r, t.scope)) is not None and d.id != t.id]

    def sanction(stack: list[TypeDecl], admits: type) -> None:
        while stack:
            t = stack.pop()
            if t.id in sanctioned:
                continue
            sanctioned.add(t.id)
            stack.extend(r for r in refs(t)
                         if isinstance(r, admits) and r.id not in sanctioned)

    sanctioned: set[DeclId] = set()
    sanction([d for n in (CHOICE, TIEBREAK_RESOLUTION)
              if (d := resolved(n, TOP)) is not None], object)
    demonstrated = resolved(DEMONSTRATED_CHOICE, TOP)
    if demonstrated is not None and demonstrated.id in {
            d.id for i in v.own_instances
            if (of := v.index.component(i.component, i.scope)) is not None
            and of.name == DEMONSTRATION_CONSISTENCY and from_lib(of.span)
            for p, a in zip(of.type_params, i.type_args) if p == DEMONSTRATED
            if (d := resolved(a, i.scope)) is not None}:
        sanction([demonstrated], object)
    sanction([d for i in v.own_instances for a in i.type_args
              if isinstance(d := resolved(a, i.scope), RecordType)],
             RecordType)
    return [lint(t.span.first, LintNamed(
                Category.BANNED_TYPE, LintSentence.BANNED_TYPE, (t.name,)))
            for t, linted in scoped if linted and t.id not in sanctioned]


def _type_among[T](runs: Runs, name: str, scope: Scope,
                   among: Mapping[DeclId, T]) -> T | None:
    """The declaration among `among` that the type `name` denotes in
    `scope` (`engine.Index.type_decl`); None where it denotes a
    primitive type, a type parameter or a declaration not among them."""
    d = runs.index.type_decl(name, scope)
    return None if d is None else among.get(d.id)


# Unread fields


def _all_literals(unit: Unit) -> list[BodyLiteral | None]:
    """The head (as None) and every body literal, disjunction branches
    included."""
    out: list[BodyLiteral | None] = [None]
    stack = list(unit.body or ())
    while stack:
        lit = stack.pop(0)
        out.append(lit)
        if isinstance(lit, Disjunction):
            for b in lit.branches:
                stack.extend(b)
    return out


def _terms_of(unit: Unit, lit: BodyLiteral | None) -> tuple[Term, ...]:
    return unit.head.args if lit is None else literal_terms(lit)


def _var_uses(unit: Unit, enums: set[str]) -> dict[str, int]:
    """How often each variable stands in a clause; a variable that is the
    one argument of an enumerator atom does not count there."""
    uses: dict[str, int] = {}
    for lit in _all_literals(unit):
        if isinstance(lit, AtomLiteral) and len(lit.atom.args) == 1 \
                and lit.atom.relation.name in enums \
                and not lit.atom.relation.instances:
            continue
        for t in _terms_of(unit, lit):
            for s in subterms(t):
                if isinstance(s, Variable):
                    uses[s.name] = uses.get(s.name, 0) + 1
    return uses


def _reads(term: Term, uses: dict[str, int]) -> bool:
    """A field written as `term` is read: it is no `_`, and no variable
    the clause uses nowhere else."""
    if isinstance(term, Wildcard):
        return False
    return not (isinstance(term, Variable) and uses.get(term.name, 0) <= 1)


@quotes("procedure.md", "Witness",
        "A case never reads a `Choice` field: the choice point that field "
        "encodes stands under the other branches")
@quotes("principles.md", "Choice points and open parameters",
        "A choice point stands at the concept, or under a branch when its "
        "property exists only with that branch.")
@quotes("style.md", "Cases",
        "**Concept branch.** The concept branch is declared first in "
        "`Choice`, and in each field's type of a record-typed `Choice`.")
def check_unread_field(solver: Solver, runs: Runs) -> list[Finding]:
    """A case, a constructor at its parent, whose clauses never read a field
    that encodes a choice point, a hint. A clause reads a field where it
    writes the constructor and puts at the field anything but `_` or a
    variable it uses nowhere else.
    Serves the concept's form."""
    choice = solver.choice
    if choice is None:
        return []
    v = view(solver, runs)
    adts = {td.id: td for _, _p, td in _choice_adts(solver, v)}

    def adt_of(name: str, scope: Scope) -> AdtType | None:
        return _type_among(runs, name, scope, adts)

    points: dict[str, list[tuple[int, str]]] = {}
    owner: dict[str, AdtType] = {}
    for td in adts.values():
        for c in td.constructors:
            owner[c.name] = td
            chosen = [(j, f.name) for j, f in enumerate(c.fields)
                      if adt_of(f.type, td.scope) is not None]
            if chosen:
                points[c.name] = chosen
    choice_decl = solver.program.declared(choice.declaration)
    if not isinstance(choice_decl, AdtType | RecordType):
        raise ValueError("`Choice` names no type declaration")
    roots: list[tuple[str, AdtType | None]] = [
        (f.name, adt_of(f.type, choice_decl.scope))
        for f in choice.record or ()]
    if not points and len(roots) < 2:
        return []
    enums = v.enumerators
    written: set[tuple[str, int]] = set()
    read: set[tuple[str, int]] = set()
    rec_written: set[tuple[str, int]] = set()
    rec_read: set[tuple[str, int, int]] = set()
    open_read: set[tuple[int, int]] = set()

    def root_ctor(t: Term, i: int) -> str | None:
        td = roots[i][1]
        if isinstance(t, ConstructorTerm) and td is not None \
                and t.name in {c.name for c in td.constructors}:
            return t.name
        return None

    def choice_record(t: RecordTerm) -> bool:
        return len(t.args) == len(roots) and all(
            isinstance(a, Variable | Wildcard) or root_ctor(a, i) is not None
            for i, a in enumerate(t.args))

    for u in v.own_units:
        if u.scope == TOP and not u.head.relation.instances \
                and u.head.relation.name in enums:
            continue
        uses = _var_uses(u, enums)
        for lit in _all_literals(u):
            for top in _terms_of(u, lit):
                for t in subterms(top):
                    if isinstance(t, ConstructorTerm) and t.name in points:
                        for j, _name in points[t.name]:
                            if j >= len(t.args):
                                continue
                            written.add((t.name, j))
                            if _reads(t.args[j], uses):
                                read.add((t.name, j))
                    elif isinstance(t, RecordTerm) and len(roots) > 1 \
                            and choice_record(t):
                        for i, a in enumerate(t.args):
                            ctor = root_ctor(a, i)
                            if ctor is not None:
                                rec_written.add((ctor, i))
                            for j, b in enumerate(t.args):
                                if j == i or not _reads(b, uses):
                                    continue
                                if ctor is None:
                                    open_read.add((i, j))
                                else:
                                    rec_read.add((ctor, i, j))
    out: list[Finding] = []

    def hint(ctor: str, field: str) -> None:
        td = owner[ctor]
        c = next(c for c in td.constructors if c.name == ctor)
        at = c.span.first if c.own_line else td.span.first
        out.append(lint(at, LintNamed(Category.UNREAD_FIELD,
                                      LintSentence.UNREAD_FIELD,
                                      (ctor, field))))

    for ctor, chosen in points.items():
        for j, name in chosen:
            if (ctor, j) in written and (ctor, j) not in read:
                hint(ctor, name)
    for ctor, i in sorted(rec_written, key=lambda k: (k[1], k[0])):
        for j, (name, _td) in enumerate(roots):
            if j != i and (ctor, i, j) not in rec_read \
                    and (i, j) not in open_read:
                hint(ctor, name)
    return out


# Case sections


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
    points = [p for _, p, _td in _choice_adts(solver, v)]
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
            value for lit in _all_literals(u)
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
        out.append(_at_choice(v, solver.choice, Category.CASE_SECTION,
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
    (`solver.model.Dependence.stranded`): the program runs the clause for
    those cases, so its marker does not list every case that reads it. The
    marker finding of `solver.model.dependence`, which the `store` report
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
        return [_at_choice(view(solver, runs), solver.choice,
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
