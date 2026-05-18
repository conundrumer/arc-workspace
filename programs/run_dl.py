"""Run Souffle solvers against their tasks' train+test pairs.

Usage:
    uv run python programs/run_dl.py            # run all .dl solvers
    uv run python programs/run_dl.py <stem>     # run one

For a single stem, encodes each example's input grid as fact lines on stdin,
invokes `souffle -D- <stem>.dl`, reads the output relation from stdout,
compares to expected output grid.
"""

import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from arc.task import load as load_task  # noqa: E402

SOLVERS_DIR = REPO_ROOT / "programs" / "solvers"


def grid_to_facts(rows: list[list[int]]) -> str:
    """Encode a grid as Souffle facts for `in(p, col)` over Position records."""
    h = len(rows)
    w = len(rows[0]) if h > 0 else 0
    lines = []
    for row in range(h):
        for col in range(w):
            t = row
            b = h - 1 - row
            l = col
            r = w - 1 - col
            lines.append(f"[{t}, {b}, {l}, {r}]\t{rows[row][col]}")
    return "\n".join(lines) + ("\n" if lines else "")


def parse_output(stdout: str) -> list[tuple[str, list[list[int]], list[tuple[int, int]]]]:
    """Parse Souffle's default text output for the `out` relation.

    Returns a list of (variant, grid, conflicts) tuples. Variant is the
    trailing column value (e.g. '$FlipTB') from a Choice ADT, or '' when
    `out` has no trailing column. Cells are grouped by variant; each group
    is one grid. `conflicts` is a sorted list of (t, l) cells that received
    multiple distinct colors within the same variant — an ambiguous output
    that the solver should treat as a failure.
    """
    parts = re.split(r"^={3,}$", stdout, flags=re.MULTILINE)
    if len(parts) < 3:
        raise ValueError(f"unexpected souffle output:\n{stdout}")
    data = parts[1].strip()
    if not data:
        return [("", [], [])]

    line_re = re.compile(r"\[(-?\d+), (-?\d+), (-?\d+), (-?\d+)\]\t(-?\d+)(?:\t(.+))?$")
    grouped: dict[str, list] = {}
    for line in data.splitlines():
        m = line_re.match(line)
        if not m:
            raise ValueError(f"unexpected fact line: {line!r}")
        groups = m.groups()
        variant = groups[5] if groups[5] is not None else ""
        cells = grouped.setdefault(variant, [])
        cells.append(tuple(int(x) for x in groups[:5]))

    candidates: list[tuple[str, list[list[int]], list[tuple[int, int]]]] = []
    for variant in sorted(grouped):
        cells = grouped[variant]
        bounds = {(t + b + 1, l + r + 1) for (t, b, l, r, _) in cells}
        if len(bounds) != 1:
            raise ValueError(f"inconsistent grid bounds in {variant!r}: {bounds}")
        h, w = next(iter(bounds))
        grid = [[0] * w for _ in range(h)]
        seen: dict[tuple[int, int], int] = {}
        conflicts: set[tuple[int, int]] = set()
        for (t, b, l, r, color) in cells:
            if t < 0 or l < 0 or t >= h or l >= w:
                raise ValueError(f"cell out of derived bounds: ({t}, {l}) in {h}x{w}")
            if (t, l) in seen and seen[(t, l)] != color:
                conflicts.add((t, l))
            seen[(t, l)] = color
            grid[t][l] = color
        candidates.append((variant, grid, sorted(conflicts)))
    return candidates


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
    comments and `.comp Consts { ... }` blocks.
    """
    findings: list[tuple[str, int, str, str]] = []
    src = _strip_block_comments(source)
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

    findings.sort(key=lambda f: (f[1], f[0]))
    return findings


GRID_MACRO_RE = re.compile(r"\bGRID_(\d+)x(\d+)\b")


def gen_grid_macro(h: int, w: int) -> str:
    """Emit `#define GRID_HxW(rel, V0, V1, ...) rel([t,b,l,r], Vk). ...`.

    The macro expands to one fact per cell of an H×W frame, in row-major order
    over Vk arg names. Position values are inlined per (H, W) pair.
    """
    args = ", ".join(f"V{i}" for i in range(h * w))
    rows = []
    for row in range(h):
        cells = []
        for col in range(w):
            v = f"V{row * w + col}"
            cells.append(f"rel([{row}, {h-1-row}, {col}, {w-1-col}], {v}).")
        rows.append(" ".join(cells))
    body = " \\\n    ".join(rows)
    return f"#define GRID_{h}x{w}(rel, {args}) \\\n    {body}"


def expand_grid_macros(source: str) -> tuple[str, bool]:
    """Prepend `#define GRID_HxW` lines for every (H, W) used in source."""
    dims = {(int(m.group(1)), int(m.group(2))) for m in GRID_MACRO_RE.finditer(source)}
    if not dims:
        return source, False
    macros = "\n".join(gen_grid_macro(h, w) for (h, w) in sorted(dims))
    return f"// Generated GRID_HxW expansions.\n{macros}\n\n{source}", True


def run_dl(
    task_id: str, input_rows: list[list[int]], stem: str | None = None
) -> list[tuple[str, list[list[int]], list[tuple[int, int]]]]:
    dl_path = SOLVERS_DIR / f"{stem or task_id}.dl"
    if not dl_path.exists():
        raise FileNotFoundError(f"no .dl solver at {dl_path}")

    source = dl_path.read_text()
    expanded, modified = expand_grid_macros(source)
    if modified:
        # Tempfile lives next to the original so `#include "../lib.dl"` resolves.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dl", dir=str(SOLVERS_DIR), delete=False
        ) as tf:
            tf.write(expanded)
            run_path = Path(tf.name)
        try:
            return _invoke_souffle(run_path, input_rows)
        finally:
            run_path.unlink(missing_ok=True)
    return _invoke_souffle(dl_path, input_rows)


def _invoke_souffle(
    dl_path: Path, input_rows: list[list[int]]
) -> list[tuple[str, list[list[int]], list[tuple[int, int]]]]:
    facts = grid_to_facts(input_rows)
    # Bound runaway souffle: some rule shapes can hang the evaluator
    # and exhaust system memory.
    result = subprocess.run(
        ["souffle", "-D-", "-w", str(dl_path)],
        input=facts,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError(f"souffle exited {result.returncode}:\n{result.stderr}")
    return parse_output(result.stdout)


@dataclass
class VariantResult:
    name: str  # '' when out has no trailing column
    ok: bool
    actual: list[list[int]]
    conflicts: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class PairResult:
    kind: str
    idx: int
    ok: bool
    error: str | None = None
    expected: list[list[int]] | None = None
    accepted: list[list[list[int]]] | None = None
    variants: list[VariantResult] = field(default_factory=list)


@dataclass
class TaskResult:
    stem: str
    pairs: list[PairResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.pairs)

    @property
    def passes(self) -> int:
        return sum(1 for p in self.pairs if p.ok)

    @property
    def all_pass(self) -> bool:
        return all(p.ok for p in self.pairs)


def run_pair(stem: str, task_id: str, kind: str, idx: int, ex) -> PairResult:
    try:
        actuals = run_dl(task_id, ex.input, stem=stem)
        accepted: list[list[list[int]]] = [ex.output]
        if ex.alt is not None and ex.alt.kind == "tiebreak":
            accepted.append(ex.alt.grid)
        variants = [
            VariantResult(
                name=v,
                ok=(g in accepted) and not c,
                actual=g,
                conflicts=c,
            )
            for v, g, c in actuals
        ]
        ok = bool(variants) and all(v.ok for v in variants)
        return PairResult(
            kind=kind,
            idx=idx,
            ok=ok,
            expected=ex.output,
            accepted=accepted,
            variants=variants,
        )
    except Exception as e:
        return PairResult(
            kind=kind, idx=idx, ok=False, error=f"{type(e).__name__}: {e}"
        )


def _pair_work(stem: str) -> list[tuple]:
    """Build (stem, task_id, kind, idx, ex) tuples for every pair of `stem`."""
    task_id = stem.split("_", 1)[0]
    task = load_task(task_id)
    work = []
    for kind, examples in (("train", task.train), ("test", task.test)):
        for idx, ex in enumerate(examples):
            work.append((stem, task_id, kind, idx, ex))
    return work


def run_task(stem: str) -> TaskResult:
    """Single-task entry: pairs run in parallel."""
    work = _pair_work(stem)
    with ThreadPoolExecutor() as executor:
        pairs = list(executor.map(lambda w: run_pair(*w), work))
    return TaskResult(stem=stem, pairs=pairs)


def _grid_lines(grid: list[list[int]]) -> list[str]:
    """One line per row; 0 rendered as '.' for readability."""
    if not grid or not grid[0]:
        return ["(empty)"]
    return [" ".join("." if c == 0 else str(c) for c in row) for row in grid]


def render_diff(expected: list[list[int]], actual: list[list[int]]) -> list[str]:
    """Stacked expected then actual; mismatch count below."""
    eh = len(expected) if expected else 0
    ew = len(expected[0]) if eh else 0
    ah = len(actual) if actual else 0
    aw = len(actual[0]) if ah else 0

    lines = ["expected:"]
    lines.extend(_grid_lines(expected))
    lines.append("actual:")
    lines.extend(_grid_lines(actual))

    if (eh, ew) == (ah, aw) and eh > 0:
        n_diff = sum(
            1 for r in range(eh) for c in range(ew) if expected[r][c] != actual[r][c]
        )
        if n_diff:
            lines.append(f"{n_diff}/{eh*ew} cells differ")
    elif (eh, ew) != (ah, aw):
        lines.append(f"shape mismatch: {eh}x{ew} vs {ah}x{aw}")

    return lines


def render_pair_failure(p: PairResult) -> list[str]:
    """Lines describing a failing pair: variant breakdown + diff per failing actual."""
    lines = [f"{p.kind}[{p.idx}]: FAIL"]
    if p.error:
        lines.append(f"  {p.error}")
        return lines
    if not p.variants:
        lines.append("  (no variants emitted)")
        return lines

    has_named = any(v.name for v in p.variants)
    multi = len(p.variants) > 1

    if has_named or multi:
        pass_v = [v.name or "(out)" for v in p.variants if v.ok]
        fail_v = [v.name or "(out)" for v in p.variants if not v.ok]
        lines.append(f"  variants: {len(pass_v)} pass / {len(fail_v)} fail")
        if pass_v:
            lines.append(f"    pass: {', '.join(pass_v)}")
        if fail_v:
            lines.append(f"    fail: {', '.join(fail_v)}")

    # Group failing variants by (actual output, conflict cells) so duplicates
    # share one diff block.
    groups: dict[tuple, list[str]] = defaultdict(list)
    for v in p.variants:
        if v.ok:
            continue
        key = (
            tuple(tuple(r) for r in v.actual) if v.actual else (),
            tuple(v.conflicts),
        )
        groups[key].append(v.name or "(out)")

    for (actual_key, conflicts_tup), names in groups.items():
        actual = [list(r) for r in actual_key]
        lines.append("")
        if has_named or multi:
            lines.append(f"  {', '.join(names)}:")
        if conflicts_tup:
            lines.append(f"    conflicts at: {list(conflicts_tup)}")
        else:
            for dl in render_diff(p.expected or [], actual):
                lines.append(f"    {dl}")

    return lines


def all_stems() -> list[str]:
    return sorted(p.stem for p in SOLVERS_DIR.glob("*.dl"))


def cmd_one(stem: str) -> int:
    result = run_task(stem)
    for p in result.pairs:
        if p.ok:
            print(f"{p.kind}[{p.idx}]: PASS")
        else:
            for line in render_pair_failure(p):
                print(line)

    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    findings = lint_body(source)
    if findings:
        print()
        print(f"--- {len(findings)} lint finding(s) in {stem}.dl ---")
        for cat, lineno, match, line in findings:
            print(f"  L{lineno}: {cat} `{match}`  →  {line.strip()}")

    return 0 if result.all_pass else 1


def cmd_all() -> int:
    stems = all_stems()

    # Flatten all (stem, pair) work so the pool sees one big queue.
    all_work: list[tuple] = []
    for stem in stems:
        all_work.extend(_pair_work(stem))

    with ThreadPoolExecutor() as executor:
        all_pairs = list(executor.map(lambda w: run_pair(*w), all_work))

    by_stem: dict[str, list[PairResult]] = defaultdict(list)
    for w, p in zip(all_work, all_pairs):
        by_stem[w[0]].append(p)
    results = [TaskResult(stem=stem, pairs=by_stem.get(stem, [])) for stem in stems]

    for r in results:
        marker = "PASS" if r.all_pass else "FAIL"
        print(f"{r.stem}: {r.passes}/{r.total} {marker}")

    failed = [r for r in results if not r.all_pass]
    if failed:
        print()
        print(f"--- {len(failed)} failing solver(s) ---")
        for r in failed:
            print(f"\n{r.stem}:")
            for p in r.pairs:
                if p.ok:
                    continue
                for line in render_pair_failure(p):
                    print(f"  {line}")

    lint_findings: dict[str, list] = {}
    for stem in stems:
        source = (SOLVERS_DIR / f"{stem}.dl").read_text()
        findings = lint_body(source)
        if findings:
            lint_findings[stem] = findings

    if lint_findings:
        print()
        total = sum(len(v) for v in lint_findings.values())
        print(f"--- lint findings: {total} across {len(lint_findings)} solver(s) ---")
        for stem in sorted(lint_findings):
            for cat, lineno, match, line in lint_findings[stem]:
                print(f"  {stem}.dl:L{lineno}: {cat} `{match}`  →  {line.strip()}")

    print()
    print(f"summary: {len(results) - len(failed)}/{len(results)} solvers")
    return 0 if not failed else 1


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.exit(cmd_all())
    if len(sys.argv) == 2:
        sys.exit(cmd_one(sys.argv[1]))
    print(f"usage: {sys.argv[0]} [<task_id_or_stem>]", file=sys.stderr)
    sys.exit(2)
