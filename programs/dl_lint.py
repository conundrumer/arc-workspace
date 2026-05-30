"""Lint .dl solver bodies against 4-style.md.

Flags orientation literals, bare nonzero literals, and arithmetic in
solver-body code. `.comp` blocks are skipped wholesale — components are
generic, lib-shaped code, not solver body. The public entry point is
`lint_body`; run_dl.py calls it after running each solver.
"""

import re

ORIENTATION_LITERALS = {
    # Dirs
    "TOP", "BOTTOM", "LEFT", "RIGHT",
    # Axes
    "VERTICAL", "HORIZONTAL",
    # DiagDirs
    "TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT",
    # DiagAxes
    "DIAGONAL", "ANTIDIAGONAL",
    # D4
    "IDENTITY", "ROT_CW", "ROT_180", "ROT_CCW",
    "FLIP_LR", "FLIP_TB", "FLIP_DIAG", "FLIP_ANTIDIAG",
}

ORIENTATION_LITERAL_RE = re.compile(
    r"\b(" + "|".join(sorted(ORIENTATION_LITERALS, key=len, reverse=True)) + r")\b"
)
COMMENT_RE = re.compile(r"//.*$")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", flags=re.DOTALL)
COMP_OPEN_RE = re.compile(r"\.comp\s+\w+")
NUMERIC_LITERAL_RE = re.compile(r"(?<![A-Za-z_0-9.])\d+(?![A-Za-z_0-9.])")

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


def _find_arithmetic(line: str) -> list[tuple[int, str]]:
    """Find binary arithmetic ops (+, -, *, /, %) with value-shaped operands."""
    out: list[tuple[int, str]] = []
    for m in re.finditer(r"[+\-*/%]", line):
        i = m.start()
        if _value_context(line, i, i + 1):
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
      - 'orientation literal' — TOP, LEFT, etc. (must come from Consts)
      - 'nonzero literal'     — bare integer != 0
      - 'arithmetic'          — +, -, *, /, %
      - 'comparison' (gated)  — <, <=, >, >=; enabled by LINT_COMPARISON

    Returns (category, lineno, match, raw_line). Skips // and /* */
    comments and `.comp` blocks (detected by `.comp Name {` with the opening
    brace on the header line, then balanced to the closing brace).
    """
    findings: list[tuple[str, int, str, str]] = []
    src = _strip_block_comments(source)
    in_comp = False
    comp_depth = 0

    for lineno, raw_line in enumerate(src.splitlines(), start=1):
        line = COMMENT_RE.sub("", raw_line)

        if not in_comp and COMP_OPEN_RE.search(line) and "{" in line:
            comp_depth = line.count("{") - line.count("}")
            in_comp = comp_depth > 0
            continue

        if in_comp:
            comp_depth += line.count("{") - line.count("}")
            if comp_depth <= 0:
                in_comp = False
            continue

        for m in ORIENTATION_LITERAL_RE.finditer(line):
            findings.append(("orientation literal", lineno, m.group(1), raw_line.rstrip()))
        for m in NUMERIC_LITERAL_RE.finditer(line):
            if m.group(0) != "0":
                findings.append(("nonzero literal", lineno, m.group(0), raw_line.rstrip()))
        for _, op in _find_arithmetic(line):
            findings.append(("arithmetic", lineno, op, raw_line.rstrip()))
        if LINT_COMPARISON:
            for _, op in _find_comparison(line):
                findings.append(("comparison", lineno, op, raw_line.rstrip()))

    findings.sort(key=lambda f: (f[1], f[0]))
    return findings
