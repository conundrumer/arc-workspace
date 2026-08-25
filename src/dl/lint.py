"""Lint .dl solver bodies against 4-style.md.

Flags orientation literals, bare nonzero literals, arithmetic, and the
`range` generator in solver-body code. `.comp` blocks are skipped wholesale —
components are generic, lib-shaped code, not solver body — except `Fit` and
`Parse`, whose rules are model claims and lint as body. The public entry
point is `lint_body`; run_dl.py calls it after running each solver.
"""

import re

from dl.dlparse import Comp, ParseError, Rule, parse

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
RANGE_RE = re.compile(r"\brange\s*\(")

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


def lint_body(source: str) -> list[tuple[str, int, str, str]]:
    """Flag body code that violates 4-style.md.

    Categories:
      - 'orientation literal' — DIR_T, DIR_L, etc. (must come from Consts)
      - 'nonzero literal'     — bare integer != 0
      - 'arithmetic'          — +, -, *, /, %
      - 'range'               — the `range` number generator
      - 'consts data'         — nonzero literal in a Consts rule; a rule
                                line commented `@structural` exempts the rule
      - 'comparison' (gated)  — <, <=, >, >=; enabled by LINT_COMPARISON

    Returns (category, lineno, match, raw_line). Skips // and /* */
    comments and `.comp` blocks (spans from the parsed source) — except
    `Fit` and `Parse`, which lint as body, and `Consts`, whose rules take
    the 'consts data' check. A source that does not parse returns no
    findings; the rewrite lint reports the parse error.
    """
    try:
        program = parse(source)
    except ParseError:
        return []

    findings: list[tuple[str, int, str, str]] = []
    src = _strip_block_comments(source)
    raw_lines = src.splitlines()

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

    findings.extend(_consts_data(program.comps().get("Consts"), raw_lines, code))
    findings.sort(key=lambda f: (f[1], f[0]))
    return findings


def _consts_data(
    comp: Comp | None, raw_lines: list[str], code,
) -> list[tuple[str, int, str, str]]:
    """Nonzero literals in Consts rules, minus `@structural`-marked rules."""
    findings: list[tuple[str, int, str, str]] = []
    if comp is None:
        return findings
    for it in comp.items:
        if not isinstance(it, Rule) or it.body is None:
            continue
        span = range(it.line, it.end_line + 1)
        if any("@structural" in raw_lines[ln - 1] for ln in span):
            continue
        for ln in span:
            for m in NUMERIC_LITERAL_RE.finditer(code(ln)):
                if m.group(0) != "0":
                    findings.append(
                        ("consts data", ln, m.group(0), raw_lines[ln - 1].rstrip())
                    )
    return findings
