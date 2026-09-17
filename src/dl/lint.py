"""Lint .dl solver programs against the style doc under docs/wf-solver/.

`.comp` blocks are skipped wholesale — a proposal comp is lib code on its
way out of the solver, and its proposal entry is what makes it legitimate,
so a comp with no entry is a finding — except the comps whose rules are
model hypotheses, which lint as program. The public entry point is
`lint_program`; run_dl.py calls it after running each solver.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from dl.annotations import FORMS, Annotations, read, resolved_claims
from dl.context import DOCS_DIR, lib_sources
from dl.dlparse import (
    SECTION_RE,
    Agg,
    Atom,
    Cmp,
    Comp,
    Decl,
    Define,
    Disj,
    Functor,
    Include,
    Init,
    Item,
    Lit,
    Neg,
    ParseError,
    Program,
    Rigid,
    Rule,
    TypeDecl,
    marker_names,
    parse,
)
from dl.features_run import NO_CHOICE, case_label
from dl.solve import solver_file
from dl.source import KEYWORDS_DOC, doc_keywords


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
SINGLETON_AXIS_MARKER = "@singleton-axis"


def exempt_literal(lit: str, singleton_axis: bool) -> bool:
    """A 0 anywhere; a 1 in a rule marked `@singleton-axis`."""
    return lit == "0" or (singleton_axis and lit == "1")
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
# The category a sibling header line the grammar or the representative
# rejects is reported under.
FAMILY_CASE_CAT = "family case"
# The header: the leading comment block, the task id, then `@draft`, then
# the fields and the claims in this order. A value continues on a line of
# `//` and two spaces. `review` repeats; the others stand once.
HEADER_CAT = "header"
# A `@claim` line: what it names, and where it stands.
CLAIM_CAT = "claim"

# A header keyword the doc does not list. A session adds the keyword it needs
# and proposes it in its review, so this is a hint, not a finding.
KEYWORD_CAT = "keyword"
# Every header line in the order they stand, with the rank the order check
# reads.
HEADER_ORDER = ("@draft", "@representative", "@keywords", "@scene", "@rule",
                "concept", "input", "output", "review")
HEADER_RANK = {"draft": 0, "representative": 1, "keywords": 1, "scene": 2,
               "rule": 3, "concept": 4, "input": 5, "output": 6, "review": 7}
# The fields a sibling drops in favour of `@representative:`.
SIBLING_DROPS = ("@keywords:", "concept:", "input:", "output:")
# The words of the witness grammar, whose findings stand under the witness
# category.
WITNESS_WORDS = frozenset({"witness", "relaxed", "reassigned", "deviation"})
# Cases that share facts or rules stand under one marker, and that marker
# joins their names with a comma. The names run to the first colon, after
# which the marker may carry a gloss.
CASE_MARKER_CAT = "case marker"

# A gloss stands above `Choice`. Each constructor of a choice ADT opens a
# line of its own, and its directive lines are its description.
GLOSS_CAT = "gloss"
FIELD_TYPE_RE = re.compile(r":\s*(\w+)")
BRANCH_LINE_RE = r"^\s*(?:\|\s*)?{name}\s*\{{"
# The concept branch stands first in its type and carries no witness line;
# every other branch carries at least one.
WITNESS_CAT = "witness"
WITNESS_FORM = FORMS["witness"]
# A lib component marked as a construction: an instance of it serves no
# claim of its own, so it carries no `@claim` line.
CONSTRUCTION_RE = re.compile(r"^\.comp\s+(\w+).*//\s*@construction", re.M)
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
    a component's public relations are its interface."""
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
                    f"`{seg}` is private to {comp}; read one of its "
                    f"public relations",
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
                        f"`{it.comp}` is internal to the lib; instantiate a public component",
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
        "no Determine comp reads this Parse comp; read it in Determine, "
        "or fold it into the program",
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
        text = solver_file(task_id)[0].read_text()
    except OSError:
        return None
    try:
        return parse(text).items
    except ParseError:
        return None


def _family_case(
    ann: Annotations, raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """A `@representative:` line whose case name the representative does not
    hold.

    The case names one case of the representative's `Choice`, so the name
    stands among that type's constructors. A record-typed `Choice` has no
    constructors, so no name stands. A representative there is no parse of
    says nothing about the name, and the line passes.
    """
    findings: list[tuple[str, int, str, str]] = []
    for f in ann.field_lines("representative"):
        parts = f.value.split()
        if len(parts) < 2:
            continue
        task_id, case = parts[0], parts[1]
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
        findings.append((FAMILY_CASE_CAT, f.line, why,
                         raw_lines[f.line - 1].rstrip()))
    return findings


def _case_marker(raw_lines: list[str]) -> list[tuple[str, int, str, str]]:
    """A section marker whose case names are joined by `/`.

    A name may apply a constructor to the fields it fixes, so the names
    are read outside the parentheses.
    """
    findings: list[tuple[str, int, str, str]] = []
    for lineno, raw in enumerate(raw_lines, 1):
        m = SECTION_RE.match(raw.strip())
        if m is None:
            continue
        if any("/" in name for name in marker_names(m.group(1))):
            findings.append((
                CASE_MARKER_CAT, lineno,
                "a marker over several cases joins their names with a comma: "
                "`// --- Box, Erode ---`",
                raw.rstrip(),
            ))
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


def _malformed(
    ann: Annotations, raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """Every line that opens an annotation and breaks its form, under the
    category of the grammar it belongs to."""
    out: list[tuple[str, int, str, str]] = []
    for bad in ann.malformed:
        if bad.word in WITNESS_WORDS:
            cat = WITNESS_CAT
        elif bad.line <= ann.header_end:
            cat = HEADER_CAT
        else:
            cat = CLAIM_CAT
        out.append((cat, bad.line, bad.why, raw_lines[bad.line - 1].rstrip()))
    return out


def _header(
    ann: Annotations, raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """The header lines that break the grammar, and the fields it lacks."""
    findings: list[tuple[str, int, str, str]] = []

    def flag(lineno: int, why: str) -> None:
        findings.append((HEADER_CAT, lineno, why, raw_lines[lineno - 1].rstrip()))

    if not raw_lines or not raw_lines[0].strip().startswith("//"):
        return [(HEADER_CAT, 1, "the file opens with `// <task_id>`",
                 raw_lines[0].rstrip() if raw_lines else "")]
    # Every header line the order check reads, as (line, rank, word).
    placed = [(f.line, HEADER_RANK[f.word], f.word) for f in ann.fields]
    placed += [(c.line, HEADER_RANK[c.kind], c.kind) for c in ann.claims]
    placed.sort()
    last = -1
    for lineno, rank, _ in placed:
        if rank < last:
            flag(lineno, "header lines go in the order "
                 + ", ".join(HEADER_ORDER))
        last = max(last, rank)
    seen: set[str] = set()
    for f in ann.fields:
        if f.word == "draft":
            if f.line > 2:
                flag(f.line, "`@draft` goes under the task id")
            continue
        if f.word == "review":
            if not f.kind:
                flag(f.line, "`review` takes a kind: `// review <kind>: <text>`")
        elif f.word in seen:
            flag(f.line, f"`{f.word}` stands once in the header")
        elif "representative" in seen or (f.word == "representative" and seen):
            flag(f.line, "a sibling carries `@representative:` in place of "
                 + ", ".join(f"`{w}`" for w in SIBLING_DROPS))
        seen.add(f.word)
    slugs: set[str] = set()
    for c in ann.claims:
        if c.slug in slugs:
            flag(c.line, f"`{c.slug}` names an earlier header line; a slug "
                 "stands once across `@scene` and `@rule`")
        slugs.add(c.slug)
    for lineno in ann.prose[:1]:
        flag(lineno, "no prose in the header; a remark about a case goes "
             "at its constructor, and a remark about a clause at the clause")
    known = _known_keywords()
    keywords = ann.field_lines("keywords")
    if keywords and known:
        for word in ann.keywords():
            if word not in known:
                findings.append((KEYWORD_CAT, keywords[0].line,
                                 f"`{word}` is not in keywords.md; propose it in the review",
                                 raw_lines[keywords[0].line - 1].rstrip()))
    if not seen & {"keywords", "representative"}:
        flag(1, "the header carries `@keywords:` or `@representative:`")
    elif ("keywords" in seen and "output" not in seen
            and not any(c.kind == "rule" for c in ann.claims)):
        flag(1, "the header has no `@rule` line; a rule is " + FORMS["rule"])
    return findings


def _comment_lines_above(raw_lines: list[str], lineno: int) -> list[int]:
    """The numbers of the consecutive comment lines directly above `lineno`,
    nearest first, stopping at a section marker."""
    out: list[int] = []
    n = lineno - 1
    while n >= 1:
        line = raw_lines[n - 1].strip()
        if not line.startswith("//") or SECTION_RE.match(line):
            break
        out.append(n)
        n -= 1
    return out


def _gloss_above(raw_lines: list[str], lineno: int) -> bool:
    """A gloss comment stands on the line above `lineno`."""
    if lineno < 2:
        return False
    above = raw_lines[lineno - 2].strip()
    return above.startswith("//") and not SECTION_RE.match(above)


SELF = -1
"""The index `_choice_adts` gives `Choice` itself."""

NESTED = -2
"""The index `_choice_adts` gives an ADT a constructor's field names. A case
label drops such a field, so the case column does not carry its branch."""


def _choice_adts(items: list[Item]) -> list[tuple[int, TypeDecl | None]]:
    """The ADTs a solver's `Choice` ranges over, each with the index of the
    field that carries it. A field whose type is no ADT takes None."""
    types = {it.name: it for it in items if isinstance(it, TypeDecl)}
    choice = types.get("Choice")
    if choice is None:
        return []
    fields = [types.get(n) for n in FIELD_TYPE_RE.findall(choice.rhs)]
    if choice.branches:
        return [(SELF, choice)] + [(NESTED, td) for td in fields
                                   if td is not None and td.branches]
    return [(i, td if td is not None and td.branches else None)
            for i, td in enumerate(fields)]


def _branch_sites(td: TypeDecl, raw_lines: list[str]) -> list[tuple[str, int | None]]:
    """Each branch of `td` with the line it opens, in declaration order. The
    line is None when the branch opens no line of its own."""
    sites: list[tuple[str, int | None]] = []
    used: set[int] = set()
    for name in td.branches:
        pat = re.compile(BRANCH_LINE_RE.format(name=re.escape(name)))
        at = next((n for n in range(td.line, len(raw_lines) + 1)
                   if n not in used and pat.match(raw_lines[n - 1])), None)
        if at is not None:
            used.add(at)
        sites.append((name, at))
    return sites


def _witnesses_of(ann: Annotations, raw_lines: list[str], at: int) -> tuple[str, ...]:
    """The ids of the `@witness` lines above `at`, nearest first."""
    by_line = {w.line: w.id for w in ann.witnesses}
    return tuple(by_line[n] for n in _comment_lines_above(raw_lines, at)
                 if n in by_line)


@dataclass(frozen=True)
class Branch:
    """One branch of a choice point, `is_concept` on the one declared first.
    `witnesses` holds the ids of the branch's `@witness` lines, and stands
    empty when it carries none."""

    name: str
    is_concept: bool
    line: int | None
    witnesses: tuple[str, ...]


@dataclass(frozen=True)
class ChoicePoint:
    """One choice point of a solver: `Choice` itself, at SELF, or one field
    of a record-typed `Choice`, at that field's index. The branches stand
    in declaration order, and stand empty when the field's type is no
    ADT."""

    field: int
    type: str
    branches: tuple[Branch, ...]


def choice_points(source: str) -> list[ChoicePoint]:
    """The choice points a solver's case column carries, in field order. A
    source that declares no `Choice`, or that does not parse, has none."""
    try:
        items = parse(source).items
    except ParseError:
        return []
    src = _strip_block_comments(source)
    raw_lines = src.splitlines()
    ann = read(src)
    points: list[ChoicePoint] = []
    for field, td in _choice_adts(items):
        if field == NESTED:
            continue
        if td is None:
            points.append(ChoicePoint(field=field, type="", branches=()))
            continue
        points.append(ChoicePoint(field=field, type=td.name, branches=tuple(
            Branch(name=name, is_concept=i == 0, line=at,
                   witnesses=() if at is None
                   else _witnesses_of(ann, raw_lines, at))
            for i, (name, at) in enumerate(_branch_sites(td, raw_lines)))))
    return points


def concept_case(source: str) -> str:
    """The case the concept branches make, spelled as the runner spells a
    case name. A solver that declares no `Choice` has the one case the
    runner names. A choice point that ranges over no ADT leaves the case
    unspelled, and the answer is empty."""
    points = choice_points(source)
    if not points:
        return NO_CHOICE
    if any(not p.branches for p in points):
        return ""
    names = [p.branches[0].name for p in points]
    if len(points) == 1 and points[0].field == SELF:
        return case_label(f"${names[0]}()")
    return case_label("[" + ", ".join(f"${n}()" for n in names) + "]")


def branch_above(source: str, line: int) -> str:
    """The name of the choice branch whose comment block holds `line`, and
    empty when no branch's block does."""
    raw_lines = _strip_block_comments(source).splitlines()
    for point in choice_points(source):
        for b in point.branches:
            if b.line is None:
                continue
            if line in _comment_lines_above(raw_lines, b.line):
                return b.name
    return ""


def _glosses(
    ann: Annotations, items: list[Item], raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """`Choice` lacking the gloss above the type, and the constructors of a
    choice ADT — of `Choice` itself, and of the ADTs named as field types —
    that open no line of their own."""
    targets: list[tuple[bool, TypeDecl]] = []
    seen: set[str] = set()
    for field, td in _choice_adts(items):
        if td is not None and td.name not in seen:
            seen.add(td.name)
            targets.append((field == SELF, td))
    findings: list[tuple[str, int, str, str]] = []
    for is_choice, td in targets:
        if is_choice and not _gloss_above(raw_lines, td.line):
            findings.append((GLOSS_CAT, td.line,
                             f"a gloss stands above `{td.name}`: what the choice is",
                             raw_lines[td.line - 1].rstrip()))
        for name, at in _branch_sites(td, raw_lines):
            if at is None:
                findings.append((GLOSS_CAT, td.line,
                                 f"`{name}` opens its own line",
                                 raw_lines[td.line - 1].rstrip()))
                continue
            witnessed = bool(_witnesses_of(ann, raw_lines, at))
            if name == td.branches[0] and witnessed:
                findings.append((WITNESS_CAT, at,
                                 f"`{name}` is the concept branch; drop its "
                                 "`@witness` line",
                                 raw_lines[at - 1].rstrip()))
            elif name != td.branches[0] and not witnessed:
                findings.append((WITNESS_CAT, at,
                                 f"`{name}` is no concept branch and has no "
                                 f"`@witness` line; add {WITNESS_FORM}",
                                 raw_lines[at - 1].rstrip()))
    return findings


@lru_cache(maxsize=2)
def _constructions(text: str) -> frozenset[str]:
    """The lib components marked `// @construction`. An instance of one of
    them builds a term the model reads through, and serves no claim of its
    own."""
    return frozenset(CONSTRUCTION_RE.findall(text))


def _claimed_instances(items: list[Item]) -> list[Init]:
    """Every instance a `@claim` line stands above: the ones at program
    scope and the ones inside `Parse`, of a component the lib does not mark
    `@construction`. An instance of a comp the solver holds itself — Params,
    Determine, Parse — states no claim of the model."""
    built = _constructions(_lib_source()) | frozenset(STOCK_COMPS)
    inner = [i for it in items if isinstance(it, Comp) and it.name == "Parse"
             for i in it.items]
    return [it for it in (*items, *inner)
            if isinstance(it, Init) and it.comp not in built]


def _claims(
    ann: Annotations, source: str, program: Program, raw_lines: list[str],
) -> list[tuple[str, int, str, str]]:
    """A `@claim` line that names a slug no header states, and, in a solver
    whose header states claims, an instance or a concept branch that carries
    no `@claim` line.

    A solver whose header states no claim is not written under the claim
    grammar, so nothing references anything and the check stays quiet.
    """
    findings: list[tuple[str, int, str, str]] = []

    def flag(lineno: int, why: str) -> None:
        findings.append((CLAIM_CAT, lineno, why, raw_lines[lineno - 1].rstrip()))

    stated = {c.slug for c in resolved_claims(source)}
    stated |= {c.slug for c in ann.branch_claims}
    for ref in ann.refs:
        for slug in ref.slugs:
            if slug not in stated:
                flag(ref.line, f"`{slug}` names no `@scene` or `@rule` line "
                     "of the header")
    if not ann.claims:
        return findings
    at = {ref.above for ref in ann.refs}
    for init in _claimed_instances(program.items):
        if init.line not in at:
            flag(init.line, f"`{init.inst}` carries no `@claim` line; the "
                 "claims the instance serves stand above it as "
                 f"{FORMS['claim']}")
    for point in _choice_adts(program.items):
        td = point[1]
        if td is None or not td.branches:
            continue
        name, line = _branch_sites(td, raw_lines)[0]
        if line is not None and line not in at:
            flag(line, f"`{name}` is the concept branch; the claim the choice "
                 f"answers stands above it as {FORMS['claim']}")
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
            f"`{td.name}` is none of the types a solver may define — "
            f"`Choice` and the types it reaches, `TiebreakResolution`, or a "
            f"record filling a comp type param; re-encode it or propose",
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
    # A `//` line inside a block comment is no annotation, so the grammar
    # reads the source the block comments are blanked out of.
    ann = read(src)
    findings.extend(_family_case(ann, raw_lines))
    findings.extend(_case_marker(raw_lines))
    findings.extend(_malformed(ann, raw_lines))
    findings.extend(_header(ann, raw_lines))

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
    findings.extend(_glosses(ann, program.items, raw_lines))
    findings.extend(_claims(ann, src, program, raw_lines))
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
        singleton_axis = any(
            SINGLETON_AXIS_MARKER in raw_lines[ln - 1] for ln in span
        )
        for ln in span:
            for m in NUMERIC_LITERAL_RE.finditer(code(ln)):
                if exempt_literal(m.group(0), singleton_axis):
                    continue
                findings.append(
                    ("params data", ln, m.group(0), raw_lines[ln - 1].rstrip())
                )
    return findings
