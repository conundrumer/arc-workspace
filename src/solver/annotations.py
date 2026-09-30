"""The handbook syntax a solver carries in comments, as one reader over the
engine's comment list gives it."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from engine import Comment, DeclId, Program, TypeDecl, UnitId
from engine.program import AdtType, Component, Instance, RelationDecl
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


class HeaderWord(StrEnum):
    """solver-file.md:11-90 (the template and Header)."""

    DRAFT = "draft"
    KEYWORDS = "keywords"
    REPRESENTATIVE = "representative"
    INPUT = "input"
    OUTPUT = "output"
    CONCEPT = "concept"


@dataclass(frozen=True)
class HeaderField:
    """A header field, solver-file.md:11-90. `prefixed` is false for the
    plain `input:`, `output:` and `concept:` forms. (The annotation
    `Field`; the syntax one is `engine.program.TypeField`.)"""

    word: HeaderWord
    value: str
    line: int
    end: int
    prefixed: bool


@dataclass(frozen=True)
class ReviewLine:
    """`// review <kind>: <text>`, solver-file.md:84."""

    kind: str
    text: str
    line: int


@dataclass(frozen=True)
class Representative:
    """`@representative: <task id> [<Case>]`, solver-file.md:90."""

    task_id: str
    case: str | None
    line: int


class Plausibility(StrEnum):
    """principles.md:136 (plausibility)."""

    ORDINARY = "ordinary"
    VARIANT = "variant"
    BORDERLINE = "borderline"
    FOREIGN = "foreign"


class VerdictWord(StrEnum):
    """principles.md:150-153; `derived` solver-file.md:121, `stored`
    solver-file.md:138."""

    CONCEPT = "concept"
    ANY = "any"
    OTHER = "other"
    DERIVED = "derived"
    STORED = "stored"


@dataclass(frozen=True)
class NamedVerdict:
    """A verdict that names a branch, or branches joined by `&`
    (principles.md:150-153): the name as its line writes it, whose parts
    `names.denote` reads."""

    text: str


type Verdict = VerdictWord | NamedVerdict


@dataclass(frozen=True)
class WitnessLine:
    """`@witness <id>: <plausibility> <verdict>` with its nested `@relaxed`
    and `@reassigned` lines, solver-file.md:11-79 and procedure.md:150.
    (The comment line; a witness file entry is `solver.witness.Entry`.)"""

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


class ClaimKind(StrEnum):
    """solver-file.md:82 (`@scene` and `@rule`)."""

    SCENE = "scene"
    RULE = "rule"


@dataclass(frozen=True)
class Approximated:
    """`@approximated: <text>` under a `@rule`, solver-file.md:92-93."""

    text: str
    line: int
    witnesses: tuple[WitnessLine, ...]


@dataclass(frozen=True)
class Claim:
    """`@scene` or `@rule` `<slug>: <text>`, solver-file.md:82 and :101."""

    kind: ClaimKind
    slug: str
    text: str
    line: int
    approximated: tuple[Approximated, ...]
    constructor: str | None
    """The constructor whose branch comment holds it; None in the header."""


@dataclass(frozen=True)
class DeriveLine:
    """`@derive <Proposer>: <plausibility> <verdict>`, solver-file.md:120-121."""

    proposer: str
    plausibility: Plausibility
    verdict: Verdict
    line: int
    above: DeclId | None
    """The declaration it stands directly above; None where it stands
    above none."""
    relaxed: tuple[str, ...]


@dataclass(frozen=True)
class StoreLine:
    """`@store: …` above a `.decl`, or `@store <rel>: …` above an `.init`,
    solver-file.md:137-138."""

    relation: str | None
    """The relation the line names; None for the bare form."""
    plausibility: Plausibility
    verdict: Verdict
    line: int
    above: DeclId | None
    relaxed: tuple[str, ...]


@dataclass(frozen=True)
class ClaimLine:
    """`// @claim <slug>…` above an instance, solver-file.md:140-142. (The
    annotation `Ref`; the syntax one is `engine.Occurrence`.)"""

    slugs: tuple[str, ...]
    line: int
    above: DeclId | None


class IgnoreForm(StrEnum):
    LINT = "lint"
    """`@ignore: <category>` and `@ignore <rel>: <category>`,
    solver-file.md:134-136."""
    DERIVE = "derive"
    """`@ignore: derive [<name>]`, solver-file.md:122."""
    STORE = "store"
    """`@ignore [<rel>]: store [<name>]`, solver-file.md:138."""


@dataclass(frozen=True)
class IgnoreLine:
    """An `@ignore` line of any form, solver-file.md:122, :134-136, :138."""

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


@dataclass(frozen=True)
class MarkerPart:
    """One name a case marker lists, as written (solver-file.md:105-106),
    for `names.denote` to read."""

    name: str

    @property
    def prose(self) -> bool:
        """Whether the part is prose: more than one word stands between two
        of its `&`s, as in `Size decompose data`, whatever word it starts
        with. A prose part lists no case and denotes nothing."""
        return any(len(piece.split()) > 1 for piece in self.name.split("&"))


@dataclass(frozen=True)
class CaseMarker:
    """`// --- <names>[: gloss] ---`, solver-file.md:104-107."""

    parts: tuple[MarkerPart, ...]
    gloss: str | None
    line: int


class TrailingWord(StrEnum):
    SINGLETON_AXIS = "singleton-axis"
    """solver-file.md:118-119."""
    CONSTRUCTION = "construction"
    """solver-file.md:140."""


@dataclass(frozen=True)
class TrailingDirective:
    """`// @singleton-axis: …` or `// @construction` after code."""

    word: TrailingWord
    text: str
    line: int
    unit: UnitId | DeclId | None
    """The unit or declaration on whose line it trails."""


@dataclass(frozen=True)
class Workaround:
    """`// @workaround: <form>`, solver-file.md:139."""

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
    (line 1) is not among them."""


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
_REPRESENTATIVE_RE = re.compile(r"^(\S+)(?:\s+(\S+))?$")
_PLAIN_FIELD_RE = re.compile(r"^(\w+)(?:\s+([\w-]+))?:\s*(.*)$")
_MARKER_RE = re.compile(r"^---\s*(.*?)\s*---$")
_DASH = "—"

_RETIRED = frozenset({"invariant", "addition", "deviation"})
_NESTED_WORDS = frozenset({"approximated", "relaxed", "reassigned"})
_INPUT_MARK = "input"
"""`// @input` after a declaration: the lib's mark of a runner input, read
by no rule of the solver file."""


class _Open:
    """A line that nested and continuation lines under it join, while its
    comment block lasts."""

    def __init__(self, kind: str, line: int, parts: dict[str, object]) -> None:
        self.kind = kind
        self.line = line
        self.parts = parts
        self.relaxed: list[str] = []
        self.reassigned: list[str] = []
        self.witnesses: list[_Open] = []
        self.approximated: list[_Open] = []
        self.end = line


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


def _split(text: str) -> list[str]:
    """`text` split at the commas that stand outside parentheses."""
    out: list[str] = []
    depth, cur = 0, ""
    for ch in text:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [p.strip() for p in out]


def _marker(text: str, line: int) -> CaseMarker:
    """`<names>[: gloss]`: the names split at the commas that stand outside
    parentheses, each kept as written, for `names.denote` to read
    (solver-file.md:104-106)."""
    head, colon, gloss = text.partition(":")
    parts = [MarkerPart(name) for name in _split(head) if name]
    return CaseMarker(tuple(parts), gloss.strip() if colon else None, line)


def _constructor_at(program: Program, line: int) -> str | None:
    """The constructor whose branch comment holds `line`: in the solver's
    own ADT whose declaration spans it, the first constructor below it
    (solver-file.md:21-34)."""
    for t in program.types:
        if isinstance(t, AdtType) and t.span.file is None \
                and t.span.first <= line <= t.span.last:
            for c in t.constructors:
                if c.span.first > line:
                    return c.name
    return None


def _trailing_unit(program: Program, line: int) -> UnitId | DeclId | None:
    """The unit or declaration of the solver's own text on whose line a
    trailing comment stands: the one of the smallest span that holds the
    line."""
    found: list[tuple[int, UnitId | DeclId]] = []
    for u in program.units:
        if u.span is not None and u.span.file is None \
                and u.span.first <= line <= u.span.last:
            found.append((u.span.last - u.span.first, u.id))
    for m in program.macros:
        if m.span is not None and m.span.file is None \
                and m.span.first <= line <= m.span.last:
            found.append((m.span.last - m.span.first, m.id))
    decls: list[TypeDecl | RelationDecl | Component | Instance] = [
        *program.types, *program.relations, *program.components,
        *program.instances]
    for d in decls:
        if d.span is not None and d.span.file is None \
                and d.span.first <= line <= d.span.last:
            found.append((d.span.last - d.span.first, d.id))
    if not found:
        return None
    return min(found, key=lambda f: f[0])[1]


def read(program: Program) -> tuple[Annotations, tuple[Fault, ...]]:
    """The annotations the program's comments carry, positioned through
    each comment's `above` link and its indentation, and what could not be
    read.

    The comments read are the solver's own (`file` None) and the `//`
    ones: a line inside a block comment is no annotation. A comment block
    is a run of own-line comments on consecutive lines; the header is the
    block that starts on line 1 (solver-file.md:11-20). A nested line
    carries two spaces or more after `//` (solver-file.md:18-19); a line of
    two spaces or more that opens no directive continues the field or
    claim above it (solver-file.md:16)."""
    problems: list[Fault] = []

    def problem(kind: ProblemKind, line: int, read: str | Detail) -> None:
        problems.append(Fault(
            kind, InSolver(line),
            Quoted(read) if isinstance(read, str) else read))

    own = sorted((c for c in program.comments if c.file is None),
                 key=lambda c: (c.line, c.column))
    header_end = 0
    for c in own:
        if not c.own_line or c.line != header_end + 1 \
                or _content(c) is None:
            break
        header_end = c.line

    fields: list[_Open] = []
    reviews: list[_Open] = []
    representatives: list[Representative] = []
    claims: list[_Open] = []
    witnesses: list[_Open] = []
    derives: list[_Open] = []
    stores: list[_Open] = []
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
    for c in own:
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

    open_field: _Open | None = None     # a field or claim a continuation joins
    open_claim: _Open | None = None     # a claim an `@approximated:` joins
    open_approx: _Open | None = None    # an `@approximated:` a witness joins
    open_block: _Open | None = None     # a witness, derive or store line
    prev_line = -1

    def close() -> None:
        nonlocal open_field, open_claim, open_approx, open_block
        open_field = open_claim = open_approx = open_block = None

    for c in own:
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
                    sep = " " if open_field.parts["value"] else ""
                    open_field.parts["value"] = (
                        f"{open_field.parts['value']}{sep}{content}")
                    open_field.end = line
                continue
            if (m := _MARKER_RE.match(content)) and m[1].strip("-").strip():
                markers.append(_marker(m[1], line))
                close()
                continue
            plain = _PLAIN_FIELD_RE.match(content) if in_header else None
            close()
            if plain is not None and plain[1] == "review" and plain[2]:
                reviews.append(_Open("review", line, {
                    "kind": plain[2], "value": plain[3].strip()}))
                open_field = reviews[-1]
                continue
            if plain is not None and plain[2] is None:
                try:
                    word = HeaderWord(plain[1])
                except ValueError:
                    word = None
                if word is not None:
                    fields.append(_Open("field", line, {
                        "word": word, "value": plain[3].strip(),
                        "prefixed": False}))
                    open_field = fields[-1]
                    continue
            if in_header and content == HeaderWord.DRAFT:
                fields.append(_Open("field", line, {
                    "word": HeaderWord.DRAFT, "value": "",
                    "prefixed": False}))
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
            fields.append(_Open("field", line, {
                "word": HeaderWord.DRAFT, "value": "", "prefixed": True}))
            if tail.strip():
                problem(ProblemKind.OFF_FORM, line, content)
            continue
        if word in (HeaderWord.KEYWORDS, HeaderWord.REPRESENTATIVE,
                    HeaderWord.INPUT, HeaderWord.OUTPUT, HeaderWord.CONCEPT):
            close()
            if not tail.startswith(":"):
                problem(ProblemKind.OFF_FORM, line, content)
                continue
            fields.append(_Open("field", line, {
                "word": HeaderWord(word), "value": tail[1:].strip(),
                "prefixed": True}))
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
            claims.append(_Open("claim", line, {
                "kind": ClaimKind(word), "slug": m[1],
                "value": m[2].strip(),
                "constructor": None if in_header
                else _constructor_at(program, line)}))
            open_field = open_claim = claims[-1]
            continue
        if word == "claim":
            close()
            if not _REF_TAIL_RE.match(tail):
                problem(ProblemKind.OFF_FORM, line, content)
                continue
            claim_lines.append(ClaimLine(tuple(tail.split()), line, above))
            continue
        if word == "witness":
            nested = spaces >= 2
            m = _WITNESS_TAIL_RE.match(tail)
            plaus = None if m is None else _plausibility(m[2])
            if m is None or plaus is None:
                problem(ProblemKind.OFF_FORM, line, content)
                open_block = None
                continue
            block = _Open("witness", line, {
                "id": m[1], "plausibility": plaus, "verdict": _verdict(m[3]),
                "approximates": None,
                "constructor": None if in_header
                else _constructor_at(program, line)})
            if nested:
                if open_approx is None or open_claim is None:
                    problem(ProblemKind.OFF_FORM, line, content)
                    open_block = None
                    continue
                block.parts["approximates"] = open_claim.parts["slug"]
                open_approx.witnesses.append(block)
                open_field = None
            else:
                open_field = open_claim = open_approx = None
            witnesses.append(block)
            open_block = block
            continue
        if word in ("derive", "store"):
            close()
            m = (_DERIVE_TAIL_RE if word == "derive"
                 else _STORE_TAIL_RE).match(tail)
            plaus = None if m is None else _plausibility(m[2])
            if m is None or plaus is None:
                problem(ProblemKind.OFF_FORM, line, content)
                continue
            block = _Open(word, line, {
                "target": m[1], "plausibility": plaus,
                "verdict": _verdict(m[3]), "above": above})
            (derives if word == "derive" else stores).append(block)
            open_block = block
            continue
        if word == "approximated":
            if not tail.startswith(":") or open_claim is None \
                    or open_claim.parts["kind"] != ClaimKind.RULE:
                problem(ProblemKind.OFF_FORM, line, content)
                continue
            approx = _Open("approximated", line,
                           {"value": tail[1:].strip()})
            open_claim.approximated.append(approx)
            open_approx = open_field = approx
            continue
        if word in ("relaxed", "reassigned"):
            value = tail.strip()
            if not value or " " in value or open_block is None \
                    or (word == "reassigned"
                        and open_block.kind != "witness"):
                problem(ProblemKind.OFF_FORM, line, content)
                continue
            (open_block.relaxed if word == "relaxed"
             else open_block.reassigned).append(value)
            continue
        if word == "ignore":
            _ignore(tail, content, line, above, last_of_block[line],
                    ignores, problem)
            continue
        if word == "workaround":
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
        if f.parts["word"] != HeaderWord.REPRESENTATIVE:
            continue
        m = _REPRESENTATIVE_RE.match(str(f.parts["value"]))
        if m is None:
            problem(ProblemKind.OFF_FORM, f.line, str(f.parts["value"]))
        else:
            representatives.append(Representative(m[1], m[2], f.line))
    if len(representatives) > 1:
        problem(ProblemKind.UNDECIDED, representatives[1].line,
                Undecided(UndecidedForm.SECOND_REPRESENTATIVE, None))

    def witness_of(w: _Open) -> WitnessLine:
        p = w.parts
        return WitnessLine(
            str(p["id"]), _as(p["plausibility"], Plausibility),
            _verdict_of(p["verdict"]), w.line, tuple(w.relaxed),
            tuple(w.reassigned), _opt_str(p["approximates"]),
            _opt_str(p["constructor"]))

    annotations = Annotations(
        header=tuple(HeaderField(
            _as(f.parts["word"], HeaderWord), str(f.parts["value"]), f.line,
            f.end, bool(f.parts["prefixed"])) for f in fields),
        reviews=tuple(ReviewLine(str(r.parts["kind"]), str(r.parts["value"]),
                                 r.line) for r in reviews),
        representative=representatives[0] if representatives else None,
        claims=tuple(Claim(
            _as(c.parts["kind"], ClaimKind), str(c.parts["slug"]),
            str(c.parts["value"]), c.line,
            tuple(Approximated(str(a.parts["value"]), a.line,
                               tuple(witness_of(w) for w in a.witnesses))
                  for a in c.approximated),
            _opt_str(c.parts["constructor"])) for c in claims),
        witnesses=tuple(witness_of(w) for w in witnesses),
        derives=tuple(DeriveLine(
            str(d.parts["target"]),
            _as(d.parts["plausibility"], Plausibility),
            _verdict_of(d.parts["verdict"]), d.line,
            _opt_decl(d.parts["above"]), tuple(d.relaxed)) for d in derives),
        stores=tuple(StoreLine(
            _opt_str(s.parts["target"]),
            _as(s.parts["plausibility"], Plausibility),
            _verdict_of(s.parts["verdict"]), s.line,
            _opt_decl(s.parts["above"]), tuple(s.relaxed)) for s in stores),
        claim_lines=tuple(claim_lines),
        ignores=tuple(ignores),
        markers=tuple(markers),
        trailing=tuple(trailing),
        workarounds=tuple(workarounds),
        header_prose=tuple(header_prose),
    )
    return annotations, tuple(sorted(problems, key=_problem_line))


def _problem_line(p: Fault) -> int:
    return p.place.line if isinstance(p.place, InSolver) else 0


def _as[T](value: object, kind: type[T]) -> T:
    assert isinstance(value, kind)
    return value


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _opt_decl(value: object) -> DeclId | None:
    return value if isinstance(value, DeclId) else None


def _verdict_of(value: object) -> Verdict:
    assert isinstance(value, (VerdictWord, NamedVerdict))
    return value


def _ignore(tail: str, content: str, line: int, above: DeclId | None,
            last: bool, out: list[IgnoreLine],
            problem: Callable[[ProblemKind, int, str | Detail], None]
            ) -> None:
    """One `@ignore` line (solver-file.md:122, :134-136, :138). The lint
    form stands on the declaration directly under it, with no other
    directive between (solver-file.md:134); the derive and store forms
    stand on the declaration their comment block stands above."""
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
        out.append(IgnoreLine(IgnoreForm(first), None, relation,
                              name.strip() or None, reason, line, above))
        return
    try:
        category = Category(given)
    except ValueError:
        problem(ProblemKind.UNKNOWN_IGNORE_CATEGORY, line, Named(given))
        return
    out.append(IgnoreLine(IgnoreForm.LINT, category, relation, None, reason,
                          line, above if last else None))
