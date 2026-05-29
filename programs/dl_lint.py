"""Lint .dl solver bodies against 4-style.md.

Flags orientation literals, bare nonzero literals, and arithmetic in
solver-body code. `.comp Consts` blocks are skipped wholesale; any other
`.comp` carrying a `// lint-ok` marker on its header (or the line above) is
treated as generic, lib-shaped code and skipped too. The public entry point is
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
COMP_CONSTS_OPEN_RE = re.compile(r"\.comp\s+Consts\s*\{")
COMP_OPEN_RE = re.compile(r"\.comp\s+\w+")
NUMERIC_LITERAL_RE = re.compile(r"(?<![A-Za-z_0-9.])\d+(?![A-Za-z_0-9.])")

# Suppression marker: `// lint-ok` on a `.comp` header (or the comment line
# directly above it) opts that whole generic component out of body linting — the
# comment-driven analog of how `.comp Consts` is skipped. `// lint-ok: <category>`
# narrows it to one category; text after an em-dash/period is a human reason,
# ignored. There is deliberately no per-line form: a flag on a task-body line
# means fix it (value -> Consts, op -> a primitive) or move the code into a
# component — not silence it in place.
LINT_OK_RE = re.compile(r"lint-ok\b\s*:?\s*([^\n]*)", re.IGNORECASE)

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


def _parse_lint_ok(comment: str) -> tuple[bool, set[str]]:
    """Parse `lint-ok` markers in a comment → (blanket, {category words}).

    `lint-ok: arithmetic — reason` yields (False, {'arithmetic'}); the reason
    after an em-dash/period is dropped. Bare `lint-ok` yields (True, set()).
    """
    blanket = False
    words: set[str] = set()
    for m in LINT_OK_RE.finditer(comment):
        spec = re.split(r"—|--|\.", m.group(1), maxsplit=1)[0]
        toks = set(re.findall(r"[a-z]+", spec.lower()))
        if toks:
            words |= toks
        else:
            blanket = True
    return blanket, words


def _suppresses(category: str, supp: tuple[bool, set[str]]) -> bool:
    """A finding category is suppressed by a blanket marker, or by any marker
    word that appears in the category (`literal` covers `nonzero literal`)."""
    blanket, words = supp
    return blanket or any(w in category for w in words)


def _comp_block_suppressions(lines: list[str]) -> dict[int, tuple[bool, set[str]]]:
    """Body-line suppressions from any non-Consts `.comp` whose header line — or
    the line directly above it — carries a lint-ok marker. Lets a whole generic
    component opt out, the way `.comp Consts` is skipped wholesale. Keyed by the
    1-based lineno of each body line."""
    out: dict[int, tuple[bool, set[str]]] = {}
    n = len(lines)
    i = 0
    while i < n:
        code = COMMENT_RE.sub("", lines[i])
        if (COMP_OPEN_RE.search(code) and "{" in code
                and not COMP_CONSTS_OPEN_RE.search(code)):
            hb, hw = _parse_lint_ok(lines[i].partition("//")[2])
            if i:
                ab, aw = _parse_lint_ok(lines[i - 1].partition("//")[2])
            else:
                ab, aw = False, set()
            supp = (hb or ab, hw | aw)
            depth = code.count("{") - code.count("}")
            j = i
            while depth > 0 and j + 1 < n:
                j += 1
                c = COMMENT_RE.sub("", lines[j])
                depth += c.count("{") - c.count("}")
            if supp[0] or supp[1]:
                for k in range(i + 1, j + 1):
                    out[k + 1] = supp
            i = j + 1
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
    comments and `.comp Consts { ... }` blocks; findings inside a
    `// lint-ok`-marked `.comp` are suppressed (see _comp_block_suppressions).
    """
    findings: list[tuple[str, int, str, str]] = []
    src = _strip_block_comments(source)
    src_lines = src.splitlines()
    comp_supp = _comp_block_suppressions(src_lines)
    in_consts = False
    consts_depth = 0

    for lineno, raw_line in enumerate(src.splitlines(), start=1):
        line = COMMENT_RE.sub("", raw_line)

        if not in_consts and COMP_CONSTS_OPEN_RE.search(line):
            in_consts = True
            consts_depth = line.count("{") - line.count("}")
            continue

        if in_consts:
            consts_depth += line.count("{") - line.count("}")
            if consts_depth <= 0:
                in_consts = False
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

    empty = (False, set())
    findings = [
        f for f in findings
        if not _suppresses(f[0], comp_supp.get(f[1], empty))
    ]
    findings.sort(key=lambda f: (f[1], f[0]))
    return findings
