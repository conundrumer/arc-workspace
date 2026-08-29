"""Lint .dl solver bodies against 4-style.md.

Flags orientation literals, bare nonzero literals, arithmetic, and the
`range` generator in solver-body code. `.comp` blocks are skipped wholesale —
a proposal comp is lib code on its way out of the solver, and its
proposals.md entry is what makes it legitimate — except `Fit` and `Parse`,
whose rules are model claims and lint as body. The public entry
point is `lint_body`; run_dl.py calls it after running each solver.
"""

import re
from functools import lru_cache

from dl.dlparse import Comp, Init, Item, ParseError, Rule, TypeDecl, parse
from dl.paths import PROGRAMS_DIR

ORIENTATION_LITERALS = {
    # Dirs
    "DIR_T", "DIR_B", "DIR_L", "DIR_R",
    # Axes
    "AXIS_V", "AXIS_H",
    # DiagDirs
    "DIAG_TL", "DIAG_TR", "DIAG_BL", "DIAG_BR",
    # DiagAxes
    "DAXIS_DG", "DAXIS_AD",
    # D4
    "D4_ID", "D4_CW", "D4_HT", "D4_CC",
    "D4_LR", "D4_TB", "D4_DG", "D4_AD",
}

ORIENTATION_LITERAL_RE = re.compile(
    r"\b(" + "|".join(sorted(ORIENTATION_LITERALS, key=len, reverse=True)) + r")\b"
)
COMMENT_RE = re.compile(r"//.*$")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", flags=re.DOTALL)
NUMERIC_LITERAL_RE = re.compile(r"(?<![A-Za-z_0-9.])\d+(?![A-Za-z_0-9.])")
UNIT_MARKER = "@unit"


def exempt_literal(lit: str, unit: bool) -> bool:
    """A 0 anywhere; a 1 in a unit-marked rule."""
    return lit == "0" or (unit and lit == "1")
RANGE_RE = re.compile(r"\brange\s*\(")

# Souffle keywords. Each one was checked against the souffle 2.5 binary and
# rejected in every position a name can take: relation head, .decl, .init,
# .type, .comp, .functor, and attribute. The directive words (`decl`, `type`,
# `init`, `comp`, `plan`, ...) are reserved only with their leading dot, so
# they are usable as names and are not here.
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


def _lib_source() -> str:
    """lib.dl's text, or empty when it is not there to read."""
    try:
        return (PROGRAMS_DIR / "lib.dl").read_text()
    except OSError:
        return ""


@lru_cache(maxsize=2)
def _lib_comps(text: str) -> dict[str, Comp]:
    """lib.dl's components, keyed by name. Keyed on the text, so an edit to
    lib.dl reaches a process that already linted against it."""
    try:
        return _comp_table(parse(text).items)
    except ParseError:
        return {}


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
    table = _lib_comps(_lib_source()) | _comp_table(items)
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


def lint_body(source: str) -> list[tuple[str, int, str, str]]:
    """Flag body code that violates 4-style.md.

    Categories:
      - 'orientation literal' — DIR_T, DIR_L, etc. (must come from Consts)
      - 'nonzero literal'     — bare integer != 0
      - 'arithmetic'          — +, -, *, /, %
      - 'range'               — the `range` number generator
      - 'consts data'         — literal in a Consts rule, minus
                                `exempt_literal` exemptions
      - 'rigid chart'         — a `_rigid_` name, anywhere: RIGID charts
                                are readable only through their placed forms
      - 'reserved name'       — a declared name Souffle reserves, which
                                costs the whole file a parse
      - 'shadowed type'       — a type argument that collides with a type
                                name inside the component it is passed to
      - 'comparison' (gated)  — <, <=, >, >=; enabled by LINT_COMPARISON

    Returns (category, lineno, match, raw_line). Skips // and /* */
    comments and `.comp` blocks (spans from the parsed source) — except
    `Fit` and `Parse`, which lint as body, and `Consts`, whose rules take
    the 'consts data' check. The reserved-name check reads every line,
    comps included, since Souffle rejects such a name anywhere. A source
    that does not parse returns that check's findings alone; the rewrite
    lint reports the parse error.
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
        if comp.name in ("Fit", "Parse"):
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

    findings.extend(_shadowed_types(program.items, raw_lines))
    findings.extend(_consts_data(program.comps().get("Consts"), raw_lines, code))
    findings.sort(key=lambda f: (f[1], f[0]))
    return findings


def _consts_data(
    comp: Comp | None, raw_lines: list[str], code,
) -> list[tuple[str, int, str, str]]:
    """Consts-rule literals that `exempt_literal` does not exempt."""
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
                    ("consts data", ln, m.group(0), raw_lines[ln - 1].rstrip())
                )
    return findings
