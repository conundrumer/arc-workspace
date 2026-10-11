"""The handbook syntax a solver carries in comments, as one reader over the
engine's comment list gives it."""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated

from engine import Comment, DeclId, Engine, Program, UnitId
from engine.program import AdtType, Span, own
from engine.quotes import quotes
from solver.category import Category
from solver.problems import (
    Detail,
    InSolver,
    FormPart,
    Named,
    OffForm,
    OffPart,
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
        "line gives, has one value on every input, and the line is a branch "
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
        "<reason>`, with the category the hint gives, in the run of "
        "`@ignore` lines directly above its declaration.")
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

    @property
    def directive(self) -> "DirectiveWord | None":
        """The directive whose line a bare `@ignore` line of this form
        stands in place of; None for a lint category."""
        return {IgnoreForm.DERIVE: DirectiveWord.DERIVE,
                IgnoreForm.STORE: DirectiveWord.STORE}.get(self)


@quotes("solver-file.md", "Program",
        "**`@ignore` directive.** A relation kept despite a hint has `// "
        "@ignore: <category> — <reason>`, with the category the hint gives, "
        "in the run of `@ignore` lines directly above its declaration.")
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


def marker_line(engine: Engine, text: str) -> str:
    """The comment line of a case marker whose text between its dashes is
    `text`, as the solver writes it."""
    return engine.line_comment(f"{_MARKER_DASHES} {text} {_MARKER_DASHES}")


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


NESTS_UNDER: Annotated[dict[DirectiveWord, tuple[DirectiveWord | ClaimKind, ...]],
    quotes("solver-file.md", "File structure",
           "// @rule <slug>: <what the output takes from the input> // "
           "@approximated: <the rule the program runs> // @witness <id>: "
           "<plausibility> <verdict>")] = {
    DirectiveWord.APPROXIMATED: (ClaimKind.RULE,),
    DirectiveWord.WITNESS: (DirectiveWord.APPROXIMATED,),
    DirectiveWord.RELAXED: (DirectiveWord.WITNESS, DirectiveWord.DERIVE,
                            DirectiveWord.STORE),
    DirectiveWord.REASSIGNED: (DirectiveWord.WITNESS,),
}
"""The lines each nested line nests under: a `@witness` line with two
spaces or more after `//` among them."""


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
    """Every annotation of one solver."""

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
_SLUG_RE = re.compile(_SLUG)
_REF_TAIL_RE = re.compile(rf"^(?:\s+{_SLUG})+$")
_VERDICT_RE = re.compile(r"\S+(?:\s*&\s*\S+)*")
_JUDGMENT_RE = re.compile(r"\s*(\S+)(?:\s+(\S.*))?")
"""A plausibility, and the verdict after it."""
_DERIVE_NAME_RE = re.compile(r"\w+")
"""The proposer a `@derive` line names."""
_RELATION_RE = re.compile(r"[\w.]+")
"""The relation a `@store` or `@ignore` line names."""
_PROPOSER_RE = re.compile(r"[A-Za-z_]\w*")
"""The `<Proposer>` of `@ignore: derive <Proposer>`: a bare word, which no
case name is but `concept`, since a constructor's name carries `$` and a
branch's name `=`."""
_REPRESENTATIVE_RE = re.compile(r"^(\S+)(?:\s+(\S+))?$")
_PLAIN_FIELD_RE = re.compile(r"^(\w+)(?:\s+([\w-]+))?:\s*(.*)$")
_MARKER_DASHES = "---"
_MARKER_RE = re.compile(rf"^{_MARKER_DASHES}\s*(.*?)\s*{_MARKER_DASHES}$")
_DASH = "—"

_RETIRED = frozenset({"invariant", "addition", "deviation"})
_NESTED_WORDS = frozenset(NESTS_UNDER) - {DirectiveWord.WITNESS}
"""The words whose line is always nested: each word of `NESTS_UNDER` but
`@witness`, whose line nests only where two spaces or more follow `//`."""
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
    word: DirectiveWord = field(kw_only=True)
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


def input_mark_lines(comments: Iterable[Comment]) -> frozenset[int]:
    """The lines on which a trailing comment of the parsed text's own
    `comments` is the lib's `// @input` mark."""
    out: set[int] = set()
    for c in comments:
        got = _content(c)
        if got is None or c.own_line or not own(c):
            continue
        d = _DIRECTIVE_RE.match(got[1])
        if d is not None and d[1] == _INPUT_MARK:
            out.add(c.line)
    return frozenset(out)


def input_marked(span: Span, marks: frozenset[int]) -> bool:
    return not marks.isdisjoint(range(span.first, span.last + 1))


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


def _split_colon(tail: str) -> tuple[str, str | None, list[OffPart]]:
    """`tail` at its first `:`: the text before it; the text after it,
    None where no `:` stands; and the parts off form of the `:` with no
    name before it: `COLON` where no `:` stands, `SPACING` where only
    spaces stand before it, none where nothing does."""
    head, colon, rest = tail.partition(":")
    if not colon:
        return head, None, [OffPart(FormPart.COLON, None)]
    if head and not head.strip():
        return head, rest, [OffPart(FormPart.SPACING, None)]
    return head, rest, []


def _colon(tail: str) -> tuple[str | None, list[OffPart]]:
    """The text after the `:` that opens `tail`, and the parts off form
    where none opens it (`_split_colon`); `COLON` where other text stands
    before the first `:`."""
    head, rest, parts = _split_colon(tail)
    if head.strip():
        return None, [OffPart(FormPart.COLON, None)]
    return (None if parts else rest), parts


def _name_colon(tail: str, name: re.Pattern[str], part: FormPart,
                optional: bool
                ) -> tuple[str | None, str | None, list[OffPart]]:
    """A name in `name`'s form, one or more spaces before it and none
    between it and the `:` after it, then the `:`: the name, None where
    `optional` and the line gives none; the text after the `:`, None where
    no `:` stands; and the parts off form, the name's as `part`."""
    head, rest, parts = _split_colon(tail)
    if rest is None:
        return None, None, parts
    written = head.strip()
    if not written:
        return None, rest, parts if optional else [OffPart(part, None)]
    if not name.fullmatch(written):
        return written, rest, [OffPart(part, written)]
    if not head[0].isspace() or head[-1].isspace():
        return written, rest, [OffPart(FormPart.SPACING, written)]
    return written, rest, []


def _read_judgment(rest: str | None
                   ) -> tuple[Plausibility | None, Verdict | None, list[OffPart]]:
    """The plausibility and the verdict after the `:` of a `@witness`,
    `@derive` or `@store` line, and the parts off form; no part where no
    `:` stands, whose own part stands in its place."""
    if rest is None:
        return None, None, []
    m = _JUDGMENT_RE.fullmatch(rest)
    if m is None:
        return None, None, [OffPart(FormPart.PLAUSIBILITY, None)]
    off: list[OffPart] = []
    plausibility = _plausibility(m[1])
    if plausibility is None:
        off.append(OffPart(FormPart.PLAUSIBILITY, m[1]))
    written: str | None = m[2]
    if written is None:
        off.append(OffPart(FormPart.VERDICT, None))
        return plausibility, None, off
    if not _VERDICT_RE.fullmatch(written):
        off.append(OffPart(FormPart.VERDICT, written))
        return plausibility, None, off
    return plausibility, _verdict(written), off


def _marker(engine: Engine, text: str, line: int) -> CaseMarker:
    """`<names>[: gloss]`: the names split at the commas that stand outside
    parentheses, each kept as written, for `names.denote` to read
    (solver-file.md, under "Cases")."""
    head, colon, gloss = text.partition(":")
    parts = [MarkerPart(name) for name in engine.split_top(head) if name]
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


def read(engine: Engine, program: Program
         ) -> tuple[Annotations, tuple[Fault, ...]]:
    """The annotations the program's comments carry, positioned through
    each comment's `above` link and its indentation, and what could not be
    read.

    The comments read are the solver's own (`file` None) and the `//` ones: a
    line inside a block comment is no annotation. A comment block is a run of
    own-line comments on consecutive lines; the header is the block that starts
    on line 1 (solver-file.md, under "File structure"). A nested line carries
    two spaces or more after `//` (solver-file.md, under "File structure"); a
    line of two spaces or more that opens no directive continues the field or
    claim above it (solver-file.md, under "File structure"). A line off its
    word's form gives one fault, with each part of it found off the form
    (`OffForm`)."""
    problems: list[Fault] = []
    off_at: dict[int, int] = {}
    """The index in `problems` of the off-form fault of each line."""

    def problem(kind: ProblemKind, line: int, read: str | Detail) -> None:
        problems.append(Fault(
            kind, InSolver(line),
            Quoted(read) if isinstance(read, str) else read))

    def off(line: int, text: str, word: DirectiveWord | HeaderWord | ClaimKind,
            parts: Iterable[OffPart]) -> None:
        """The parts of the line `line` off its word's form, joined to the
        line's fault."""
        if line not in off_at:
            off_at[line] = len(problems)
            problem(ProblemKind.OFF_FORM, line, OffForm(text, word, ()))
        had = problems[off_at[line]]
        assert isinstance(had.detail, OffForm)
        problems[off_at[line]] = Fault(had.kind, had.place, OffForm(
            had.detail.text, had.detail.word,
            (*had.detail.parts, *parts)))

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

    # Whether each own-line comment stands in the run of `@ignore` lines at
    # the end of its block, for the lint-form `@ignore` lines that stand on
    # their declaration.
    blocks: list[list[Comment]] = []
    for c in owned:
        if not c.own_line:
            continue
        if blocks and blocks[-1][-1].line + 1 == c.line:
            blocks[-1].append(c)
        else:
            blocks.append([c])
    in_ignore_run: dict[int, bool] = {}
    for block in blocks:
        # Each comment's answer is whether every comment after it is an
        # `@ignore` line or a continuation line, so the block is read once
        # from its end.
        rest_in_run = True
        for c in reversed(block):
            in_ignore_run[c.line] = rest_in_run
            r = _content(c)
            d = _DIRECTIVE_RE.match(r[1]) if r is not None else None
            rest_in_run = rest_in_run and r is not None and (
                d[1] == DirectiveWord.IGNORE if d is not None
                else r[0] >= 2 and not r[1].startswith("@"))

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
                markers.append(_marker(engine, m[1], line))
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
            off(line, content, DirectiveWord(word),
                [OffPart(FormPart.INDENT, None)])
        if word in _RETIRED:
            problem(ProblemKind.RETIRED_FORM, line, content)
            close()
            continue
        if word == HeaderWord.DRAFT:
            close()
            fields.append(_OpenField(line, HeaderWord.DRAFT, "", True))
            if tail.strip():
                off(line, content, HeaderWord.DRAFT,
                    [OffPart(FormPart.TRAILING, tail.strip())])
            continue
        if word in (HeaderWord.KEYWORDS, HeaderWord.REPRESENTATIVE,
                    HeaderWord.INPUT, HeaderWord.OUTPUT, HeaderWord.CONCEPT):
            close()
            value, parts = _colon(tail)
            if value is None:
                off(line, content, HeaderWord(word), parts)
                continue
            fields.append(_OpenField(line, HeaderWord(word), value.strip(),
                                     True))
            open_field = fields[-1]
            continue
        if word in (ClaimKind.SCENE, ClaimKind.RULE):
            close()
            slug, rest, parts = _name_colon(tail, _SLUG_RE, FormPart.SLUG,
                                            False)
            if rest is not None and not rest.strip():
                parts.append(OffPart(FormPart.TEXT, None))
            if parts:
                if word == ClaimKind.RULE and _REF_TAIL_RE.match(tail):
                    problem(ProblemKind.RETIRED_FORM, line, content)
                else:
                    off(line, content, ClaimKind(word), parts)
                continue
            assert slug is not None and rest is not None
            claims.append(_OpenClaim(
                line, ClaimKind(word), slug, rest.strip(),
                None if in_header else _constructor_at(program, line)))
            open_field = open_claim = claims[-1]
            continue
        if word == DirectiveWord.CLAIM:
            close()
            slugs = tail.split()
            parts = [OffPart(FormPart.SLUG, s) for s in slugs
                     if not _SLUG_RE.fullmatch(s)]
            if not slugs:
                parts.append(OffPart(FormPart.SLUG, None))
            if parts:
                off(line, content, DirectiveWord.CLAIM, parts)
                continue
            claim_lines.append(ClaimLine(tuple(slugs), line, above))
            continue
        if word == DirectiveWord.WITNESS:
            nested = spaces >= 2
            wid, rest, parts = _name_colon(tail, _SLUG_RE, FormPart.ID,
                                          False)
            plaus, verdict, judged = _read_judgment(rest)
            parts += judged
            if nested and (open_approx is None or open_claim is None):
                parts.append(OffPart(FormPart.PARENT, None))
            if parts:
                off(line, content, DirectiveWord.WITNESS, parts)
                open_block = None
                continue
            assert wid is not None and plaus is not None \
                and verdict is not None
            block = _OpenWitness(
                line, plaus, verdict, wid,
                None if in_header else _constructor_at(program, line),
                word=DirectiveWord.WITNESS)
            if nested:
                assert open_approx is not None and open_claim is not None
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
            directive = DirectiveWord(word)
            target, rest, parts = (
                _name_colon(tail, _DERIVE_NAME_RE, FormPart.PROPOSER, False)
                if directive == DirectiveWord.DERIVE
                else _name_colon(tail, _RELATION_RE, FormPart.RELATION, True))
            plaus, verdict, judged = _read_judgment(rest)
            parts += judged
            if parts:
                off(line, content, directive, parts)
                continue
            assert plaus is not None and verdict is not None
            branch = _OpenBranch(line, plaus, verdict, target, above,
                                 word=directive)
            (derives if directive == DirectiveWord.DERIVE
             else stores).append(branch)
            open_block = branch
            continue
        if word == DirectiveWord.APPROXIMATED:
            value, parts = _colon(tail)
            if open_claim is None or open_claim.kind \
                    not in NESTS_UNDER[DirectiveWord.APPROXIMATED]:
                parts.append(OffPart(FormPart.PARENT, None))
            if parts:
                off(line, content, DirectiveWord.APPROXIMATED, parts)
                continue
            assert value is not None and open_claim is not None
            approx = _OpenApproximated(line, value.strip())
            open_claim.approximated.append(approx)
            open_approx = open_field = approx
            continue
        if word in (DirectiveWord.RELAXED, DirectiveWord.REASSIGNED):
            directive = DirectiveWord(word)
            value = tail.strip()
            parts = [] if value and " " not in value \
                else [OffPart(FormPart.VALUE, value or None)]
            if open_block is None \
                    or open_block.word not in NESTS_UNDER[directive]:
                parts.append(OffPart(FormPart.PARENT, None))
            if parts:
                off(line, content, directive, parts)
                continue
            assert open_block is not None
            (open_block.relaxed if directive == DirectiveWord.RELAXED
             else open_block.reassigned).append(value)
            continue
        if word == DirectiveWord.IGNORE:
            _ignore(tail, content, line, above, in_ignore_run[line],
                    ignores, problem, off)
            continue
        if word == DirectiveWord.WORKAROUND:
            value, parts = _colon(tail)
            if value is not None and not value.strip():
                parts.append(OffPart(FormPart.TEXT, None))
            if parts:
                off(line, content, DirectiveWord.WORKAROUND, parts)
            else:
                assert value is not None
                workarounds.append(Workaround(value.strip(), line))
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
            written = at_word(f.word) if f.prefixed else f.word.value
            off(f.line, f"{written}: {f.value}", f.word,
                [OffPart(FormPart.REPRESENTATIVE, f.value)
                 if f.value else OffPart(FormPart.TEXT, None)])
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
            in_run: bool, out: list[IgnoreLine],
            problem: Callable[[ProblemKind, int, str | Detail], None],
            off: Callable[[int, str, DirectiveWord, Iterable[OffPart]], None]
            ) -> None:
    """One `@ignore` line (solver-file.md, under "Params" and "Program"). The
    lint form stands on the declaration its comment block stands above where
    only `@ignore` lines and their continuation lines stand between
    (solver-file.md, under "Program"); the derive and store forms stand on
    the declaration their comment block stands above."""
    relation, rest, parts = _name_colon(tail, _RELATION_RE,
                                        FormPart.RELATION, True)
    if rest is None or parts:
        off(line, content, DirectiveWord.IGNORE, parts)
        return
    given, dash, reason = rest.partition(_DASH)
    given, reason = " ".join(given.split()), reason.strip()
    if not given:
        parts.append(OffPart(FormPart.TEXT, None))
    if not dash:
        parts.append(OffPart(FormPart.DASH, None))
    elif not reason:
        parts.append(OffPart(FormPart.REASON, None))
    if parts:
        off(line, content, DirectiveWord.IGNORE, parts)
        if not given:
            return
    first, _sp, name = given.partition(" ")
    if first in (IgnoreForm.DERIVE, IgnoreForm.STORE):
        if first == IgnoreForm.DERIVE and relation is not None:
            off(line, content, DirectiveWord.IGNORE,
                [OffPart(FormPart.DERIVE_RELATION, relation)])
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
                          line, above if in_run else None))


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


def comment_text(engine: Engine, line: str) -> str:
    """An annotation line as a `//` comment of the solver file
    (`engine.Engine.line_comment`)."""
    return engine.line_comment(line)


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
