"""The handbook syntax a solver carries in comments, as one reader over the
engine's comment list gives it."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated

from engine import Comment, DeclId, Program, UnitId
from engine.program import AdtType, Span, own
from engine.text import split_top
from engine.quotes import quotes
from solver.category import Category
from solver.problems import (
    Detail,
    InSolver,
    Named,
    ProblemKind,
    Quoted,
    Fault,
    Undecided,
    UndecidedForm,
)


@quotes("solver-file.md", "File structure",
        "// <task_id> // @draft // @keywords: <keywords from keywords.md>")
class HeaderWord(StrEnum):
    """The word of a header field."""

    DRAFT = "draft"
    KEYWORDS = "keywords"
    REPRESENTATIVE = "representative"
    INPUT = "input"
    OUTPUT = "output"
    CONCEPT = "concept"


PREFIXED_WORDS: Annotated[frozenset[HeaderWord],
    quotes("solver-file.md", "File structure",
           "// <task_id> // @draft // @keywords: <keywords from keywords.md>")
] = frozenset({HeaderWord.DRAFT, HeaderWord.REPRESENTATIVE,
               HeaderWord.KEYWORDS})
"""The header words the template writes with `@`; `concept:`, `input:` and
`output:` stand without it."""


@quotes("solver-file.md", "File structure",
        "// <task_id> // @draft // @keywords: <keywords from keywords.md>")
@dataclass(frozen=True)
class HeaderField:
    """A header field. `prefixed` is false for the plain `input:`, `output:`
    and `concept:` forms.
    (The annotation `Field`; the syntax one is `engine.program.TypeField`.)"""

    word: HeaderWord
    value: str
    line: int
    end: int
    prefixed: bool

    @property
    def words(self) -> tuple[str, ...]:
        """The field's words, every line of it read: the keywords of a
        `@keywords:` field (solver-file.md, under "File structure")."""
        return tuple(self.value.split())


@quotes("solver-file.md", "Header",
        "A `// review <kind>: <text>` line stands last in the header.")
@dataclass(frozen=True)
class ReviewLine:
    """`// review <kind>: <text>`."""

    kind: str
    text: str
    line: int


@quotes("solver-file.md", "Header",
        "// @representative: <family's first-solved task id> <Case when the "
        "sibling has one case of its Choice>")
@dataclass(frozen=True)
class Representative:
    """`@representative: <task id> [<Case>]`."""

    task_id: str
    case: str | None
    line: int


@quotes("principles.md", "Witnesses",
        "**plausibility**: the annotator's ordinal estimate of how readily "
        "the generator could produce the witness.")
class Plausibility(StrEnum):
    """A witness's plausibility."""

    ORDINARY = "ordinary"
    VARIANT = "variant"
    BORDERLINE = "borderline"
    FOREIGN = "foreign"


@quotes("principles.md", "Witnesses",
        "`concept`: the concept case's output.")
@quotes("principles.md", "Witnesses",
        "`any`: the output of any case defined on the witness.")
@quotes("principles.md", "Witnesses",
        "`other`: an output that no case produces.")
@quotes("solver-file.md", "Params",
        "The verdict `derived` denotes that branch")
@quotes("solver-file.md", "Program",
        "The verdict `stored` denotes that branch")
class VerdictWord(StrEnum):
    """A verdict a line writes as a word."""

    CONCEPT = "concept"
    ANY = "any"
    OTHER = "other"
    DERIVED = "derived"
    STORED = "stored"


@quotes("principles.md", "Witnesses",
        "the branch's name: the output of that branch's model.")
@dataclass(frozen=True)
class NamedVerdict:
    """A verdict that names a branch, or branches joined by `&`: the name as
    its line writes it, whose parts `names.denote` reads."""

    text: str


type Verdict = VerdictWord | NamedVerdict


@quotes("solver-file.md", "File structure",
        "// @witness <id>: <plausibility> <verdict> // @relaxed <slug of the "
        "scene claim this witness breaks> // @reassigned <parameter changed "
        "for this witness>")
@quotes("procedure.md", "Witness",
        "`@relaxed` for the scene claim it breaks, which rules out "
        "`ordinary`, and `@reassigned` for each parameter that the assignment "
        "it stands at changes.")
@dataclass(frozen=True)
class WitnessLine:
    """`@witness <id>: <plausibility> <verdict>` with its nested `@relaxed`
    and `@reassigned` lines. (The comment line; a witness file entry is
    `solver.witness.Entry`.)"""

    id: str
    plausibility: Plausibility
    verdict: Verdict
    line: int
    relaxed: tuple[str, ...]
    reassigned: tuple[str, ...]
    approximates: str | None
    """The slug of the `@approximated:` line it stands under; None where it
    stands under none."""
    constructor: str | None
    """The constructor whose branch comment holds it; None in the header."""


@quotes("solver-file.md", "Header",
        "`@scene` and `@rule` are in dependency order.")
class ClaimKind(StrEnum):
    """`@scene` and `@rule`."""

    SCENE = "scene"
    RULE = "rule"


@quotes("solver-file.md", "File structure",
        "// @rule <slug>: <what the output takes from the input> // "
        "@approximated: <the rule the program runs>")
@dataclass(frozen=True)
class Approximated:
    """`@approximated: <text>` under a `@rule`."""

    text: str
    line: int
    witnesses: tuple[WitnessLine, ...]


@quotes("solver-file.md", "Header",
        "`@scene` and `@rule` are in dependency order.")
@quotes("solver-file.md", "Cases",
        "which each other branch's `@scene` or `@rule` line changes")
@dataclass(frozen=True)
class Claim:
    """`@scene` or `@rule` `<slug>: <text>`."""

    kind: ClaimKind
    slug: str
    text: str
    line: int
    approximated: tuple[Approximated, ...]
    constructor: str | None
    """The constructor whose branch comment holds it; None in the header."""


@quotes("solver-file.md", "Params",
        "**`@derive` directive.** The line is a branch of a choice point on "
        "the parameter")
@dataclass(frozen=True)
class DeriveLine:
    """`@derive <Proposer>: <plausibility> <verdict>`."""

    proposer: str
    plausibility: Plausibility
    verdict: Verdict
    line: int
    above: DeclId | None
    """The declaration it stands directly above; None where it stands
    above none."""
    relaxed: tuple[str, ...]


@quotes("solver-file.md", "Program",
        "**`@store` directive.** The relation, or the instance's relation the "
        "line names, has one value on every input, and the line is a branch "
        "of a choice point on it")
@dataclass(frozen=True)
class StoreLine:
    """`@store: …` above a `.decl`, or `@store <rel>: …` above an `.init`."""

    relation: str | None
    """The relation the line names; None for the bare form."""
    plausibility: Plausibility
    verdict: Verdict
    line: int
    above: DeclId | None
    relaxed: tuple[str, ...]


@quotes("solver-file.md", "Program",
        "**`@claim` directive.** At program scope or inside `Parse`, an "
        "instance of a component without an `@construction` mark has the "
        "directive, one line per instance, listing the claims the instance "
        "serves.")
@dataclass(frozen=True)
class ClaimLine:
    """`// @claim <slug>…` above an instance. (The annotation `Ref`; the
    syntax one is `engine.Occurrence`.)"""

    slugs: tuple[str, ...]
    line: int
    above: DeclId | None


@quotes("solver-file.md", "Program",
        "A relation kept despite a hint has `// @ignore: <category> — "
        "<reason>` on the line immediately above its declaration")
@quotes("solver-file.md", "Program",
        "Above a `.init`, `// @ignore <relation>: <category> — <reason>` "
        "dismisses that one relation of the instance")
@quotes("solver-file.md", "Params",
        "`// @ignore: derive <Proposer> — <reason>` above the parameter "
        "records the same for the one derivation `<Proposer>` selects.")
@quotes("solver-file.md", "Program",
        "`// @ignore: store — <reason>` and `// @ignore: store <name> — "
        "<reason>` record what the `@ignore: derive` forms record.")
class IgnoreForm(StrEnum):
    LINT = "lint"
    """`@ignore: <category>` and `@ignore <rel>: <category>`."""
    DERIVE = "derive"
    """`@ignore: derive [<Proposer> | <name>]`."""
    STORE = "store"
    """`@ignore [<rel>]: store [<name>]`."""


@quotes("solver-file.md", "Program",
        "**`@ignore` directive.** A relation kept despite a hint has `// "
        "@ignore: <category> — <reason>` on the line immediately above its "
        "declaration, with the category the hint gives.")
@quotes("solver-file.md", "Params",
        "`// @ignore: derive — <reason>` above the parameter records that "
        "every derivation of it fails a case condition")
@dataclass(frozen=True)
class IgnoreLine:
    """An `@ignore` line of any form."""

    form: IgnoreForm
    category: Category | None
    """The category of the lint form; None for the derive and store
    forms."""
    relation: str | None
    """The relation the named form above an `.init` names."""
    name: str | None
    """The `<name>` of a named derive or store form."""
    reason: str
    line: int
    above: DeclId | None
    proposer: str | None = None
    """The `<Proposer>` of `@ignore: derive <Proposer>`, which stands in
    place of a `@derive <Proposer>` line and excludes that one derivation
    of the parameter; None for every other form, the bare
    `@ignore: derive` among them, which excludes every derivation."""


@quotes("solver-file.md", "Cases",
        "Cases that share facts or clauses are under one marker listing names "
        "whose cases they are")
@dataclass(frozen=True)
class MarkerPart:
    """One name a case marker lists, as written, for `names.denote` to read."""

    name: str

    @property
    def prose(self) -> bool:
        """Whether the part is prose: more than one word stands between two
        of its `&`s, as in `Size decompose data`, whatever word it starts
        with. A prose part lists no case and denotes nothing."""
        return any(len(piece.split()) > 1 for piece in pieces(self.name))

    @property
    def slash_joined(self) -> bool:
        """Whether the part joins names by `/`, which a marker writes as
        separate parts (solver-file.md, under "Cases")."""
        return "/" in self.name


def pieces(name: str) -> list[str]:
    """The pieces of a name as written between its `&`s, each with the
    spaces around it."""
    return name.split("&")


@quotes("solver-file.md", "Cases",
        "**Case markers.** Cases do not interleave: each case's Params and "
        "clauses are under its marker.")
@dataclass(frozen=True)
class CaseMarker:
    """`// --- <names>[: gloss] ---`."""

    parts: tuple[MarkerPart, ...]
    gloss: str | None
    line: int


@quotes("solver-file.md", "File structure",
        "// @derive <Proposer>: <plausibility> <verdict>")
@quotes("solver-file.md", "Program",
        "**`@workaround` directive.** A temporary workaround is under a `// "
        "@workaround: <the principled form it stands in for>` line.")
class DirectiveWord(StrEnum):
    """The word of an `@` line of a comment block that the reader reads
    besides the header fields and the claims' kinds."""

    CLAIM = "claim"
    WITNESS = "witness"
    DERIVE = "derive"
    STORE = "store"
    APPROXIMATED = "approximated"
    RELAXED = "relaxed"
    REASSIGNED = "reassigned"
    IGNORE = "ignore"
    WORKAROUND = "workaround"


HEADER_RANK: Annotated[dict[HeaderWord | ClaimKind, int],
    quotes("solver-file.md", "Header",
           "`@scene` and `@rule` are in dependency order."),
    quotes("solver-file.md", "Header",
           "A `// review <kind>: <text>` line stands last in the header.")] = {
    HeaderWord.DRAFT: 0, HeaderWord.REPRESENTATIVE: 1, HeaderWord.KEYWORDS: 1,
    ClaimKind.SCENE: 2, ClaimKind.RULE: 3, HeaderWord.CONCEPT: 4,
    HeaderWord.INPUT: 5, HeaderWord.OUTPUT: 6,
}
"""The rank of each header line's word, in template order: the lines stand
in rank order, and the words of one rank in either order. A review line
stands last (`REVIEW_RANK`)."""
REVIEW_RANK = 7

SIBLING_DROPS: Annotated[frozenset[HeaderWord],
    quotes("solver-file.md", "Header",
           "A family sibling's header, omitting other fields:")
] = frozenset({HeaderWord.KEYWORDS, HeaderWord.CONCEPT,
               HeaderWord.INPUT, HeaderWord.OUTPUT})
"""The fields a family sibling leaves out, since it carries
`@representative:` in their place."""


def header_word_text(word: HeaderWord | ClaimKind) -> str:
    """A header line's word as the template writes it: `@keywords`,
    `@scene`, `concept`."""
    prefixed = isinstance(word, ClaimKind) or word in PREFIXED_WORDS
    return at_word(word) if prefixed else str(word)


@quotes("solver-file.md", "Params",
        "The clause containing that literal ends with `// @singleton-axis: "
        "<what the structure is>`.")
@quotes("solver-file.md", "Program",
        "an instance of a component without an `@construction` mark has the "
        "directive")
class TrailingWord(StrEnum):
    SINGLETON_AXIS = "singleton-axis"
    CONSTRUCTION = "construction"


@dataclass(frozen=True)
class TrailingDirective:
    """`// @singleton-axis: …` or `// @construction` after code."""

    word: TrailingWord
    text: str
    line: int
    unit: UnitId | DeclId | None
    """The unit or declaration on whose line it trails."""


@quotes("solver-file.md", "Program",
        "**`@workaround` directive.** A temporary workaround is under a `// "
        "@workaround: <the principled form it stands in for>` line.")
@dataclass(frozen=True)
class Workaround:
    """`// @workaround: <form>`."""

    text: str
    line: int


@dataclass(frozen=True)
class Annotations:
    """Every annotation of one solver (plan §D4 `Annotations`)."""

    header: tuple[HeaderField, ...]
    reviews: tuple[ReviewLine, ...]
    representative: Representative | None
    claims: tuple[Claim, ...]
    witnesses: tuple[WitnessLine, ...]
    derives: tuple[DeriveLine, ...]
    stores: tuple[StoreLine, ...]
    claim_lines: tuple[ClaimLine, ...]
    ignores: tuple[IgnoreLine, ...]
    markers: tuple[CaseMarker, ...]
    trailing: tuple[TrailingDirective, ...]
    workarounds: tuple[Workaround, ...]
    header_prose: tuple[Comment, ...]
    """The header's lines that open no field, no claim and no directive,
    and continue none: the header check's to judge. The task id's line
    (`task_id`) is not among them."""
    task_id: Annotated[Comment | None,
        quotes("solver-file.md", "File structure",
               "// <task_id> // @draft // @keywords: <keywords from "
               "keywords.md>")]
    """The own-line comment on line 1, the line that holds the task id; None
    where line 1 holds none."""


# The reader


_DIRECTIVE_RE = re.compile(r"^@([\w-]+)(.*)$")
_SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_CLAIM_TAIL_RE = re.compile(rf"^\s+({_SLUG}):\s*(\S.*)$")
_REF_TAIL_RE = re.compile(rf"^(?:\s+{_SLUG})+$")
_VERDICT = r"\S+(?:\s*&\s*\S+)*"
_WITNESS_TAIL_RE = re.compile(rf"^\s+({_SLUG}):\s*(\S+)\s+({_VERDICT})$")
_DERIVE_TAIL_RE = re.compile(rf"^\s+(\w+):\s*(\S+)\s+({_VERDICT})$")
_STORE_TAIL_RE = re.compile(rf"^(?:\s+([\w.]+))?:\s*(\S+)\s+({_VERDICT})$")
_IGNORE_TAIL_RE = re.compile(r"^(?:\s+([\w.]+))?:\s*(.*)$")
_PROPOSER_RE = re.compile(r"[A-Za-z_]\w*")
"""The `<Proposer>` of `@ignore: derive <Proposer>`: a bare word, which no
case name is but `concept`, since a constructor's name carries `$` and a
branch's name `=`."""
_REPRESENTATIVE_RE = re.compile(r"^(\S+)(?:\s+(\S+))?$")
_PLAIN_FIELD_RE = re.compile(r"^(\w+)(?:\s+([\w-]+))?:\s*(.*)$")
_MARKER_RE = re.compile(r"^---\s*(.*?)\s*---$")
_DASH = "—"

_RETIRED = frozenset({"invariant", "addition", "deviation"})
_NESTED_WORDS = frozenset({DirectiveWord.APPROXIMATED, DirectiveWord.RELAXED,
                           DirectiveWord.REASSIGNED})
REVIEW_WORD: Annotated[str,
    quotes("solver-file.md", "Header",
           "A `// review <kind>: <text>` line stands last in the "
           "header.")] = "review"
"""The word of a `// review <kind>:` line."""
_INPUT_MARK = "input"
"""`// @input` after a declaration: the lib's mark of a runner input, read
by no rule of the solver file."""


@dataclass(eq=False)
class _Open:
    """A line that nested and continuation lines under it join, while its
    comment block lasts: `end` is the last line joined."""

    line: int

    def __post_init__(self) -> None:
        self.end = self.line


@dataclass(eq=False)
class _OpenField(_Open):
    """A header field."""

    word: HeaderWord
    value: str
    prefixed: bool


@dataclass(eq=False)
class _OpenReview(_Open):
    """A `// review <kind>:` line."""

    kind: str
    value: str


@dataclass(eq=False)
class _OpenApproximated(_Open):
    """An `@approximated:` line, with the `@witness` lines under it."""

    value: str
    witnesses: list["_OpenWitness"] = field(default_factory=list)


@dataclass(eq=False)
class _OpenClaim(_Open):
    """An `@scene` or `@rule` claim, with its `@approximated:` lines."""

    kind: ClaimKind
    slug: str
    value: str
    constructor: str | None
    approximated: list[_OpenApproximated] = field(default_factory=list)


@dataclass(eq=False)
class _OpenVerdict(_Open):
    """A line with a plausibility and a verdict, with the `@relaxed` and
    `@reassigned` lines under it."""

    plausibility: Plausibility
    verdict: Verdict
    relaxed: list[str] = field(default_factory=list, kw_only=True)
    reassigned: list[str] = field(default_factory=list, kw_only=True)


@dataclass(eq=False)
class _OpenWitness(_OpenVerdict):
    """A `@witness` line."""

    id: str
    constructor: str | None
    approximates: str | None = None


@dataclass(eq=False)
class _OpenBranch(_OpenVerdict):
    """A `@derive` or `@store` line: `target` is the proposer or the
    relation it names, None for a `@store` line that names none."""

    target: str | None
    above: DeclId | None


type _Joined = _OpenField | _OpenReview | _OpenClaim | _OpenApproximated
"""A line a continuation line joins."""


def _content(comment: Comment) -> tuple[int, str] | None:
    """The spaces after `//` and the content after them, stripped at the
    end; None for a block comment."""
    if comment.block:
        return None
    body = comment.text
    stripped = body.lstrip(" ")
    return len(body) - len(stripped), stripped.rstrip()


def _verdict(text: str) -> Verdict:
    """A verdict word, or a name as its line writes it, for
    `names.denote` to read."""
    written = text.strip()
    try:
        return VerdictWord(written)
    except ValueError:
        return NamedVerdict(written)


def _plausibility(text: str) -> Plausibility | None:
    try:
        return Plausibility(text)
    except ValueError:
        return None


def _marker(text: str, line: int) -> CaseMarker:
    """`<names>[: gloss]`: the names split at the commas that stand outside
    parentheses, each kept as written, for `names.denote` to read
    (solver-file.md, under "Cases")."""
    head, colon, gloss = text.partition(":")
    parts = [MarkerPart(name) for name in split_top(head) if name]
    return CaseMarker(tuple(parts), gloss.strip() if colon else None, line)


def branch_band(adt: AdtType, index: int) -> tuple[int, int]:
    """The lines between which constructor `index`'s branch comment stands
    (solver-file.md, under "File structure"), both outside it: the last line of
    the constructor before it, or the type's first line, and the constructor's
    first line."""
    start = adt.span.first if index == 0 \
        else adt.constructors[index - 1].span.last
    return start, adt.constructors[index].span.first


def _constructor_at(program: Program, line: int) -> str | None:
    """The constructor whose branch comment holds `line` (`branch_band`),
    in the solver's own ADT whose declaration spans it."""
    for t in program.types:
        if isinstance(t, AdtType) and _holds(t.span, line):
            for i, c in enumerate(t.constructors):
                start, end = branch_band(t, i)
                if start < line < end:
                    return c.name
    return None


def _trailing_unit(program: Program, line: int) -> UnitId | DeclId | None:
    """The unit or declaration of the solver's own text on whose line a
    trailing comment stands: the one of the smallest span that holds the
    line."""
    found = [(x.span.last - x.span.first, x.id)
             for x in (*program.units, *program.macros, *program.declarations)
             if x.span is not None and _holds(x.span, line)]
    if not found:
        return None
    return min(found, key=lambda f: f[0])[1]


def _holds(span: Span | None, line: int) -> bool:
    """Whether `span` is of the solver's own text (`own`) and holds
    `line`."""
    return own(span) and span is not None and span.first <= line <= span.last


def read(program: Program) -> tuple[Annotations, tuple[Fault, ...]]:
    """The annotations the program's comments carry, positioned through
    each comment's `above` link and its indentation, and what could not be
    read.

    The comments read are the solver's own (`file` None) and the `//` ones: a
    line inside a block comment is no annotation. A comment block is a run of
    own-line comments on consecutive lines; the header is the block that starts
    on line 1 (solver-file.md, under "File structure"). A nested line carries
    two spaces or more after `//` (solver-file.md, under "File structure"); a
    line of two spaces or more that opens no directive continues the field or
    claim above it (solver-file.md, under "File structure")."""
    problems: list[Fault] = []

    def problem(kind: ProblemKind, line: int, read: str | Detail) -> None:
        problems.append(Fault(
            kind, InSolver(line),
            Quoted(read) if isinstance(read, str) else read))

    owned = sorted((c for c in program.comments if own(c)),
                   key=lambda c: (c.line, c.column))
    header_end = 0
    for c in owned:
        if not c.own_line or c.line != header_end + 1 \
                or _content(c) is None:
            break
        header_end = c.line

    fields: list[_OpenField] = []
    reviews: list[_OpenReview] = []
    representatives: list[Representative] = []
    claims: list[_OpenClaim] = []
    witnesses: list[_OpenWitness] = []
    derives: list[_OpenBranch] = []
    stores: list[_OpenBranch] = []
    claim_lines: list[ClaimLine] = []
    ignores: list[IgnoreLine] = []
    markers: list[CaseMarker] = []
    trailing: list[TrailingDirective] = []
    workarounds: list[Workaround] = []
    header_prose: list[Comment] = []

    # Whether each own-line comment is the last of its block but for
    # continuation lines, for the `@ignore` lines that stand directly above
    # their declaration.
    blocks: list[list[Comment]] = []
    for c in owned:
        if not c.own_line:
            continue
        if blocks and blocks[-1][-1].line + 1 == c.line:
            blocks[-1].append(c)
        else:
            blocks.append([c])
    last_of_block: dict[int, bool] = {}
    for block in blocks:
        # Each comment's answer is whether every comment after it
        # continues, so the block is read once from its end.
        rest_continues = True
        for c in reversed(block):
            last_of_block[c.line] = rest_continues
            r = _content(c)
            rest_continues = rest_continues and r is not None \
                and r[0] >= 2 and not r[1].startswith("@")

    open_field: _Joined | None = None   # a field or claim a continuation joins
    open_claim: _OpenClaim | None = None  # a claim an `@approximated:` joins
    open_approx: _OpenApproximated | None = None  # an `@approximated:` a witness joins
    open_block: _OpenVerdict | None = None  # a witness, derive or store line
    prev_line = -1

    def close() -> None:
        nonlocal open_field, open_claim, open_approx, open_block
        open_field = open_claim = open_approx = open_block = None

    for c in owned:
        got = _content(c)
        if got is None:
            continue
        spaces, content = got
        line = c.line
        if not c.own_line:
            d = _DIRECTIVE_RE.match(content)
            if d is not None:
                word, tail = d[1], d[2].strip()
                tail = tail[1:].strip() if tail.startswith(":") else tail
                if word in (TrailingWord.SINGLETON_AXIS,
                            TrailingWord.CONSTRUCTION):
                    trailing.append(TrailingDirective(
                        TrailingWord(word), tail, line,
                        _trailing_unit(program, line)))
                elif word != _INPUT_MARK:
                    problem(ProblemKind.UNKNOWN_FORM, line, content)
            close()
            prev_line = -1
            continue
        if line != prev_line + 1:
            close()
        prev_line = line
        in_header = line <= header_end
        above = c.above if isinstance(c.above, DeclId) else None
        d = _DIRECTIVE_RE.match(content)
        if d is None:
            if content and spaces >= 2 and (open_field is not None
                                            or not in_header):
                if open_field is not None:
                    sep = " " if open_field.value else ""
                    open_field.value = f"{open_field.value}{sep}{content}"
                    open_field.end = line
                continue
            if (m := _MARKER_RE.match(content)) and m[1].strip("-").strip():
                markers.append(_marker(m[1], line))
                close()
                continue
            plain = _PLAIN_FIELD_RE.match(content) if in_header else None
            close()
            if plain is not None and plain[1] == REVIEW_WORD and plain[2]:
                reviews.append(_OpenReview(line, plain[2], plain[3].strip()))
                open_field = reviews[-1]
                continue
            if plain is not None and plain[2] is None:
                try:
                    word = HeaderWord(plain[1])
                except ValueError:
                    word = None
                if word is not None:
                    fields.append(_OpenField(line, word, plain[3].strip(),
                                             False))
                    open_field = fields[-1]
                    continue
            if in_header and content == HeaderWord.DRAFT:
                fields.append(_OpenField(line, HeaderWord.DRAFT, "", False))
            elif in_header and line > 1 and content:
                header_prose.append(c)
            continue
        word, tail = d[1], d[2]
        if word in _NESTED_WORDS and spaces < 2:
            problem(ProblemKind.OFF_FORM, line, content)
        if word in _RETIRED:
            problem(ProblemKind.RETIRED_FORM, line, content)
            close()
            continue
        if word == HeaderWord.DRAFT:
            close()
            fields.append(_OpenField(line, HeaderWord.DRAFT, "", True))
            if tail.strip():
                problem(ProblemKind.OFF_FORM, line, content)
            continue
        if word in (HeaderWord.KEYWORDS, HeaderWord.REPRESENTATIVE,
                    HeaderWord.INPUT, HeaderWord.OUTPUT, HeaderWord.CONCEPT):
            close()
            if not tail.startswith(":"):
                problem(ProblemKind.OFF_FORM, line, content)
                continue
            fields.append(_OpenField(line, HeaderWord(word),
                                     tail[1:].strip(), True))
            open_field = fields[-1]
            continue
        if word in (ClaimKind.SCENE, ClaimKind.RULE):
            close()
            m = _CLAIM_TAIL_RE.match(tail)
            if m is None:
                kind = (ProblemKind.RETIRED_FORM
                        if word == ClaimKind.RULE and _REF_TAIL_RE.match(tail)
                        else ProblemKind.OFF_FORM)
                problem(kind, line, content)
                continue
            claims.append(_OpenClaim(
                line, ClaimKind(word), m[1], m[2].strip(),
                None if in_header else _constructor_at(program, line)))
            open_field = open_claim = claims[-1]
            continue
        if word == DirectiveWord.CLAIM:
            close()
            if not _REF_TAIL_RE.match(tail):
                problem(ProblemKind.OFF_FORM, line, content)
                continue
            claim_lines.append(ClaimLine(tuple(tail.split()), line, above))
            continue
        if word == DirectiveWord.WITNESS:
            nested = spaces >= 2
            m = _WITNESS_TAIL_RE.match(tail)
            plaus = None if m is None else _plausibility(m[2])
            if m is None or plaus is None:
                problem(ProblemKind.OFF_FORM, line, content)
                open_block = None
                continue
            block = _OpenWitness(
                line, plaus, _verdict(m[3]), m[1],
                None if in_header else _constructor_at(program, line))
            if nested:
                if open_approx is None or open_claim is None:
                    problem(ProblemKind.OFF_FORM, line, content)
                    open_block = None
                    continue
                block.approximates = open_claim.slug
                open_approx.witnesses.append(block)
                open_field = None
            else:
                open_field = open_claim = open_approx = None
            witnesses.append(block)
            open_block = block
            continue
        if word in (DirectiveWord.DERIVE, DirectiveWord.STORE):
            close()
            m = (_DERIVE_TAIL_RE if word == DirectiveWord.DERIVE
                 else _STORE_TAIL_RE).match(tail)
            plaus = None if m is None else _plausibility(m[2])
            if m is None or plaus is None:
                problem(ProblemKind.OFF_FORM, line, content)
                continue
            branch = _OpenBranch(line, plaus, _verdict(m[3]), m[1], above)
            (derives if word == DirectiveWord.DERIVE else stores).append(branch)
            open_block = branch
            continue
        if word == DirectiveWord.APPROXIMATED:
            if not tail.startswith(":") or open_claim is None \
                    or open_claim.kind != ClaimKind.RULE:
                problem(ProblemKind.OFF_FORM, line, content)
                continue
            approx = _OpenApproximated(line, tail[1:].strip())
            open_claim.approximated.append(approx)
            open_approx = open_field = approx
            continue
        if word in (DirectiveWord.RELAXED, DirectiveWord.REASSIGNED):
            value = tail.strip()
            if not value or " " in value or open_block is None \
                    or (word == DirectiveWord.REASSIGNED
                        and not isinstance(open_block, _OpenWitness)):
                problem(ProblemKind.OFF_FORM, line, content)
                continue
            (open_block.relaxed if word == DirectiveWord.RELAXED
             else open_block.reassigned).append(value)
            continue
        if word == DirectiveWord.IGNORE:
            _ignore(tail, content, line, above, last_of_block[line],
                    ignores, problem)
            continue
        if word == DirectiveWord.WORKAROUND:
            if not tail.startswith(":") or not tail[1:].strip():
                problem(ProblemKind.OFF_FORM, line, content)
            else:
                workarounds.append(Workaround(tail[1:].strip(), line))
            continue
        if word == _INPUT_MARK:
            continue
        problem(ProblemKind.UNKNOWN_FORM, line, content)
        close()

    for f in fields:
        if f.word != HeaderWord.REPRESENTATIVE:
            continue
        m = _REPRESENTATIVE_RE.match(f.value)
        if m is None:
            problem(ProblemKind.OFF_FORM, f.line, f.value)
        else:
            representatives.append(Representative(m[1], m[2], f.line))
    if len(representatives) > 1:
        problem(ProblemKind.UNDECIDED, representatives[1].line,
                Undecided(UndecidedForm.SECOND_REPRESENTATIVE, None))

    def witness_of(w: _OpenWitness) -> WitnessLine:
        return WitnessLine(
            w.id, w.plausibility, w.verdict, w.line, tuple(w.relaxed),
            tuple(w.reassigned), w.approximates, w.constructor)

    annotations = Annotations(
        header=tuple(HeaderField(f.word, f.value, f.line, f.end, f.prefixed)
                     for f in fields),
        reviews=tuple(ReviewLine(r.kind, r.value, r.line) for r in reviews),
        representative=representatives[0] if representatives else None,
        claims=tuple(Claim(
            c.kind, c.slug, c.value, c.line,
            tuple(Approximated(a.value, a.line,
                               tuple(witness_of(w) for w in a.witnesses))
                  for a in c.approximated),
            c.constructor) for c in claims),
        witnesses=tuple(witness_of(w) for w in witnesses),
        derives=tuple(DeriveLine(
            _as(d.target, str), d.plausibility, d.verdict, d.line, d.above,
            tuple(d.relaxed)) for d in derives),
        stores=tuple(StoreLine(
            s.target, s.plausibility, s.verdict, s.line, s.above,
            tuple(s.relaxed)) for s in stores),
        claim_lines=tuple(claim_lines),
        ignores=tuple(ignores),
        markers=tuple(markers),
        trailing=tuple(trailing),
        workarounds=tuple(workarounds),
        header_prose=tuple(header_prose),
        task_id=next((c for c in owned if c.line == 1 and c.own_line),
                     None),
    )
    return annotations, tuple(sorted(problems, key=_problem_line))


def _problem_line(p: Fault) -> int:
    return p.place.line if isinstance(p.place, InSolver) else 0


def _as[T](value: object, kind: type[T]) -> T:
    assert isinstance(value, kind)
    return value


def _ignore(tail: str, content: str, line: int, above: DeclId | None,
            last: bool, out: list[IgnoreLine],
            problem: Callable[[ProblemKind, int, str | Detail], None]
            ) -> None:
    """One `@ignore` line (solver-file.md, under "Params" and "Program"). The
    lint form stands on the declaration directly under it, with no other
    directive between (solver-file.md, under "Program"); the derive and store
    forms stand on the declaration their comment block stands above."""
    m = _IGNORE_TAIL_RE.match(tail)
    if m is None:
        problem(ProblemKind.OFF_FORM, line, content)
        return
    relation, rest = m[1], m[2]
    given, dash, reason = rest.partition(_DASH)
    given, reason = " ".join(given.split()), reason.strip()
    if not dash or not reason or not given:
        problem(ProblemKind.OFF_FORM, line, content)
        if not given:
            return
    first, _sp, name = given.partition(" ")
    if first in (IgnoreForm.DERIVE, IgnoreForm.STORE):
        if first == IgnoreForm.DERIVE and relation is not None:
            problem(ProblemKind.OFF_FORM, line, content)
            return
        name = name.strip()
        if first == IgnoreForm.DERIVE and _PROPOSER_RE.fullmatch(name) \
                and name != VerdictWord.CONCEPT:
            out.append(IgnoreLine(IgnoreForm.DERIVE, None, None, None,
                                  reason, line, above, name))
            return
        out.append(IgnoreLine(IgnoreForm(first), None, relation,
                              name or None, reason, line, above))
        return
    try:
        category = Category(given)
    except ValueError:
        problem(ProblemKind.UNKNOWN_IGNORE_CATEGORY, line, Named(given))
        return
    out.append(IgnoreLine(IgnoreForm.LINT, category, relation, None, reason,
                          line, above if last else None))


# Writing annotation lines

class Slot(StrEnum):
    """The slots a line the tool asks the session to add holds where the
    session writes its own judgment."""

    ID = "<id>"
    PLAUSIBILITY = "<plausibility>"
    VERDICT = "<verdict>"
    REASON = "<reason>"


def at_word(word: "DirectiveWord | HeaderWord | ClaimKind") -> str:
    """A word of an `@` line as the line writes it, after its `@`:
    `@witness`, `@derive`, `@scene`."""
    return f"@{word}"


def _named(relation: str | None) -> str:
    """The relation a `@store` or `@ignore` line names after its word,
    with the space before it; nothing where it names none."""
    return f" {relation}" if relation is not None else ""


def comment_text(line: str) -> str:
    """An annotation line as a `//` comment of the solver file."""
    return f"// {line}"


def verdict_text(verdict: Verdict | Slot) -> str:
    """A verdict as its line writes it: its word, or its name; a slot as
    the slot."""
    if isinstance(verdict, NamedVerdict):
        return verdict.text
    return verdict.value


def _judgment(plausibility: Plausibility | Slot,
              verdict: Verdict | Slot) -> str:
    """The plausibility and verdict a `@witness`, `@derive` or `@store`
    line ends with."""
    return f"{plausibility.value} {verdict_text(verdict)}"


def witness_text(id: str | Slot, plausibility: Plausibility | Slot,
                 verdict: Verdict | Slot) -> str:
    """A `@witness` line (solver-file.md, under "File structure"), as the
    reader reads it."""
    return (f"{at_word(DirectiveWord.WITNESS)} {id}: "
            f"{_judgment(plausibility, verdict)}")


def derive_text(proposer: str, plausibility: Plausibility | Slot,
                verdict: Verdict | Slot) -> str:
    """A `@derive` line (solver-file.md, under "Params"), as the reader reads
    it."""
    return (f"{at_word(DirectiveWord.DERIVE)} {proposer}: "
            f"{_judgment(plausibility, verdict)}")


def store_text(relation: str | None, plausibility: Plausibility | Slot,
               verdict: Verdict | Slot) -> str:
    """A `@store` line (solver-file.md, under "Program"), naming the relation
    of an instance where it stands above an `.init`."""
    return (f"{at_word(DirectiveWord.STORE)}{_named(relation)}: "
            f"{_judgment(plausibility, verdict)}")


def ignore_text(relation: str | None, what: Category | IgnoreForm,
                reason: str | Slot | None = None, proposer: str | None = None
                ) -> str:
    """An `@ignore` line (solver-file.md, under "Params" and "Program"):
    `what` is the category of the lint form, or the derive or store form,
    the derive form with `proposer` where it is given; `reason` follows the
    dash where it is given. The lint form without its category raises
    `ValueError`."""
    if what == IgnoreForm.LINT:
        raise ValueError("an `@ignore` line of the lint form has a category")
    word = what.value if proposer is None else f"{what.value} {proposer}"
    tail = f" {_DASH} {reason}" if reason is not None else ""
    return f"{at_word(DirectiveWord.IGNORE)}{_named(relation)}: {word}{tail}"
