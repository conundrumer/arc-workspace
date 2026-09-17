"""The solver annotation grammar, read once for every tool.

A solver states its model in comment lines. The header carries the fields
and the claims; the body carries the references, the branch claims, and
the witness blocks. Every line the grammar parses starts with `@`, the
legacy plain fields aside.

`read` gives the whole annotation view of one source: the header fields,
the claims with their slugs and their approximations, the `@claim`
references with the line they stand above, the branch claims, and the
witness blocks with their nested lines. A line that opens an annotation
and then breaks its form lands in `malformed`, with the form it takes.

The lint, the witness check, the console, and the keyword count all read
this module, so a form is stated here once.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache

# --- the line forms ---------------------------------------------------

# Any comment line: the indent before the marker, the spaces after it, and
# the content.
COMMENT_RE = re.compile(r"^(\s*)//( *)(.*?)\s*$")
# A directive: the word after `@`, then the rest of the content.
DIRECTIVE_RE = re.compile(r"^@([\w-]+)(.*)$")
# A plain header field: `<word>: <value>`, or `review <kind>: <value>`.
PLAIN_FIELD_RE = re.compile(r"^(\w+)(?:\s+(\w+))?:\s*(.*)$")
# A slug: lowercase words joined by `-`.
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
CLAIM_TAIL_RE = re.compile(rf"^\s+({SLUG}):\s*(\S.*)$")
WITNESS_TAIL_RE = re.compile(rf"^\s+({SLUG}):\s*(\S+)\s+(\S+)$")
REF_TAIL_RE = re.compile(rf"^(\s+{SLUG})+$")
REPRESENTATIVE_TAIL_RE = re.compile(r"^(\S+)(?:\s+(\S+))?$")

# The header fields, in the order they stand. `draft` goes first, under the
# task id.
DRAFT = "draft"
PREFIXED_FIELDS = ("draft", "keywords", "representative")
LEGACY_FIELDS = ("concept", "input", "output", "review")
FIELDS = PREFIXED_FIELDS + LEGACY_FIELDS
# The kinds of claim, in the order the header states them.
CLAIM_KINDS = ("scene", "rule")
# The directives that stand nested under the line above them.
NESTED_WORDS = ("approximated", "relaxed", "reassigned")

# The forms, as a message names them.
FORMS = {
    "draft": "`// @draft`",
    "keywords": "`// @keywords: <keyword> <keyword>`",
    "representative": "`// @representative: <task id> [<Case>]`",
    "scene": "`// @scene <slug>: <text>`",
    "rule": "`// @rule <slug>: <text>`",
    "claim": "`// @claim <slug> [<slug> ...]`",
    "witness": "`// @witness <id>: <plausibility> <verdict>`",
    "approximated": "`//     @approximated: <text>`",
    "relaxed": "`//     @relaxed <slug>`",
    "reassigned": "`//     @reassigned <parameter>`",
}
SLUG_FORM = "a slug of lowercase words joined by `-`"

# A retired directive, with the form that took its place.
RETIRED = {
    "invariant": f"a claim about the input is {FORMS['scene']}",
    "addition": ("a branch states an addition as its own "
                 f"{FORMS['scene']} or {FORMS['rule']} line, with a new slug"),
    "deviation": f"a branch carries {FORMS['witness']}",
}
# The `@rule` line that stood above an instance, which `@claim` took over.
RETIRED_RULE_REF = (f"`@rule` above an instance is retired; the instance "
                    f"carries {FORMS['claim']}")


@dataclass
class Field:
    """One header field. `kind` carries the second word of a `review` line,
    `prefixed` says the line was written with `@`, and `end` is the last
    line of the value, which continues on lines of `//` and two spaces."""

    word: str
    kind: str | None
    value: str
    line: int
    prefixed: bool
    end: int = 0

    def __post_init__(self) -> None:
        self.end = self.end or self.line


@dataclass
class Claim:
    """One claim: a `@scene` line or a `@rule` line, with the text of the
    `@approximated:` line nested under it, if any."""

    kind: str
    slug: str
    text: str
    line: int
    approximated: str | None = None


@dataclass(frozen=True)
class Ref:
    """One `@claim` line, with the number of the first line under it that
    is not a comment — the line the reference stands above."""

    slugs: tuple[str, ...]
    line: int
    above: int


@dataclass
class Witness:
    """One `@witness` line, with the slugs its nested `@relaxed` lines name
    and the parameters its `@reassigned` lines name."""

    id: str
    plausibility: str
    verdict: str
    line: int = 0
    relaxed: list[str] = field(default_factory=list)
    reassigned: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Malformed:
    """A line that opens an annotation and breaks its form. `word` is the
    directive the line opens, and empty for a plain field."""

    line: int
    raw: str
    why: str
    word: str = ""


@dataclass
class Annotations:
    """The whole annotation view of one solver source."""

    fields: list[Field] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    branch_claims: list[Claim] = field(default_factory=list)
    refs: list[Ref] = field(default_factory=list)
    witnesses: list[Witness] = field(default_factory=list)
    malformed: list[Malformed] = field(default_factory=list)
    prose: list[int] = field(default_factory=list)
    """The header lines the grammar parses as nothing, the task id aside."""
    header_end: int = 0
    """The number of lines in the leading comment block."""

    def field_lines(self, word: str) -> list[Field]:
        return [f for f in self.fields if f.word == word]

    def slugs(self) -> set[str]:
        return {c.slug for c in self.claims}

    def keywords(self) -> list[str]:
        """The words of the first `@keywords:` line. A continuation line is
        not read."""
        lines = self.field_lines("keywords")
        return lines[0].value.split() if lines else []

    def representative(self) -> Field | None:
        lines = self.field_lines("representative")
        return lines[0] if lines else None

    def is_draft(self) -> bool:
        return bool(self.field_lines(DRAFT))


def nested_form(line: str) -> str:
    """The nested form of a directive line of a nested word that is not
    nested after `//`, and empty for any other line."""
    m = COMMENT_RE.match(line)
    if m is None or len(m[2]) >= 2:
        return ""
    d = DIRECTIVE_RE.match(m[3])
    if d is None or d[1] not in NESTED_WORDS:
        return ""
    return "//     " + m[3]


def _header_end(lines: list[str]) -> int:
    """The count of lines in the leading comment block."""
    n = 0
    while n < len(lines) and lines[n].strip().startswith("//"):
        n += 1
    return n


def _next_code_line(lines: list[str], at: int) -> int:
    """The number of the first line at or after `at` (1-based) that is not a
    comment and not blank."""
    n = at
    while n <= len(lines):
        text = lines[n - 1].strip()
        if text and not text.startswith("//"):
            return n
        n += 1
    return 0


@lru_cache(maxsize=8)
def read(source: str) -> Annotations:
    """The annotation view of a solver source."""
    lines = source.splitlines()
    out = Annotations(header_end=_header_end(lines))
    open_claim: Claim | None = None     # the claim an `@approximated:` takes
    open_witness: Witness | None = None  # the block a nested line joins
    open_field: Field | None = None      # the field a continuation joins

    def bad(lineno: int, why: str, word: str = "") -> None:
        out.malformed.append(
            Malformed(lineno, lines[lineno - 1].strip(), why, word))

    for lineno, raw in enumerate(lines, 1):
        m = COMMENT_RE.match(raw)
        if m is None:
            open_claim = open_witness = open_field = None
            continue
        spaces, content = m[2], m[3]
        shown = raw.strip()   # the line as a message names it
        in_header = lineno <= out.header_end
        d = DIRECTIVE_RE.match(content)
        if d is None:
            # Two spaces after `//` mark a continuation, so a field opens
            # only on a line of one.
            if content and len(spaces) >= 2:
                if open_field is not None:   # a continuation of the value
                    open_field.value = f"{open_field.value} {content}".strip()
                    open_field.end = lineno
                continue
            plain = PLAIN_FIELD_RE.match(content)
            if in_header and plain and plain[1] in FIELDS:
                if plain[1] in PREFIXED_FIELDS:
                    bad(lineno, f"`{plain[1]}` is retired as a plain field; "
                                f"the field is {FORMS[plain[1]]}")
                out.fields.append(Field(plain[1], plain[2], plain[3].strip(),
                                        lineno, False))
                open_field = out.fields[-1]
                continue
            if in_header and content == DRAFT:
                bad(lineno, "`draft` is retired as a plain field; the field "
                            f"is {FORMS['draft']}")
                out.fields.append(Field(DRAFT, None, "", lineno, False))
                continue
            if in_header and lineno > 1 and content:
                out.prose.append(lineno)
            open_claim = open_witness = open_field = None
            continue
        word, tail = d[1], d[2]
        open_field = None
        if fixed := nested_form(raw):
            bad(lineno, f"`{shown}` carries its indent before `//`; a nested "
                        f"line carries it after, as `{fixed}`"
                        if m[1] else
                        f"`{shown}` stands one space after `//`; the nested "
                        f"form is `{fixed}`", word)
        if word in RETIRED:
            bad(lineno, f"`@{word}` is retired; {RETIRED[word]}", word)
            open_claim = open_witness = None
            continue
        if word == DRAFT:
            out.fields.append(Field(DRAFT, None, "", lineno, True))
            if tail.strip():
                bad(lineno, f"`@draft` takes no value; the field is "
                            f"{FORMS['draft']}")
            continue
        if word in ("keywords", "representative"):
            value = tail.lstrip(":").strip() if tail.startswith(":") else ""
            if not tail.startswith(":"):
                bad(lineno, f"`@{word}` takes a value after a colon; the "
                            f"field is {FORMS[word]}")
            elif word == "representative" and not REPRESENTATIVE_TAIL_RE.match(value):
                bad(lineno, f"`{shown}` is off the `@representative` form, "
                            f"which is {FORMS['representative']}")
            out.fields.append(Field(word, None, value, lineno, True))
            open_field = out.fields[-1]
            continue
        if word in CLAIM_KINDS:
            c = CLAIM_TAIL_RE.match(tail)
            if c is None:
                if REF_TAIL_RE.match(tail) and word == "rule":
                    bad(lineno, RETIRED_RULE_REF)
                else:
                    bad(lineno, f"`{shown}` is off the `@{word}` form, "
                                f"which is {FORMS[word]}, the slug "
                                f"{SLUG_FORM}")
                open_claim = open_witness = None
                continue
            claim = Claim(word, c[1], c[2].strip(), lineno)
            (out.claims if in_header else out.branch_claims).append(claim)
            open_claim, open_witness = claim, None
            continue
        if word == "claim":
            if not REF_TAIL_RE.match(tail):
                bad(lineno, f"`{shown}` is off the `@claim` form, which is "
                            f"{FORMS['claim']}, each slug {SLUG_FORM}")
                open_claim = open_witness = None
                continue
            out.refs.append(Ref(tuple(tail.split()), lineno,
                                _next_code_line(lines, lineno + 1)))
            open_claim = open_witness = None
            continue
        if word == "witness":
            w = WITNESS_TAIL_RE.match(tail)
            if w is None:
                bad(lineno, f"`{shown}` is off the `@witness` form, which "
                            f"is {FORMS['witness']}, the id {SLUG_FORM}", "witness")
                open_claim = open_witness = None
                continue
            block = Witness(w[1], w[2], w[3], lineno)
            out.witnesses.append(block)
            open_claim, open_witness = None, block
            continue
        if word == "approximated":
            text = tail.lstrip(":").strip() if tail.startswith(":") else ""
            if not tail.startswith(":"):
                bad(lineno, f"`{shown}` is off the `@approximated` form, "
                            f"which is {FORMS['approximated']}")
            elif open_claim is None:
                bad(lineno, "`@approximated:` stands under a `@rule` line; "
                            "none stands above this one")
            elif open_claim.kind == "scene":
                bad(lineno, "`@approximated:` stands under a `@rule` line; "
                            f"the line above it is `@scene {open_claim.slug}`")
            else:
                open_claim.approximated = text
            continue
        if word in ("relaxed", "reassigned"):
            value = tail.strip()
            if not value or " " in value:
                bad(lineno, f"`{shown}` is off the `@{word}` form, which is "
                            f"{FORMS[word]}", word)
            elif open_witness is None:
                bad(lineno, f"`@{word}` stands under a `@witness` line; none "
                            "stands above this one", word)
            else:
                (open_witness.relaxed if word == "relaxed"
                 else open_witness.reassigned).append(value)
            continue
        if word in ("input", "allow", "workaround", "singleton-axis",
                    "construction"):
            continue  # marks of other grammars, read elsewhere
        bad(lineno, f"`@{word}` is no directive of the grammar; the "
                    "directives are "
                    + ", ".join(f"`@{w}`" for w in
                                (*PREFIXED_FIELDS, *CLAIM_KINDS, "claim",
                                 "witness", *NESTED_WORDS)))
        open_claim = open_witness = None
    return out


def witness_blocks(source: str) -> list[Witness]:
    """The solver's `@witness` lines, in the order they stand."""
    return read(source).witnesses


def merged_blocks(blocks: list[Witness]) -> list[Witness]:
    """The `@witness` lines of one id as one block. The nested lines stand
    under the first branch that carries the line, and a later branch carries
    the line alone, so the id's lines read together."""
    out: dict[str, Witness] = {}
    for b in blocks:
        held = out.get(b.id)
        if held is None:
            out[b.id] = Witness(b.id, b.plausibility, b.verdict, b.line,
                                list(b.relaxed), list(b.reassigned))
            continue
        held.relaxed += [s for s in b.relaxed if s not in held.relaxed]
        held.reassigned += [s for s in b.reassigned
                            if s not in held.reassigned]
    return list(out.values())


def header_keywords(source: str) -> list[str]:
    """The keywords of a solver's `@keywords:` line."""
    return read(source).keywords()


def resolved_claims(source: str) -> list[Claim]:
    """The claims a solver's references may name: its own header claims,
    or, when it states none and names a representative, that solver's."""
    ann = read(source)
    if ann.claims:
        return ann.claims
    rep = ann.representative()
    if rep is None or not rep.value:
        return []
    from dl.solve import solver_file
    try:
        return read(solver_file(rep.value.split()[0])[0].read_text()).claims
    except OSError:
        return []


def relaxable(claims: list[Claim]) -> set[str]:
    """The slugs a `@relaxed` line may name: every `@scene` slug, and the
    slug of any claim the header approximates."""
    return {c.slug for c in claims if c.kind == "scene" or c.approximated}
