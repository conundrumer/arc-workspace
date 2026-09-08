"""Lint .dl solver programs against the style doc under docs/wf-solver/.

`.comp` blocks are skipped wholesale — a proposal comp is lib code on its
way out of the solver, and its proposal entry is what makes it legitimate,
so a comp with no entry is a finding — except the comps whose rules are
model hypotheses, which lint as program. The public entry point is
`lint_program`; run_dl.py calls it after running each solver.
"""

import re
from functools import lru_cache

from dl.context import DOCS_DIR
from dl.dlparse import (
    Comp, Decl, Define, Functor, Init, Item, ParseError, Rigid, Rule,
    TypeDecl, parse,
)
from dl.paths import PROGRAMS_DIR


def _lib_source() -> str:
    """lib.dl's text, or empty when it is not there to read."""
    try:
        return (PROGRAMS_DIR / "lib.dl").read_text()
    except OSError:
        return ""


@lru_cache(maxsize=2)
def _lib_items(text: str) -> list[Item]:
    """lib.dl's parsed items, or none when it does not parse. Keyed on the
    text, so an edit to lib.dl reaches a process that already linted
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
    """lib.dl's top-level names, each with its kind."""
    return {it.name: LIB_KINDS[type(it)] for it in _lib_items(text)
            if type(it) in LIB_KINDS}


# lib.dl's macros, `ORIGIN` aside: a position, not an orientation.
ORIENTATION_LITERALS = frozenset(
    name for name, kind in _lib_names(_lib_source()).items()
    if kind == "macro" and name != "ORIGIN"
)

ORIENTATION_LITERAL_RE = re.compile(
    r"\b(" + "|".join(sorted(ORIENTATION_LITERALS, key=len, reverse=True)) + r")\b"
    if ORIENTATION_LITERALS else r"(?!)"
)
COMMENT_RE = re.compile(r"//.*$")
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
# The comps a solver holds as its own. Any other is a proposal comp,
# legitimate only with its entry under docs/wf-solver/proposals/.
STOCK_COMPS = ("Params", "Determine", "Parse")
PROPOSALS_DIR = DOCS_DIR / "proposals"
# The category a proposal comp with no entry is reported under.
NO_ENTRY_CAT = "comp without entry"
# RIGID chart names exist only in the macro expansion; any appearance in
# solver source reads a stored pose the model claims unobservable.
RIGID_CHART_RE = re.compile(r"\b_rigid_\w+")

# Comparison-ops detector (<, <=, >, >=). Body comparisons are usually
# legitimate, so this is opt-in.
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
    its name appears. Its message points at lib.dl's line for some of
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

    try:
        program = parse(source)
    except ParseError:
        return findings

    def code(lineno: int) -> str:
        line = COMMENT_RE.sub("", raw_lines[lineno - 1])
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
    findings.extend(_comps_without_entry(program.items, raw_lines))
    findings.extend(_banned_types(program.items, raw_lines))
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
