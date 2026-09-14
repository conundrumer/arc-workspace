"""Lint .dl solver programs against the style doc under docs/wf-solver/.

`.comp` blocks are skipped wholesale — a proposal comp is lib code on its
way out of the solver, and its proposal entry is what makes it legitimate,
so a comp with no entry is a finding — except the comps whose rules are
model hypotheses, which lint as program. The public entry point is
`lint_program`; run_dl.py calls it after running each solver.
"""

import re
from functools import lru_cache

from dl.context import DOCS_DIR, lib_sources
from dl.dlparse import (
    SECTION_RE, Agg, Atom, Cmp, Comp, Decl, Define, Disj, Functor, Include,
    Init, Item, Lit, Neg, ParseError, Program, Rigid, Rule, TypeDecl, parse,
)
from dl.paths import SOLVERS_DIR
from dl.source import KEYWORDS_DOC, doc_keywords, header_keywords


def _lib_source() -> str:
    """The lib's text, its modules chained after the root, or empty when it
    is not there to read."""
    try:
        return "\n".join(text for _, text in lib_sources())
    except (OSError, ParseError):
        return ""


@lru_cache(maxsize=2)
def _lib_items(text: str) -> list[Item]:
    """The lib's parsed items, or none when it does not parse. Keyed on the
    text, so an edit to the lib reaches a process that already linted
    against it."""
    try:
        return parse(text).items
    except ParseError:
        return []


# The kind each lib top-level directive binds its name as.
LIB_KINDS = {
    TypeDecl: "type", Comp: "component", Decl: "relation",
    Functor: "functor", Define: "macro",
}


def _lib_names(text: str) -> dict[str, str]:
    """The lib's top-level names, each with its kind."""
    return {it.name: LIB_KINDS[type(it)] for it in _lib_items(text)
            if type(it) in LIB_KINDS}


# The zero box: a box, not an orientation.
ZERO_MACROS = frozenset({"ZERO"})

# The lib's macros, the zero box aside.
ORIENTATION_LITERALS = frozenset(
    name for name, kind in _lib_names(_lib_source()).items()
    if kind == "macro" and name not in ZERO_MACROS
)

ORIENTATION_LITERAL_RE = re.compile(
    r"\b(" + "|".join(sorted(ORIENTATION_LITERALS, key=len, reverse=True)) + r")\b"
    if ORIENTATION_LITERALS else r"(?!)"
)
COMMENT_RE = re.compile(r"//.*$")
# A `.plan` directive and the join order it carries, to end of line.
PLAN_RE = re.compile(r"(?<![\w.])\.plan\b.*$")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", flags=re.DOTALL)
NUMERIC_LITERAL_RE = re.compile(r"(?<![A-Za-z_0-9.])\d+(?![A-Za-z_0-9.])")
UNIT_MARKER = "@unit"


def exempt_literal(lit: str, unit: bool) -> bool:
    """A 0 anywhere; a 1 in a unit-marked rule."""
    return lit == "0" or (unit and lit == "1")
RANGE_RE = re.compile(r"\brange\s*\(")

# Souffle keywords: the complete bare-word keyword set of the souffle 2.5
# scanner (src/parser/scanner.ll), each confirmed against the binary to fail
# in every name position — relation, attribute, instance, comp, type,
# functor, record field, and variable. The directive words (`decl`, `type`,
# `init`, `comp`, `plan`, ...) are reserved only with their leading dot, so
# they are usable as names and are not here. Neither are the predefined type
# names (`number`, `symbol`, `float`, `unsigned`): they lex as identifiers
# and fail only as `.type` names, where souffle's own message is clear.
# The category a colliding name is reported under.
RESERVED_CAT = "reserved name"

RESERVED_WORDS = frozenset({
    # aggregators
    "count", "sum", "min", "max", "mean",
    # string and number functors
    "cat", "ord", "range", "strlen", "substr", "match", "contains", "autoinc",
    "to_float", "to_number", "to_string", "to_unsigned",
    # word operators
    "band", "bor", "bxor", "bnot", "bshl", "bshr", "bshru",
    "land", "lor", "lxor", "lnot",
    # relation qualifiers
    "inline", "no_inline", "magic", "no_magic", "overridable",
    "input", "output", "printsize", "eqrel", "brie", "btree", "btree_delete",
    # constants, casts, and the rest
    "as", "nil", "true", "false", "stateful", "debug_delta",
    "recursive_iteration_cnt", "__FILE__", "__LINE__", "__INCL__",
})

# A name-binding directive and the name it binds.
DECLARED_NAME_RE = re.compile(
    r"(?<![\w.])\.(decl|init|type|comp|functor)\s+([A-Za-z_]\w*)"
)
# The category a type argument colliding with a component-internal type
# name is reported under.
SHADOWED_TYPE_CAT = "shadowed type"
# The category a solver name colliding with a lib top-level name is
# reported under.
LIB_NAME_CAT = "lib name"
# A solver reads a `_`-prefixed lib name, which is private to the lib.
LIB_INTERNAL_CAT = "lib internal"
# The comps a solver holds as its own. Any other is a proposal comp,
# legitimate only with its entry under docs/wf-solver/proposals/.
STOCK_COMPS = ("Params", "Determine", "Parse")
PROPOSALS_DIR = DOCS_DIR / "proposals"
# The category a proposal comp with no entry is reported under.
NO_ENTRY_CAT = "comp without entry"
# The category a Parse comp that no Determine comp reads is reported
# under.
LONE_PARSE_CAT = "parse unshared with determine"
# The header line naming the family representative, with the case name it
# may carry: `// representative: <task_id>` or
# `// representative: <task_id> <Case>`.
FAMILY_RE = re.compile(r"^//\s*representative:\s*(\S+)(?:\s+(\S+))?\s*$")
# The same line, matched before its form is read.
REP_LINE_RE = re.compile(r"^//\s*representative:")
# The category a sibling header line the grammar or the representative
# rejects is reported under.
FAMILY_CASE_CAT = "family case"
# The header: the leading comment block, the task id, then `draft`, then
# the fields in this order. A value continues on a line of `//` and two
# spaces. `review` repeats; the others stand once.
HEADER_CAT = "header"

# A header keyword the doc does not list. A session adds the keyword it needs
# and proposes it in its review, so this is a hint, not a finding.
KEYWORD_CAT = "keyword"
HEADER_FIELDS = ("representative", "keywords", "input", "output", "review")
HEADER_RANK = {"representative": 1, "keywords": 1, "input": 2, "output": 3,
               "review": 4}
FIELD_RE = re.compile(r"^//\s*(\w+)(?:\s+(\w+))?:(?:\s|$)")
CONTINUATION_RE = re.compile(r"^//  \S")
DRAFT_LINE = "// draft"
# A gloss stands above every ADT that `Choice` is or holds as a field type,
# and above each of its constructors, one constructor per line.
GLOSS_CAT = "gloss"
FIELD_TYPE_RE = re.compile(r":\s*(\w+)")
BRANCH_LINE_RE = r"^\s*(?:\|\s*)?{name}\s*\{{"
# The build adds the lib include; a solver holds none.
INCLUDE_CAT = "include"
# RIGID chart names exist only in the macro expansion; any appearance in
# solver source reads a stored pose the model claims unobservable.
RIGID_CHART_RE = re.compile(r"\b_rigid_\w+")

# Comparison-ops detector (<, <=, >, >=). Body comparisons are usually
# legitimate, so this is opt-in. The comparisons that are not legitimate
# are the ones over a type that carries no order, which the rewrite
# lint's `typed-order` rule reads off the column types.
LINT_COMPARISON = False


def _strip_block_comments(source: str) -> str:
    """Blank out /* ... */ while preserving line count for accurate lineno."""
    return BLOCK_COMMENT_RE.sub(
        lambda m: re.sub(r"[^\n]", " ", m.group(0)), source
    )


def _value_context(line: str, op_start: int, op_end: int) -> bool:
    """True iff a value-shaped token sits on both sides of [op_start, op_end).

    Value-shaped means: ends in alnum/`_`/`)`/`]` on the left, starts with
    alnum/`_`/`(`/`[`/unary-`-` on the right (whitespace allowed). So `:-`
    rule separators, `../` paths, and `=` adjacency don't qualify.
    """
    j = op_start - 1
    while j >= 0 and line[j].isspace():
        j -= 1
    if j < 0:
        return False
    lc = line[j]
    if not (lc.isalnum() or lc == "_" or lc in ")]"):
        return False
    k = op_end
    while k < len(line) and line[k].isspace():
        k += 1
    if k >= len(line):
        return False
    rc = line[k]
    return rc.isalnum() or rc == "_" or rc in "([-"


def _is_unary_minus(line: str, i: int) -> bool:
    """True iff the '-' at i negates a value (unary), not the rule turnstile.

    Reached only when the left side isn't value-shaped (binary is handled by
    `_value_context`). Excludes the `:-` turnstile and requires a value token on
    the right, so `-M` / `-W` / `-5` flag while `:- in(P)` does not.
    """
    j = i - 1
    while j >= 0 and line[j].isspace():
        j -= 1
    if j >= 0 and line[j] == ":":  # rule turnstile ':-'
        return False
    k = i + 1
    while k < len(line) and line[k].isspace():
        k += 1
    if k >= len(line):
        return False
    rc = line[k]
    return rc.isalnum() or rc == "_" or rc in "(["


def _find_arithmetic(line: str) -> list[tuple[int, str]]:
    """Find arithmetic ops with value operands: binary +, -, *, /, % and unary -."""
    out: list[tuple[int, str]] = []
    for m in re.finditer(r"[+\-*/%]", line):
        i = m.start()
        if _value_context(line, i, i + 1):
            out.append((i, line[i]))
        elif line[i] == "-" and _is_unary_minus(line, i):
            out.append((i, line[i]))
    return out


def _find_comparison(line: str) -> list[tuple[int, str]]:
    """Find ordering comparison ops (<, <=, >, >=) with value-shaped operands.

    Skips Souffle subtype `<:` and lattice arrow `<=>`.
    """
    out: list[tuple[int, str]] = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == "<":
            if i + 1 < n and line[i + 1] == ":":
                i += 2
                continue
            if i + 2 < n and line[i + 1] == "=" and line[i + 2] == ">":
                i += 3
                continue
            if i + 1 < n and line[i + 1] == "=":
                op, end = "<=", i + 2
            else:
                op, end = "<", i + 1
            if _value_context(line, i, end):
                out.append((i, op))
            i = end
        elif c == ">":
            if i + 1 < n and line[i + 1] == "=":
                op, end = ">=", i + 2
            else:
                op, end = ">", i + 1
            if _value_context(line, i, end):
                out.append((i, op))
            i = end
        else:
            i += 1
    return out


def _reserved_names(raw_lines: list[str]) -> list[tuple[str, int, str, str]]:
    """Declared names that collide with a Souffle keyword.

    Souffle rejects the whole file for one of these, and its message names
    the token class it read rather than the collision, so this finding
    stands in for it.
    """
    findings: list[tuple[str, int, str, str]] = []
    for lineno, raw in enumerate(raw_lines, 1):
        for m in DECLARED_NAME_RE.finditer(COMMENT_RE.sub("", raw)):
            name = m.group(2)
            if name not in RESERVED_WORDS:
                continue
            findings.append((
                RESERVED_CAT, lineno,
                f"`{name}` is a Souffle reserved word and cannot name "
                f"anything; rename it",
                raw.rstrip(),
            ))
    return findings


# A record-field or attribute name in raw right-hand-side text.
FIELD_NAME_RE = re.compile(r"([A-Za-z_]\w*)\s*:")

# The category a solver type outside the sanctioned kinds is reported
# under. Sanctioned (style doc, Types and alt-outputs): `Choice` and the
# types it reaches, a record filling a comp type param at an `.init`, and
# `TiebreakResolution` with the types it reaches.
BANNED_TYPE_CAT = "banned type"

TYPE_TOKEN_RE = re.compile(r"[A-Za-z_]\w*")

RECORD_RHS_RE = re.compile(r"=\s*\[")


def _reserved_inner_names(
    items: list[Item], raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """Keyword collisions in the positions only the parse can see:
    attributes, record fields and ADT branches, component parameters, and
    type arguments. Souffle's caret lands past the word in some of them,
    so the finding names it."""
    findings: list[tuple[str, int, str, str]] = []

    def take(names: list[str], line: int) -> None:
        for name in names:
            if name not in RESERVED_WORDS:
                continue
            findings.append((
                RESERVED_CAT, line,
                f"`{name}` is a Souffle reserved word and cannot name "
                f"anything; rename it",
                raw_lines[line - 1].rstrip(),
            ))

    def walk(items: list[Item]) -> None:
        for it in items:
            if isinstance(it, Decl):
                take([f.name for f in it.fields], it.line)
            elif isinstance(it, TypeDecl):
                take(it.branches + FIELD_NAME_RE.findall(it.rhs), it.line)
            elif isinstance(it, Init):
                take(it.targs, it.line)
            elif isinstance(it, Comp):
                take(it.params + it.base_targs, it.line)
                walk(it.items)
            elif isinstance(it, Rigid):
                walk(it.items)

    walk(items)
    return findings


def _comp_table(items: list[Item]) -> dict[str, Comp]:
    """Every component in an item tree, nested ones included, by name."""
    table: dict[str, Comp] = {}
    for it in items:
        if isinstance(it, Comp):
            table[it.name] = it
            table |= _comp_table(it.items)
    return table


def _inits(items: list[Item]) -> list[Init]:
    """Every `.init` in an item tree, those inside components included."""
    out: list[Init] = []
    for it in items:
        if isinstance(it, Init):
            out.append(it)
        elif isinstance(it, Comp):
            out.extend(_inits(it.items))
    return out


def _inner_types(name: str, table: dict[str, Comp],
                 seen: frozenset[str] = frozenset()) -> set[str]:
    """Type names visible inside a component: its own, its base's, and
    those of the components it instantiates."""
    comp = table.get(name)
    if comp is None or name in seen:
        return set()
    seen = seen | {name}
    names: set[str] = set()
    for it in comp.items:
        if isinstance(it, TypeDecl):
            names.add(it.name)
        elif isinstance(it, Init):
            names |= _inner_types(it.comp, table, seen)
    if comp.base is not None:
        names |= _inner_types(comp.base, table, seen)
    return names


def _shadowed_types(
    items: list[Item], raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """Type arguments that collide with a type name inside the component
    they are passed to.

    Souffle binds the argument and the component-internal type to the same
    name, so the instance's relations take the wrong key type. Its message
    names a rule variable it could not type rather than the collision, so
    this finding stands in for it.
    """
    table = _comp_table(_lib_items(_lib_source())) | _comp_table(items)
    findings: list[tuple[str, int, str, str]] = []
    for init in _inits(items):
        inner = _inner_types(init.comp, table)
        for targ in init.targs:
            if targ not in inner:
                continue
            findings.append((
                SHADOWED_TYPE_CAT, init.line,
                f"`{targ}` also names a type inside `{init.comp}`, so the "
                f"instance takes that name for its own type; rename it",
                raw_lines[init.line - 1].rstrip(),
            ))
    return findings


def _lib_named(
    items: list[Item], raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """Solver declarations that take a lib top-level name.

    Souffle keeps top-level types, components, instances, and relations in
    one namespace and functors in another; a declaration inside a
    component is scoped to its instance; a macro is substituted wherever
    its name appears. Its message points at the lib's line for some of
    these, so this finding stands in for it.
    """
    lib = _lib_names(_lib_source())
    findings: list[tuple[str, int, str, str]] = []

    def walk(items: list[Item], top: bool) -> None:
        for it in items:
            if isinstance(it, Comp):
                walk(it.items, False)
            if not isinstance(it, (TypeDecl, Decl, Comp, Init, Functor)):
                continue
            name = it.inst if isinstance(it, Init) else it.name
            kind = lib.get(name)
            if kind is None:
                continue
            if kind != "macro" and (
                not top or (kind == "functor") != isinstance(it, Functor)
            ):
                continue
            findings.append((
                LIB_NAME_CAT, it.line,
                f"`{name}` is a lib {kind}; rename it",
                raw_lines[it.line - 1].rstrip(),
            ))

    walk(items, True)
    return findings


def _atoms(lits: list[Lit]):
    """Every atom a body reads: positive, negated, in aggregate bodies,
    and in disjunction branches."""
    for lit in lits:
        if isinstance(lit, Atom):
            yield lit
        elif isinstance(lit, Neg):
            yield lit.atom
        elif isinstance(lit, Cmp):
            for side in (lit.lhs, lit.rhs):
                if isinstance(side, Agg):
                    yield from _atoms(side.body)
        elif isinstance(lit, Disj):
            for branch in lit.branches:
                yield from _atoms(list(branch))


def _lib_internal(
    items: list[Item], raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """Reads of a `_`-prefixed lib name: a relation or instance inside a
    lib comp, or a lib comp itself. Such a name is private to the lib, and
    a unit's public readouts are its interface."""
    lib_comps = _comp_table(_lib_items(_lib_source()))
    # Each instance's comp: the solver's own, and the ones inside lib comps.
    inst_comp = {init.inst: init.comp for init in _inits(items)}
    for comp in lib_comps.values():
        inst_comp.update((it.inst, it.comp) for it in comp.items if isinstance(it, Init))
    findings: list[tuple[str, int, str, str]] = []

    def take(atom: Atom) -> None:
        segs = (atom.qual.split(".") if atom.qual else []) + [atom.name]
        for prev, seg in zip(segs, segs[1:]):
            comp = inst_comp.get(prev)
            if seg.startswith("_") and comp in lib_comps:
                findings.append((
                    LIB_INTERNAL_CAT, atom.line,
                    f"`{seg}` is internal to {comp}; read a public readout",
                    raw_lines[atom.line - 1].rstrip(),
                ))
                return

    def walk(items: list[Item]) -> None:
        for it in items:
            if isinstance(it, Comp):
                walk(it.items)
            elif isinstance(it, Init):
                if it.comp.startswith("_") and it.comp in lib_comps:
                    findings.append((
                        LIB_INTERNAL_CAT, it.line,
                        f"`{it.comp}` is internal to the lib; instantiate a public unit",
                        raw_lines[it.line - 1].rstrip(),
                    ))
            elif isinstance(it, Rule):
                take(it.head)
                for atom in _atoms(it.body or []):
                    take(atom)

    walk(items)
    return findings


def _comps_without_entry(
    items: list[Item], raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """Proposal comps with no entry file of their name."""
    findings: list[tuple[str, int, str, str]] = []
    for it in items:
        if not isinstance(it, Comp) or it.name in STOCK_COMPS:
            continue
        if (PROPOSALS_DIR / f"{it.name}.md").is_file():
            continue
        findings.append((
            NO_ENTRY_CAT, it.line,
            f"`{it.name}` is a proposal comp with no entry "
            f"docs/wf-solver/proposals/{it.name}.md; write the entry, or "
            f"fold the comp into the program",
            raw_lines[it.line - 1].rstrip(),
        ))
    return findings


def _lone_parse(
    program: Program, raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """A Parse comp that no Determine comp reads.

    Parse holds a derivation that the program and the Determine comp share.
    A solver with no Determine comp, or with one that does not read the
    Parse comp, shares nothing with it.
    """
    comps = program.comps()
    comp = comps.get("Parse")
    if comp is None:
        return []
    determine = comps.get("Determine")
    if determine is not None and _reads_parse(program, determine, raw_lines):
        return []
    return [(
        LONE_PARSE_CAT, comp.line,
        "the Determine comp does not read this parse, or the solver has "
        "no Determine comp, so the parse is shared with nothing; "
        "read it in Determine, or fold it into the program",
        raw_lines[comp.line - 1].rstrip(),
    )]


def _reads_parse(
    program: Program, determine: Comp, raw_lines: list[str],
) -> bool:
    """The Determine comp reads the Parse comp: it holds its own Parse
    instance, or its lines name a top-level one."""
    if any(isinstance(it, Init) and it.comp == "Parse"
           for it in determine.items):
        return True
    span = raw_lines[determine.line - 1:determine.end_line]
    for it in program.items:
        if not isinstance(it, Init) or it.comp != "Parse":
            continue
        if any(f"{it.inst}." in line for line in span):
            return True
    return False


def _rep_items(task_id: str) -> list[Item] | None:
    """The representative solver's parsed items, or None when its file is
    not there to read or does not parse."""
    try:
        text = (SOLVERS_DIR / f"{task_id}.dl").read_text()
    except OSError:
        return None
    try:
        return parse(text).items
    except ParseError:
        return None


def _family_case(raw_lines: list[str]) -> list[tuple[str, int, str, str]]:
    """A `// representative:` line the sibling header grammar rejects, or
    whose case name the representative does not hold.

    The case names one case of the representative's `Choice`, so the name
    stands among that type's constructors. A record-typed `Choice` has no
    constructors, so no name stands. A representative there is no parse of
    says nothing about the name, and the line passes.
    """
    findings: list[tuple[str, int, str, str]] = []
    for lineno, raw in enumerate(raw_lines, 1):
        m = FAMILY_RE.match(raw.strip())
        if m is None:
            if REP_LINE_RE.match(raw.strip()):
                why = ("a sibling header is `// representative: <task_id>`, "
                       "with at most one case name after the id")
                findings.append((FAMILY_CASE_CAT, lineno, why, raw.rstrip()))
            continue
        if m.group(2) is None:
            continue
        task_id, case = m.group(1), m.group(2)
        items = _rep_items(task_id)
        if items is None:
            continue
        choices = [it for it in items
                   if isinstance(it, TypeDecl) and it.name == "Choice"]
        if any(case in it.branches for it in choices):
            continue
        if choices and not any(it.branches for it in choices):
            why = f"`{task_id}`'s `Choice` is a record; a sibling of it names no case"
        else:
            named = (f"`{case}` is no case of `{task_id}`'s `Choice`" if choices
                     else f"`{task_id}` declares no `Choice`")
            why = f"{named}; name a case the representative holds"
        findings.append((FAMILY_CASE_CAT, lineno, why, raw.rstrip()))
    return findings


@lru_cache(maxsize=1)
def _known_keywords() -> frozenset[str]:
    """Every keyword keywords.md lists, read once per process. Empty when
    the doc is not there to read, which holds the check back."""
    try:
        text = KEYWORDS_DOC.read_text()
    except OSError:
        return frozenset()
    return frozenset(w for words in doc_keywords(text).values() for w in words)


def _header(raw_lines: list[str]) -> list[tuple[str, int, str, str]]:
    """The header lines that break the grammar, and the fields it lacks."""
    findings: list[tuple[str, int, str, str]] = []

    def flag(lineno: int, why: str) -> None:
        findings.append((HEADER_CAT, lineno, why, raw_lines[lineno - 1].rstrip()))

    if not raw_lines or not raw_lines[0].strip().startswith("//"):
        return [(HEADER_CAT, 1, "the file opens with `// <task_id>`",
                 raw_lines[0].rstrip() if raw_lines else "")]
    last = 0          # rank of the last header line placed
    keywords_line = 0  # where the `keywords:` value stands, for its words
    draft = prose = False
    seen: set[str] = set()
    for lineno, raw in enumerate(raw_lines[1:], 2):
        line = raw.strip()
        if not line.startswith("//"):
            break
        if line == DRAFT_LINE:
            if last:
                flag(lineno, "`draft` goes under the task id")
            draft = True
            continue
        if CONTINUATION_RE.match(line):
            if not last:
                flag(lineno, "a continuation line follows a field")
            continue
        if m := FIELD_RE.match(line):
            word, kind = m.group(1), m.group(2)
            if word not in HEADER_FIELDS or (kind and word != "review"):
                flag(lineno, f"`{word}:` is no header field; the fields are "
                     + ", ".join(HEADER_FIELDS))
                continue
            rank = HEADER_RANK[word]
            if word == "keywords" and not keywords_line:
                keywords_line = lineno
            if word == "review":
                if not kind:
                    flag(lineno, "`review` takes a kind: `review <kind>:`")
            elif word in seen:
                flag(lineno, f"`{word}:` stands once")
            elif "representative" in seen or (word == "representative" and seen):
                flag(lineno, "a sibling carries `representative:` in place of "
                     "`keywords:`, `input:`, and `output:`")
            if rank < last:
                flag(lineno, "header fields go in the order "
                     + ", ".join(HEADER_FIELDS))
            seen.add(word)
            last = max(last, rank)
            continue
        if not prose:
            flag(lineno, "no prose in the header; a remark about a case goes "
                 "at its constructor, and a remark about a rule at the rule")
        prose = True
    known = _known_keywords()
    if keywords_line and known:
        for word in header_keywords("\n".join(raw_lines)):
            if word not in known:
                findings.append((KEYWORD_CAT, keywords_line,
                                 f"`{word}` is not in keywords.md; propose it in the review",
                                 raw_lines[keywords_line - 1].rstrip()))
    if not seen & {"keywords", "representative"}:
        flag(1, "the header carries `keywords:` or `representative:`")
    elif "keywords" in seen and "output" not in seen:
        flag(1, "the header carries `output:`")
    return findings


def _gloss_above(raw_lines: list[str], lineno: int) -> bool:
    """A gloss comment stands on the line above `lineno`."""
    if lineno < 2:
        return False
    above = raw_lines[lineno - 2].strip()
    return above.startswith("//") and not SECTION_RE.match(above)


def _glosses(
    items: list[Item], raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """The ADTs of `Choice` — the type itself, or the field types of a
    record — that lack a gloss above the type or above a constructor."""
    types = {it.name: it for it in items if isinstance(it, TypeDecl)}
    choice = types.get("Choice")
    if choice is None:
        return []
    if choice.branches:
        targets = [choice]
    else:
        targets = [types[n] for n in FIELD_TYPE_RE.findall(choice.rhs)
                   if n in types and types[n].branches]
    findings: list[tuple[str, int, str, str]] = []
    for td in targets:
        if not _gloss_above(raw_lines, td.line):
            findings.append((GLOSS_CAT, td.line,
                             f"a gloss stands above `{td.name}`: what the choice is",
                             raw_lines[td.line - 1].rstrip()))
        used: set[int] = set()
        for name in td.branches:
            pat = re.compile(BRANCH_LINE_RE.format(name=re.escape(name)))
            at = next((n for n in range(td.line, len(raw_lines) + 1)
                       if n not in used and pat.match(raw_lines[n - 1])), None)
            if at is None:
                findings.append((GLOSS_CAT, td.line,
                                 f"`{name}` opens its own line, under its gloss",
                                 raw_lines[td.line - 1].rstrip()))
                continue
            used.add(at)
            if not _gloss_above(raw_lines, at):
                findings.append((GLOSS_CAT, at, f"a gloss stands above `{name}`",
                                 raw_lines[at - 1].rstrip()))
    return findings


def _includes(
    items: list[Item], raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    return [(INCLUDE_CAT, it.line, "the build adds the lib; drop the include",
             raw_lines[it.line - 1].rstrip())
            for it in items if isinstance(it, Include)]


def _type_scopes(
    items: list[Item], linted: bool = True,
) -> list[tuple[TypeDecl, bool]]:
    """Every solver TypeDecl, with whether it sits in linted scope: the top
    level and the Determine/Parse comps. Other comps are skipped like the rest of
    their lines."""
    out: list[tuple[TypeDecl, bool]] = []
    for it in items:
        if isinstance(it, TypeDecl):
            out.append((it, linted))
        elif isinstance(it, Comp):
            out.extend(
                _type_scopes(it.items, linted and it.name in ("Determine", "Parse"))
            )
        elif isinstance(it, Rigid):
            out.extend(_type_scopes(it.items, linted))
    return out


def _type_refs(td: TypeDecl, declared: set[str]) -> set[str]:
    """Solver type names a declaration's right-hand side references —
    constructor-field types, record-field types, factors, union members —
    its own branch and field names excluded."""
    tokens = set(TYPE_TOKEN_RE.findall(td.rhs))
    fields = set(FIELD_NAME_RE.findall(td.rhs))
    return (tokens - set(td.branches) - fields - {td.name}) & declared


def _banned_types(
    items: list[Item], raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """Solver types outside the sanctioned kinds.

    The closure walk seeds on `Choice` and `TiebreakResolution` and follows
    references through solver-declared types; the param-fill sanction takes
    the record types some `.init` passes as a type argument. Names resolve
    in file scope only, and a declaration in a skipped comp can sanction
    but is never flagged."""
    scoped = _type_scopes(items)
    by_name: dict[str, list[TypeDecl]] = {}
    for td, _ in scoped:
        by_name.setdefault(td.name, []).append(td)
    declared = set(by_name)

    sanctioned: set[str] = set()
    stack = [n for n in ("Choice", "TiebreakResolution") if n in declared]
    while stack:
        name = stack.pop()
        if name in sanctioned:
            continue
        sanctioned.add(name)
        for td in by_name[name]:
            stack.extend(_type_refs(td, declared) - sanctioned)

    records = {
        name for name, tds in by_name.items()
        if any(RECORD_RHS_RE.match(td.rhs.strip()) for td in tds)
    }
    filled = {targ for init in _inits(items) for targ in init.targs}
    sanctioned |= records & filled

    findings: list[tuple[str, int, str, str]] = []
    for td, linted in scoped:
        if not linted or td.name in sanctioned:
            continue
        findings.append((
            BANNED_TYPE_CAT, td.line,
            f"`{td.name}` is outside the sanctioned type kinds — `Choice`'s "
            f"closure, or a record filling a comp type param; re-encode it "
            f"or propose",
            raw_lines[td.line - 1].rstrip(),
        ))
    return findings


def lint_program(source: str) -> list[tuple[str, int, str, str]]:
    """Flag program code that violates the style doc.

    Returns (category, lineno, match, raw_line) per finding. The category
    names what was flagged. Skips // and /* */ comments and the `.comp`
    blocks that hold no program code, whose spans come from the parsed source.
    The reserved-name check reads every line, comps included, since Souffle
    rejects such a name anywhere; the parse extends it to the inner name
    positions. A source that does not parse returns the line-level findings
    alone; the rewrite lint reports the parse error.
    """
    src = _strip_block_comments(source)
    raw_lines = src.splitlines()
    findings: list[tuple[str, int, str, str]] = _reserved_names(raw_lines)
    findings.extend(_family_case(raw_lines))
    findings.extend(_header(raw_lines))

    try:
        program = parse(source)
    except ParseError:
        return findings

    def code(lineno: int) -> str:
        line = COMMENT_RE.sub("", raw_lines[lineno - 1])
        # A `.plan` join order names body positions, not data.
        line = PLAN_RE.sub("", line)
        # Souffle's choice-domain qualifier is not arithmetic.
        return line.replace("choice-domain", " " * len("choice-domain"))

    skip: set[int] = set()
    for comp in program.comps().values():
        if comp.name in ("Determine", "Parse"):
            skip.add(comp.line)
        else:
            skip.update(range(comp.line, comp.end_line + 1))

    for lineno in range(1, len(raw_lines) + 1):
        for m in RIGID_CHART_RE.finditer(code(lineno)):
            findings.append(("rigid chart", lineno, m.group(0),
                             raw_lines[lineno - 1].rstrip()))
        if lineno in skip:
            continue
        raw_line = raw_lines[lineno - 1]
        line = code(lineno)
        for m in ORIENTATION_LITERAL_RE.finditer(line):
            findings.append(("orientation literal", lineno, m.group(1), raw_line.rstrip()))
        for m in NUMERIC_LITERAL_RE.finditer(line):
            if m.group(0) != "0":
                findings.append(("nonzero literal", lineno, m.group(0), raw_line.rstrip()))
        for _, op in _find_arithmetic(line):
            findings.append(("arithmetic", lineno, op, raw_line.rstrip()))
        for _ in RANGE_RE.finditer(line):
            findings.append(("range", lineno, "range", raw_line.rstrip()))
        if LINT_COMPARISON:
            for _, op in _find_comparison(line):
                findings.append(("comparison", lineno, op, raw_line.rstrip()))

    findings.extend(_reserved_inner_names(program.items, raw_lines))
    findings.extend(_shadowed_types(program.items, raw_lines))
    findings.extend(_lib_named(program.items, raw_lines))
    findings.extend(_lib_internal(program.items, raw_lines))
    findings.extend(_comps_without_entry(program.items, raw_lines))
    findings.extend(_lone_parse(program, raw_lines))
    findings.extend(_banned_types(program.items, raw_lines))
    findings.extend(_glosses(program.items, raw_lines))
    findings.extend(_includes(program.items, raw_lines))
    findings.extend(_params_data(program.comps().get("Params"), raw_lines, code))
    findings.sort(key=lambda f: (f[1], f[0]))
    return findings


def _params_data(
    comp: Comp | None, raw_lines: list[str], code,
) -> list[tuple[str, int, str, str]]:
    """Params-rule literals that `exempt_literal` does not exempt."""
    findings: list[tuple[str, int, str, str]] = []
    if comp is None:
        return findings
    for it in comp.items:
        if not isinstance(it, Rule) or it.body is None:
            continue
        span = range(it.line, it.end_line + 1)
        unit = any(UNIT_MARKER in raw_lines[ln - 1] for ln in span)
        for ln in span:
            for m in NUMERIC_LITERAL_RE.finditer(code(ln)):
                if exempt_literal(m.group(0), unit):
                    continue
                findings.append(
                    ("params data", ln, m.group(0), raw_lines[ln - 1].rstrip())
                )
    return findings
