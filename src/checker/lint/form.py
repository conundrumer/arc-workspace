"""The lint checks on the solver's form: the header, the case type and its
glosses, witnesses and claims, markers and sections, the components a
solver holds, and the types it may declare."""

import re
from collections.abc import Sequence
from pathlib import Path

from checker.finding import (
    Finding,
    LabelWord,
    LintLabeled,
    LintMarked,
    LintNamed,
    LintFamily,
    LintRun,
    LintSentence,
)
from checker.judged import is_timeout
from checker.lint.view import (
    STOCK_COMPS,
    TOP,
    View,
    atoms_read,
    literal_terms,
    subterms,
    type_refs,
    unqualified,
    spanned,
    view,
    lint,
)
from checker.runs import Runs
from engine import ParseFailure, Resolved, checkout
from engine.program import (
    AdtType,
    DeclId,
    AtomLiteral,
    BodyLiteral,
    Comparison,
    ComparisonOperator,
    ConstructorTerm,
    Disjunction,
    RecordTerm,
    RecordType,
    Term,
    Unit,
    Variable,
    Wildcard,
)
from solver.vocabulary import (
    CHOICE,
    DETERMINE,
    PARSE,
    TIEBREAK_RESOLUTION,
)
from solver.annotations import (
    CaseMarker,
    ClaimKind,
    HeaderWord,
    Plausibility,
)
from solver.category import Category
from solver.model import (
    Base,
    Case,
    Choice,
    ChoicePoint,
    Solver,
    UnderMarker,
    concept_branch,
    dependence,
    is_concept,
    load,
    other_branches,
    section_at,
)
from solver.names import Denoted, cases_of, cover, ctor_text, denote
from solver.problems import ProblemKind, Fault


def keywords_doc() -> Path:
    """The handbook's list of keywords a solver header may name."""
    return checkout.docs() / "handbook" / "keywords.md"


def proposals() -> Path:
    """Where each proposal comp's entry stands."""
    return checkout.docs() / "wf-solver" / "proposals"


KEYWORD_BULLET = re.compile(r"^- `([^`]+)`")

REVIEW_RANK = 7
HEADER_RANK: dict[HeaderWord | str, int] = {
    HeaderWord.DRAFT: 0, HeaderWord.REPRESENTATIVE: 1, HeaderWord.KEYWORDS: 1,
    "scene": 2, "rule": 3, HeaderWord.CONCEPT: 4, HeaderWord.INPUT: 5,
    HeaderWord.OUTPUT: 6,
}
"""The rank of each header line's word: the lines stand in rank order,
and the words of one rank in either order (solver-file.md:11-19, :82)."""

SIBLING_DROPS = frozenset({HeaderWord.KEYWORDS, HeaderWord.CONCEPT,
                           HeaderWord.INPUT, HeaderWord.OUTPUT})
"""The fields a family sibling leaves out, since it carries
`@representative:` in their place (solver-file.md:86-90)."""


def _known_keywords() -> frozenset[str]:
    """Every keyword keywords.md lists: the leading code span of a
    bullet."""
    return frozenset(m.group(1) for line in keywords_doc().read_text()
                     .splitlines() if (m := KEYWORD_BULLET.match(line)))


def _task_id_line(v: View) -> bool:
    return any(c.line == 1 and c.own_line and c.file is None
               for c in v.program.comments)


def check_header(solver: Solver, runs: Runs) -> list[Finding]:
    """The header lines that break its grammar, and the fields it lacks
    (solver-file.md:11-19, :82 "`@scene` and `@rule` are in dependency
    order", :84 "A `// review <kind>: <text>` line stands last in the
    header", :86-90). Serves readability: the header is what a reader of
    the corpus reads first."""
    v = view(solver, runs)
    ann = solver.annotations
    out: list[Finding] = []

    def flag(line: int, sentence: LintSentence, *names: str) -> None:
        out.append(lint(line, LintNamed(Category.HEADER, sentence, names)))

    if not _task_id_line(v):
        return [lint(1, LintNamed(Category.HEADER, LintSentence.NO_TASK_ID,
                                  ()))]
    placed = sorted(
        [(f.line, HEADER_RANK[f.word]) for f in ann.header]
        + [(c.line, HEADER_RANK[c.kind.value]) for c in ann.claims
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
            flag(f.line, LintSentence.FIELD_TWICE, f.word.value)
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


def check_keyword(solver: Solver, runs: Runs) -> list[Finding]:
    """A word of the `@keywords:` line that keywords.md does not list, a
    hint: a session adds the keyword it needs and proposes it in its
    review (solver-file.md:83 "`@keywords` carries the keywords any case
    claims"). Serves readability: keywords index the corpus."""
    fields = sorted((f for f in solver.annotations.header
                     if f.word == HeaderWord.KEYWORDS), key=lambda f: f.line)
    if not fields:
        return []
    known = _known_keywords()
    return [lint(fields[0].line, LintNamed(
                Category.KEYWORD, LintSentence.UNKNOWN_KEYWORD, (w,)))
            for w in fields[0].value.split() if w not in known]


def _representative(solver: Solver, runs: Runs) -> Solver | None:
    """The family's representative solver the header names; None where
    the header names none or the reader reports it missing."""
    rep = solver.annotations.representative
    if rep is None or any(p.kind == ProblemKind.REPRESENTATIVE_MISSING
                          for p in solver.problems):
        return None
    return load(rep.task_id, runs.engine)


def check_family_case(solver: Solver, runs: Runs) -> list[Finding]:
    """A `@representative:` case name the representative's `Choice` does
    not hold (solver-file.md:90): the name denotes one case of the
    representative's `Choice`, so it stands among that type's
    constructors. Serves the concept's form: the sibling names its
    family's case."""
    rep = solver.annotations.representative
    if rep is None or rep.case is None:
        return []
    case = rep.case
    other = _representative(solver, runs)
    if other is None:
        return []

    def flag(sentence: LintSentence,
             failure: ParseFailure | None = None) -> list[Finding]:
        return [lint(rep.line, LintFamily(Category.FAMILY_CASE, sentence,
                                          rep.task_id, case, failure))]

    failed = next((p for p in other.problems
                   if p.kind == ProblemKind.PARSE_FAILURE), None)
    if failed is not None and isinstance(failed.detail, ParseFailure):
        return flag(LintSentence.FAMILY_NOT_PARSED, failed.detail)
    if other.choice is None:
        return flag(LintSentence.FAMILY_NO_CHOICE)
    if other.choice.record is not None:
        return flag(LintSentence.FAMILY_RECORD)
    top = [c.name for p in other.choice.points if not p.path
           for c in p.constructors]
    return [] if rep.case in top else flag(LintSentence.FAMILY_NO_CASE)


def check_case_marker(solver: Solver, runs: Runs) -> list[Finding]:
    """A case marker whose case names are joined by `/`
    (solver-file.md:105 "`// --- Box, Erode ---`", :107 "The comma still
    separates cases"). Serves readability."""
    return [lint(m.line, LintNamed(Category.CASE_MARKER,
                                   LintSentence.MARKER_SLASH, ()))
            for m in solver.annotations.markers
            if any("/" in p.name for p in m.parts)]


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
    lines = {c.line for c in v.program.comments
             if c.own_line and c.file is None}
    marks = {m.line for m in v.markers}
    out: list[int] = []
    n = line - 1
    while n in lines and n not in marks:
        out.append(n)
        n -= 1
    return out


def check_gloss(solver: Solver, runs: Runs) -> list[Finding]:
    """`Choice` lacking its gloss above the type, and a constructor of a
    choice ADT that opens no line of its own (style.md:49 "The gloss of a
    choice is above its type, and nowhere else"; solver-file.md:99-102).
    Serves readability: each branch's directive lines are its
    description."""
    v = view(solver, runs)
    marks = {m.line for m in v.markers}
    comments = {c.line for c in v.program.comments
                if c.own_line and c.file is None}
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


def check_witness(solver: Solver, runs: Runs) -> list[Finding]:
    """A `@witness`, `@derive` or `@store` line at `ordinary` that carries
    `@relaxed` (principles.md:136 "`ordinary`: readily, breaking no scene
    claim of the concept case"; procedure.md:150); a concept branch that
    carries a `@witness` line, and a `@witness` line under neither a
    branch nor an `@approximated:` line (style.md:48-52). Serves the
    concept's form."""
    v = view(solver, runs)
    ann = solver.annotations
    out: list[Finding] = []
    labeled = (
        [(w.line, LintLabeled(Category.WITNESS, LintSentence.ORDINARY_RELAXED,
                              LabelWord.WITNESS, w.id, tuple(w.relaxed)),
          w.plausibility) for w in ann.witnesses]
        + [(d.line, LintLabeled(Category.WITNESS,
                                LintSentence.ORDINARY_RELAXED,
                                LabelWord.DERIVE, d.proposer,
                                tuple(d.relaxed)), d.plausibility)
           for d in ann.derives]
        + [(s.line, LintLabeled(Category.WITNESS,
                                LintSentence.ORDINARY_RELAXED,
                                LabelWord.STORE, None, tuple(s.relaxed)),
            s.plausibility) for s in ann.stores])
    for line, payload, plausibility in labeled:
        if plausibility == Plausibility.ORDINARY and payload.relaxed:
            out.append(lint(line, payload))
    for _is_choice, p, _td in _choice_adts(solver, v):
        first = concept_branch(p)
        if not first.own_line:
            continue
        if any(w.constructor == first.name for w in ann.witnesses):
            out.append(lint(first.line, LintNamed(
                Category.WITNESS, LintSentence.CONCEPT_WITNESS,
                (first.name,))))
    for w in ann.witnesses:
        if w.constructor is None and w.approximates is None:
            out.append(lint(w.line, LintNamed(
                Category.WITNESS, LintSentence.WITNESS_PLACE, ())))
    return out


def check_one_case(solver: Solver, runs: Runs) -> list[Finding]:
    """`Choice` in a solver the runner holds one case of
    (solver-file.md:103 "A solver with one case has no `Choice`, case
    markers, or case column on `out`"). Where the run that gives the solver's
    cases fails, whether it holds one case is unknown, and the finding
    says so. Serves the purest form."""
    choice = solver.choice
    if choice is None:
        return []
    v = view(solver, runs)
    line = _choice_line(v, choice)
    solver_cases = runs.cases
    if not isinstance(solver_cases, tuple):
        sentence = LintSentence.ONE_CASE_UNKNOWN_TIMEOUT \
            if is_timeout(solver_cases) else LintSentence.ONE_CASE_UNKNOWN_FAILED
        return [lint(line, LintRun(Category.ONE_CASE, sentence, solver_cases))]
    if len(solver_cases) != 1:
        return []
    return [lint(line, LintRun(Category.ONE_CASE, LintSentence.ONE_CASE,
                               solver_cases[0]))]


def _choice_line(v: View, choice: Choice) -> int:
    """The line `Choice`'s declaration starts on."""
    decl = v.decls.get(choice.declaration)
    return spanned(decl.span).first if decl is not None else 1


def _constructions(v: View) -> frozenset[str]:
    """The lib components whose `.comp` line ends with `// @construction`
    (solver-file.md:140): an instance of one builds a term the model
    reads through, and serves no claim of its own."""
    trailing = {(c.file, c.line) for c in v.program.comments
                if not c.own_line and c.text.strip()
                .startswith("@construction")}
    return frozenset(c.name for c in v.program.components
                     if c.span is not None and c.span.file is not None
                     and (c.span.file, c.span.first) in trailing)


def check_claim(solver: Solver, runs: Runs) -> list[Finding]:
    """A `@claim` line whose slug no header claim states; in a solver
    whose header states claims, an instance at program scope or inside
    `Parse` of a component without `@construction` that carries no
    `@claim` line, and a concept branch with no `@claim` line; and a
    branch's claim that carries `@approximated:` (solver-file.md:140-142;
    encoding.md:42 "an instance of a component that is not a construction
    implements a claim"). Serves the concept's form."""
    v = view(solver, runs)
    ann = solver.annotations
    out: list[Finding] = []
    branch_claims = [c for c in ann.claims if c.constructor is not None]
    for c in branch_claims:
        if c.approximated:
            out.append(lint(c.line, LintNamed(
                Category.CLAIM, LintSentence.BRANCH_APPROXIMATED,
                (c.kind.value, c.slug))))
    header = [c for c in ann.claims if c.constructor is None]
    stated = {c.slug for c in header}
    if not header and ann.representative is not None:
        other = _representative(solver, runs)
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


def check_comp_without_entry(solver: Solver, runs: Runs) -> list[Finding]:
    """A proposal comp with no entry under docs/wf-solver/proposals/, a
    hint (style.md:112-113 "A proposal comp with no entry is a hint";
    solver-file.md:153 "A comp outside `Params`, `Determine`, and `Parse`
    is lib code, and a solver writes one only as a proposal comp").
    Serves the purest form: the comp is lib code on its way out of the
    solver. A proposal comp whose relations no derivation of the concept
    case reads (`solver.model.dependence`) is a `proposal comp` lint in
    place of that hint (lib-protocol.md "In the pass": a proposal comp
    holds relations "the concept case reads"), naming through `cover`
    the cases whose derivations read them."""
    v = view(solver, runs)
    comps = [c for c in v.own_components
             if c.scope == TOP and c.name not in STOCK_COMPS]
    readers = _comp_readers(solver, runs, [c.name for c in comps])
    out: list[Finding] = []
    for c in comps:
        line = spanned(c.span).first
        got = readers.get(c.name)
        if got is not None:
            out.append(lint(line, LintNamed(
                Category.PROPOSAL_COMP, LintSentence.PROPOSAL_UNREAD,
                (c.name, *got))))
        elif not (proposals() / f"{c.name}.md").is_file():
            out.append(lint(line, LintNamed(
                Category.COMP_WITHOUT_ENTRY, LintSentence.NO_PROPOSAL_ENTRY,
                (c.name,))))
    return out


def _comp_readers(solver: Solver, runs: Runs, comps: Sequence[str]
                  ) -> dict[str, tuple[str, ...]]:
    """Each of `comps` whose units no derivation of the concept case
    depends on (`solver.model.dependence`), with the fewest names that
    cover the cases whose derivations depend on one of them; none where
    the run that enumerates the solver's cases gives no result."""
    every = runs.cases
    if not comps or not isinstance(every, tuple):
        return {}
    bases = list(dict.fromkeys(c.base for c in every))
    rd = dependence(solver, bases)
    out: dict[str, tuple[str, ...]] = {}
    for name in comps:
        reading: set[Base | None] = set()
        for u in solver.program.units:
            if u.scope.components[:1] == (name,):
                reading |= set(rd.units.get(u.id, ()))
        if any(is_concept(solver, b) for b in reading):
            continue
        out[name] = cover(solver, [c for c in every if c.base in reading],
                          every)
    return out


def check_parse_unshared_with_determine(solver: Solver, runs: Runs
                                        ) -> list[Finding]:
    """A `Parse` comp that no `Determine` comp reads (solver-file.md:155
    "A `.comp Parse<Key>` contains a derivation that the program and the
    Determine comp share"). Serves the purest form."""
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
    if any(i.component == PARSE and i.scope.components == (DETERMINE,)
           for i in v.program.instances):
        return True
    for u in v.own_units:
        if u.scope.components[:1] != (DETERMINE,):
            continue
        for a in atoms_read(u):
            r = v.index.resolve(a.atom.relation, u.scope)
            if isinstance(r, Resolved):
                d = v.decls.get(r.declaration)
                if d is not None and getattr(d, "scope", TOP) \
                        .components[:1] == (PARSE,):
                    return True
    return False


def check_banned_type(solver: Solver, runs: Runs) -> list[Finding]:
    """A type the solver declares that is none of the types solver-file.md
    lists (solver-file.md:125-131; style.md:64 "any other type is
    banned"): the types `Choice` and `TiebreakResolution` reach, and the
    records an instance takes as a type argument with the records their
    fields reach. Only the types at the top level and in `Determine` and
    `Parse` are flagged. Serves the purest form."""
    v = view(solver, runs)
    scoped = [(t, t.scope == TOP or t.scope.components[:1] in
               ((DETERMINE,), (PARSE,))) for t in v.own_types]
    by_name: dict[str, list] = {}
    for t, _ in scoped:
        by_name.setdefault(t.name, []).append(t)
    declared = set(by_name)

    def refs(name: str) -> set[str]:
        return {unqualified(r) for t in by_name[name]
                for r in type_refs(t)} - {name}

    sanctioned: set[str] = set()
    stack = [n for n in (CHOICE, TIEBREAK_RESOLUTION) if n in declared]
    while stack:
        name = stack.pop()
        if name in sanctioned:
            continue
        sanctioned.add(name)
        stack.extend((refs(name) & declared) - sanctioned)
    records = {n for n, ts in by_name.items()
               if any(isinstance(t, RecordType) for t in ts)}
    filled = {a for i in v.own_instances for a in i.type_args}
    stack = list(records & filled)
    while stack:
        name = stack.pop()
        if name in sanctioned:
            continue
        sanctioned.add(name)
        stack.extend((refs(name) & records) - sanctioned)
    return [lint(t.span.first, LintNamed(
                Category.BANNED_TYPE, LintSentence.BANNED_TYPE, (t.name,)))
            for t, linted in scoped if linted and t.name not in sanctioned]


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


def check_unread_field(solver: Solver, runs: Runs) -> list[Finding]:
    """A case, a constructor at its parent, whose clauses never read a
    field that encodes a choice point, a hint (procedure.md:175 "A case
    never reads a `Choice` field: the choice point that field encodes
    stands under the other branches"; principles.md:106-108). A clause
    reads a field where it writes the constructor and puts at the field
    anything but `_` or a variable it uses nowhere else. Serves the
    concept's form."""
    choice = solver.choice
    if choice is None:
        return []
    v = view(solver, runs)
    adts = {td.name: td for _, _p, td in _choice_adts(solver, v)}
    points: dict[str, list[tuple[int, str]]] = {}
    owner: dict[str, AdtType] = {}
    for td in adts.values():
        for c in td.constructors:
            owner[c.name] = td
            chosen = [(j, f.name) for j, f in enumerate(c.fields)
                      if f.type in adts]
            if chosen:
                points[c.name] = chosen
    roots: list[tuple[str, AdtType | None]] = [
        (f.name, adts.get(f.type)) for f in choice.record or ()]
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
        td = owner.get(ctor)
        at = 1
        if td is not None:
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


def check_case_section(solver: Solver, runs: Runs) -> list[Finding]:
    """A top-level clause that contains exactly one constructor of a
    choice ADT other than its type's first, and stands outside that
    constructor's marker: before the first marker, or under a marker none
    of whose names lists cases (`cases_of`) that all take it, a hint
    (solver-file.md:104
    "Cases do not interleave: each case's Params and clauses are under
    its marker"). A marker whose names are prose marks nothing and is
    neutral; a constructor under a negation or a `!=` does not count; a
    clause of an enumerator, and a fact of one constructor or record,
    belong to no case. The clauses on one line that give one hint give
    it once. Where the run that enumerates the solver's cases gives no
    result, a clause under a marker is not judged, and a hint at `Choice`
    says so with the run's failure. Serves readability."""
    v = view(solver, runs)
    cases = {c.name for _, p, _td in _choice_adts(solver, v)
             for c in other_branches(p)}
    if not cases:
        return []
    enums = v.enumerators
    every = runs.cases
    out: list[Finding] = []
    unjudged = False
    for u in v.own_units:
        if u.scope != TOP or (not u.head.relation.instances
                              and u.head.relation.name in enums):
            continue
        if u.body is None and len(u.head.args) == 1 \
                and isinstance(u.head.args[0], ConstructorTerm | RecordTerm):
            continue
        named = {t.name for lit in _all_literals(u)
                 for top in _admitting_terms(lit, u)
                 for t in subterms(top)
                 if isinstance(t, ConstructorTerm) and t.name in cases}
        if len(named) != 1 or u.span is None:
            continue
        (case,) = named
        marker = v.section(u)
        if marker is not None:
            if not isinstance(every, tuple):
                unjudged = True
                continue
            marked = _marks(solver, marker, every)
            d = denote(solver, ctor_text(case))
            taking = frozenset(cases_of(solver, d, every)) \
                if isinstance(d, Denoted) else frozenset()
            if marked is None or any(m and m <= taking for m in marked):
                continue
        if marker is None:
            payload = LintNamed(Category.CASE_SECTION,
                                LintSentence.CASE_SECTION_BEFORE, (case,))
        else:
            payload = LintMarked(Category.CASE_SECTION,
                                 LintSentence.CASE_SECTION_UNDER, case,
                                 marker)
        out.append(lint(u.span.first, payload))
    if unjudged and solver.choice is not None \
            and not isinstance(every, tuple):
        out.append(lint(_choice_line(v, solver.choice), LintRun(
            Category.CASE_SECTION, LintSentence.CASE_SECTION_UNJUDGED,
            every)))
    return list(dict.fromkeys(out))


def check_case_section_read(solver: Solver, runs: Runs) -> list[Finding]:
    """A clause that feeds a relation some cases read, where every clause
    that feeds the rows they read there stands under a marker that does
    not list them (`solver.model.Dependence.stranded`):
    the program runs the clause for those cases, so its marker does not
    list every case that reads it (solver-file.md:104 "Cases do not
    interleave: each case's Params and clauses are under its marker").
    One finding per solver line, relation and marker: the clauses on one
    line that feed one relation under one marker give one finding, on
    that line, naming through `cover` the cases that read any of them.
    Where the run that enumerates the solver's cases gives no result,
    nothing is judged, and a hint at `Choice` says so with the run's
    failure. Serves the purest form."""
    every = runs.cases
    if solver.choice is None:
        return []
    if not isinstance(every, tuple):
        return [lint(_choice_line(view(solver, runs), solver.choice), LintRun(
            Category.CASE_SECTION, LintSentence.CASE_SECTION_READ_UNJUDGED,
            every))]
    bases = list(dict.fromkeys(c.base for c in every))
    among = [b for b in bases if b is not None]
    if not among:
        return []
    rd = dependence(solver, bases)
    by_id = {u.id: u for u in solver.program.units}
    lines: dict[tuple[int, str, CaseMarker], set[Base | None]] = {}
    for (uid, relation), reaching in sorted(
            rd.stranded.items(), key=lambda kv: (kv[0][0].index, kv[0][1])):
        u = by_id[uid]
        if u.span is None:
            continue
        section = section_at(solver, u.scope, u.span.first)
        if not isinstance(section, UnderMarker):
            continue
        lines.setdefault((u.span.first, relation, section.marker),
                         set()).update(reaching)
    return [lint(line, LintMarked(
        Category.CASE_SECTION, LintSentence.CASE_SECTION_READ, relation,
        marker, cases=tuple(cover(solver, [b for b in among if b in reaching],
                                  among))))
        for (line, relation, marker), reaching in lines.items()]
