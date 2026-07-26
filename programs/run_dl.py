"""Run Souffle solvers against their tasks' train+test pairs.

Usage:
    uv run python programs/run_dl.py                    # run all .dl solvers
    uv run python programs/run_dl.py <stem>             # run one
    uv run python programs/run_dl.py --audit <stem>     # fill sweep + mutation report
    uv run python programs/run_dl.py --sweep <stem> [cap]   # conditional fill sweep
    uv run python programs/run_dl.py --mutate <stem>    # structural mutation report

For a single stem, encodes each example's input grid as fact lines on stdin,
invokes `souffle` on it (linking the functor library; see build_functors),
reads the output relation from stdout, compares to expected output grid.

Both CLI paths also lint each solver body (see dl_lint) and print style
findings, and fit-check each solver carrying a `Fit` comp (see run_fit).
"""

import itertools
import re
import signal
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
from programs.dl_lint import lint_body  # noqa: E402

PROGRAMS_DIR = REPO_ROOT / "programs"
SOLVERS_DIR = PROGRAMS_DIR / "solvers"
FUNCTORS_SRC = PROGRAMS_DIR / "lib_functors.cpp"
FUNCTORS_LIB = PROGRAMS_DIR / "libfunctors.dylib"


def build_functors() -> None:
    """Compile lib_functors.cpp to the shared library Souffle loads at runtime.

    Skips when the artifact is newer than the source. Called once before the
    pool spins up — never per-pair, which would race. Solvers can't run without
    it (lib.dl's primitives call its functors), so a failure here is fatal.
    """
    if FUNCTORS_LIB.exists() and FUNCTORS_LIB.stat().st_mtime >= FUNCTORS_SRC.stat().st_mtime:
        return
    souffle_prefix = subprocess.run(
        ["brew", "--prefix", "souffle"], capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(
        ["clang++", "-std=c++17", "-shared", "-fPIC",
         f"-I{souffle_prefix}/include",
         "-o", str(FUNCTORS_LIB), str(FUNCTORS_SRC)],
        check=True,
    )


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


def parse_output(
    stdout: str,
) -> list[tuple[str, list[list[int]], list[tuple[int, int]], list[tuple[int, int]]]]:
    """Parse Souffle's default text output for the `out` relation.

    Returns a list of (variant, grid, conflicts, missing) tuples. Variant is
    the trailing column value (e.g. '$FlipTB') from a Choice ADT, or '' when
    `out` has no trailing column. Cells are grouped by variant; each group
    is one grid. `conflicts` is a sorted list of (t, l) cells that received
    multiple distinct colors within the same variant — an ambiguous output.
    `missing` is a sorted list of (t, l) cells no fact wrote — a partial
    output. An output grid is total, so either list fails the variant.
    """
    parts = re.split(r"^={3,}$", stdout, flags=re.MULTILINE)
    if len(parts) < 3:
        raise ValueError(f"unexpected souffle output:\n{stdout}")
    data = parts[1].strip()
    if not data:
        return [("", [], [], [])]

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

    candidates: list[
        tuple[str, list[list[int]], list[tuple[int, int]], list[tuple[int, int]]]
    ] = []
    for variant in sorted(grouped):
        cells = grouped[variant]
        bounds = {(t + b + 1, l + r + 1) for (t, b, l, r, _) in cells}
        if len(bounds) != 1:
            raise ValueError(f"inconsistent grid bounds in {variant!r}: {bounds}")
        h, w = next(iter(bounds))
        grid = [[-1] * w for _ in range(h)]
        seen: dict[tuple[int, int], int] = {}
        conflicts: set[tuple[int, int]] = set()
        for (t, _, l, _, color) in cells:
            if t < 0 or l < 0 or t >= h or l >= w:
                raise ValueError(f"cell out of derived bounds: ({t}, {l}) in {h}x{w}")
            if (t, l) in seen and seen[(t, l)] != color:
                conflicts.add((t, l))
            seen[(t, l)] = color
            grid[t][l] = color
        missing = sorted(
            (t, l) for t in range(h) for l in range(w) if grid[t][l] == -1
        )
        candidates.append((variant, grid, sorted(conflicts), missing))
    return candidates


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


def expand_grid_macros(source: str) -> str:
    """Prepend `#define GRID_HxW` lines for every (H, W) used in source."""
    dims = {(int(m.group(1)), int(m.group(2))) for m in GRID_MACRO_RE.finditer(source)}
    if not dims:
        return source
    macros = "\n".join(gen_grid_macro(h, w) for (h, w) in sorted(dims))
    return f"// Generated GRID_HxW expansions.\n{macros}\n\n{source}"


# Per-mode IO directives, appended to the built source.
SOLVE_DIRECTIVES = ".input in(IO=stdin)\n.output out(IO=stdout)\n"
FIT_DIRECTIVES = ".input train_in\n.input train_out\n.output fit_diff(IO=stdout)\n"

COMP_HEADER_RE = re.compile(r"\.comp\s+(\w+)")
DECL_RE = re.compile(r"\.decl\s+(\w+)\s*\(([^)]*)\)")


def comp_decls(source: str, comp_name: str) -> dict[str, list[str]]:
    """Map relation name -> argument types for `.decl`s directly inside comp `comp_name`."""
    decls: dict[str, list[str]] = {}
    in_comp = False
    depth = 0
    for line in source.splitlines():
        line = line.split("//")[0]
        if not in_comp:
            m = COMP_HEADER_RE.search(line)
            if m and m.group(1) == comp_name and "{" in line:
                in_comp = True
                depth = line.count("{") - line.count("}")
            continue
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            break
        m = DECL_RE.search(line)
        if m:
            args = m.group(2).strip()
            decls[m.group(1)] = [
                a.split(":")[1].strip() for a in args.split(",") if ":" in a
            ]
    return decls


def fit_slots(source: str) -> dict[str, int] | None:
    """Fitted slots: Fit decls that mirror a Consts decl. None when no Fit comp."""
    fit = comp_decls(source, "Fit")
    if not fit:
        return None
    consts = comp_decls(source, "Consts")
    return {name: len(types) for name, types in fit.items() if name in consts}


def build_source(source: str) -> str:
    """Assemble the solve-mode program from a solver file's source."""
    return f"{expand_grid_macros(source)}\n{SOLVE_DIRECTIVES}"


def build_fit_source(source: str, slots: dict[str, int]) -> str:
    """Assemble the fit-mode program: Fit instance, per-slot diffs, directives."""
    lines = [".init fit = Fit"]
    for name, arity in sorted(slots.items()):
        args = ", ".join(f"A{i}" for i in range(arity))
        lines.append(f'fit_diff("{name}") :- fit.{name}({args}), !c.{name}({args}).')
        lines.append(f'fit_diff("{name}") :- c.{name}({args}), !fit.{name}({args}).')
    appended = "\n".join(lines)
    return f"{expand_grid_macros(source)}\n{appended}\n{FIT_DIRECTIVES}"


def run_dl(
    task_id: str, input_rows: list[list[int]], stem: str | None = None
) -> list[tuple[str, list[list[int]], list[tuple[int, int]], list[tuple[int, int]]]]:
    dl_path = SOLVERS_DIR / f"{stem or task_id}.dl"
    if not dl_path.exists():
        raise FileNotFoundError(f"no .dl solver at {dl_path}")

    return parse_output(
        _run_source(build_source(dl_path.read_text()), grid_to_facts(input_rows))
    )


def _run_source(
    built: str, stdin_text: str, extra_args: list[str] | None = None
) -> str:
    """Write built source to a tempfile and run Souffle on it.

    Tempfile lives next to the originals so `#include "../lib.dl"` resolves.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".dl", dir=str(SOLVERS_DIR), delete=False
    ) as tf:
        tf.write(built)
        run_path = Path(tf.name)
    try:
        return _souffle(run_path, stdin_text, extra_args)
    finally:
        run_path.unlink(missing_ok=True)


def _souffle(
    dl_path: Path, stdin_text: str, extra_args: list[str] | None = None
) -> str:
    # -L/-lfunctors load the functor shared library build_functors compiled —
    # lib.dl's primitives call into it.
    #
    # Two bounds on runaway souffle (some rule shapes can hang the evaluator
    # and exhaust system memory). The kernel CPU-time limit (`ulimit -t`, via
    # a sh wrapper — preexec_fn is unsafe under threads) counts only souffle's
    # own burn, so system load and EDR spawn stalls can't fake a failure. The
    # wall timeout backstops hangs that block without spinning; it can be
    # raised if it ever false-positives, but stays low so inefficient solvers
    # surface.
    cmd = ["souffle", "-D-", "-w", "-L", str(PROGRAMS_DIR), "-lfunctors",
           *(extra_args or []), str(dl_path)]
    result = subprocess.run(
        ["/bin/sh", "-c", 'ulimit -t 5; exec "$0" "$@"', *cmd],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == -signal.SIGXCPU:
        raise RuntimeError(f"souffle exceeded the 5s CPU limit on {dl_path.name}")
    if result.returncode != 0:
        raise RuntimeError(f"souffle exited {result.returncode}:\n{result.stderr}")
    return result.stdout


# ---------------------------------------------------------------- sweep

def _lib_defines() -> dict[str, int]:
    """Constant-name -> value from lib.dl's #define table."""
    text = (PROGRAMS_DIR / "lib.dl").read_text()
    return {m.group(1): int(m.group(2))
            for m in re.finditer(r"^#define (\w+) (\d+)", text, flags=re.MULTILINE)}


ENUM_TYPES = {
    "Dir": "DIR_", "Axis": "AXIS_", "DiagDir": "DIAG_",
    "DiagAxis": "DAXIS_", "D4": "D4_", "Sense": "SENSE_",
}


def _enum_domain(type_name: str, defines: dict[str, int]) -> list[int]:
    prefix = ENUM_TYPES[type_name]
    return sorted(v for k, v in defines.items() if k.startswith(prefix))


def _color_domain(task) -> list[int]:
    """Colors present in the train pairs."""
    colors: set[int] = set()
    for ex in task.train:
        for grid in (ex.input, ex.output):
            for row in grid:
                colors.update(row)
    return sorted(colors)


def _number_domain(task) -> list[int]:
    """0..max train grid dimension — the range of task-shape numbers."""
    dims = [
        d
        for ex in task.train
        for grid in (ex.input, ex.output)
        for d in (len(grid), len(grid[0]) if grid else 0)
    ]
    return list(range(max(dims) + 1))


def _comp_span(source: str, comp_name: str) -> tuple[int, int]:
    """[start, end) line indices of comp `comp_name`'s interior; (0, 0) when absent."""
    lines = source.splitlines()
    depth = 0
    start = None
    for i, raw in enumerate(lines):
        code = raw.split("//")[0]
        if start is None:
            if re.search(rf"\.comp\s+{comp_name}\b", code) and "{" in code:
                depth = code.count("{") - code.count("}")
                start = i + 1
            continue
        depth += code.count("{") - code.count("}")
        if depth <= 0:
            return (start, i)
    return (0, 0)


def _consts_fact_lines(source: str) -> list[int]:
    """Line indices inside Consts outside any rule statement.

    A slot atom can also close a Consts rule (`x(N) :- fat(N).`), where it
    reads like a fact; fact matching stays off rule lines.
    """
    lines = source.splitlines()
    s, e = _comp_span(source, "Consts")
    idxs = []
    in_rule = False
    for i in range(s, e):
        code = lines[i].split("//")[0]
        if not in_rule and ":-" in code:
            in_rule = True
        if in_rule:
            if code.rstrip().endswith("."):
                in_rule = False
            continue
        idxs.append(i)
    return idxs


def _slot_facts(source: str, slot: str) -> list[str]:
    """Fact atoms for `slot` inside the Consts block."""
    lines = source.splitlines()
    pat = re.compile(rf"\b{slot}\s*\([^)]*\)\s*\.")
    return [
        m.group(0)
        for i in _consts_fact_lines(source)
        for m in pat.finditer(lines[i].split("//")[0])
    ]


def swap_fact(source: str, slot: str, values: tuple) -> str:
    """Replace `slot`'s Consts facts with a single fact holding `values`."""
    lines = source.splitlines()
    _, e = _comp_span(source, "Consts")
    pat = re.compile(rf"\b{slot}\s*\([^)]*\)\s*\.")
    for i in _consts_fact_lines(source):
        code, sep, comment = lines[i].partition("//")
        lines[i] = pat.sub("", code) + sep + comment
    args = ", ".join(str(v) for v in values)
    lines.insert(e, f"    {slot}({args}).")
    return "\n".join(lines) + "\n"


def _profile(mod_source: str, examples: list) -> list[frozenset[str]] | None:
    """Per-pair variant-name sets under this source; None on any failure.

    A modified source must reproduce the original's profile, not merely
    pass: a wrong fill or a deleted rule can silence a Choice case, and a
    vanished variant is never checked.
    """
    profile = []
    for ex in examples:
        try:
            actuals = parse_output(
                _run_source(build_source(mod_source), grid_to_facts(ex.input))
            )
        except Exception:
            return None
        accepted = [ex.output]
        if ex.alt is not None and ex.alt.kind == "tiebreak":
            accepted.append(ex.alt.grid)
        names = set()
        for variant, grid, conflicts, missing in actuals:
            if grid not in accepted or conflicts or missing:
                return None
            names.add(variant)
        profile.append(frozenset(names))
    return profile


def sweep_report(
    stem: str, max_candidates: int = 64
) -> list[tuple[str, str, object]]:
    """Conditional sweep of each enumerable Consts slot.

    Sweeps one slot at a time with the others at their stored values; a
    candidate survives when it reproduces the stored fill's variant profile
    on every train pair. A slot's fill may be a set (a symmetric member
    stores every fitting value), so the check is survivors == stored facts.

    Survivors beyond the stored facts are re-run against the test pairs:
    a producer holding only the train pairs could pick any survivor, so an
    extra that fails test is a would-be wrong prediction, and one that
    passes is gauge for this task instance.

    Returns (slot, status, detail): status 'swept' carries
    (survivors, stored, types, verdicts) — verdicts maps each extra
    survivor to its test-pass bool — 'skip' carries the reason.
    """
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    task = load_task(stem.split("_", 1)[0])
    defines = _lib_defines()
    s, e = _comp_span(source, "Consts")
    consts_text = "\n".join(source.splitlines()[s:e])

    reference: list[frozenset[str]] | None = None
    test_reference: list[frozenset[str]] | None = None
    results: list[tuple[str, str, object]] = []
    for slot, types in comp_decls(source, "Consts").items():
        if re.search(rf"\b{slot}\s*\([^)]*\)\s*:-", consts_text):
            results.append((slot, "skip", "derived"))
            continue
        facts = _slot_facts(source, slot)
        if not facts:
            results.append((slot, "skip", "0 facts"))
            continue
        domains = []
        for t in types:
            if t in ENUM_TYPES:
                domains.append(_enum_domain(t, defines))
            elif t == "Color":
                domains.append(_color_domain(task))
            elif t == "number":
                domains.append(_number_domain(task))
            else:
                domains = None
                break
        if domains is None:
            results.append((slot, "skip", f"non-enumerable ({', '.join(types)})"))
            continue

        stored = []
        for fact in facts:
            args = re.match(rf"{slot}\s*\(([^)]*)\)", fact).group(1)
            stored.append(tuple(
                int(a) if a.strip().lstrip("-").isdigit() else defines[a.strip()]
                for a in args.split(",")
            ))

        # Stored values join the candidate set, so a stored value outside
        # the domain (a count above the dims, say) still reads as stored
        # rather than as a holistic table.
        candidates = sorted(set(itertools.product(*domains)) | set(stored))
        if len(candidates) > max_candidates:
            results.append((slot, "skip", f"{len(candidates)} candidates"))
            continue

        if reference is None:
            reference = _profile(source, task.train)
            if reference is None:
                results.append((slot, "skip", "stored fill fails train"))
                continue

        def test(vals, slot=slot):
            profile = _profile(swap_fact(source, slot, vals), task.train)
            return vals if profile == reference else None

        with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
            survivors = [v for v in executor.map(test, candidates) if v]

        verdicts: dict[tuple, bool] = {}
        extras = sorted(set(survivors) - set(stored))
        if extras and set(stored) <= set(survivors):
            if test_reference is None:
                test_reference = _profile(source, task.test)
            if test_reference is None:
                verdicts = {e: False for e in extras}
            else:
                def test_check(vals, slot=slot):
                    profile = _profile(swap_fact(source, slot, vals), task.test)
                    return profile == test_reference

                with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
                    verdicts = dict(zip(extras, executor.map(test_check, extras)))
        results.append((slot, "swept", (survivors, stored, types, verdicts)))
    return results


def _num_peer(e: tuple, s: tuple, types: list[str]) -> bool:
    """e differs from s only in number args — a rival magnitude, not a
    rival identity. Nominal args (enums, Color, Ident) must match."""
    return all(e[i] == s[i] for i, t in enumerate(types) if t != "number")


def _num_below(e: tuple, s: tuple, types: list[str]) -> bool:
    """e is a smaller magnitude reading of s: nominal args equal, number
    args no larger, at least one strictly smaller."""
    nums = [i for i, t in enumerate(types) if t == "number"]
    return (_num_peer(e, s, types)
            and all(e[i] <= s[i] for i in nums)
            and any(e[i] < s[i] for i in nums))


def render_sweep(results: list[tuple[str, str, object]]) -> list[str]:
    defines = _lib_defines()
    names = {v: k for k, v in defines.items()}

    def show(vals: tuple, types: list[str]) -> str:
        return "(" + ", ".join(
            names.get(v, str(v)) if t in ENUM_TYPES else str(v)
            for v, t in zip(vals, types)
        ) + ")"

    lines = []
    for slot, status, detail in results:
        if status == "skip":
            lines.append(f"{slot}: skipped — {detail}")
            continue
        survivors, stored, types, verdicts = detail
        vset, sset = set(survivors), set(stored)
        shown_s = ", ".join(show(v, types) for v in stored)
        if vset == sset:
            if len(sset) == 1:
                lines.append(f"{slot}: unique = {shown_s} ✓")
            else:
                lines.append(f"{slot}: set of {len(sset)} = [{shown_s}] ✓")
        elif sset <= vset:
            extras = sorted(vset - sset)
            shown_e = ", ".join(show(v, types) for v in extras)
            falsified = [e for e in extras if not verdicts.get(e, False)]
            if falsified:
                shown_f = ", ".join(show(v, types) for v in falsified)
                lines.append(
                    f"{slot}: TEST-FALSIFIED — train admits [{shown_f}] "
                    f"beyond stored [{shown_s}], test refutes"
                )
            elif not all(any(_num_peer(e, s, types) for s in sset)
                         for e in extras):
                lines.append(
                    f"{slot}: UNDERDETERMINED — beyond stored [{shown_s}]: [{shown_e}]"
                )
            elif any(_num_below(e, s, types) for e in extras for s in sset):
                below = sorted(
                    e for e in extras if any(_num_below(e, s, types) for s in sset)
                )
                shown_b = ", ".join(show(v, types) for v in below)
                lines.append(
                    f"{slot}: STORED NOT LEAST — smaller fitting: [{shown_b}]"
                )
            else:
                lines.append(f"{slot}: stored {shown_s} ✓ — gauge [{shown_e}]")
        else:
            # Some stored value no singleton run reproduces.
            lines.append(f"{slot}: holistic table — singleton sweep n/a")
    return lines


# ---------------------------------------------------------------- mutate

NEG_ATOM_RE = re.compile(r"(?<![=!])!(?!=)\s*[\w.]+\s*\(")


def _rule_spans(source: str) -> list[tuple[int, int]]:
    """Inclusive line spans of rules, Fit comp excluded.

    Style-parsed: head and `:-` share the first line; `.` ends the statement.
    """
    lines = source.splitlines()
    fs, fe = _comp_span(source, "Fit")
    fit = set(range(fs - 1, fe + 1)) if (fs, fe) != (0, 0) else set()
    spans = []
    i = 0
    while i < len(lines):
        code = lines[i].split("//")[0]
        if i in fit or ":-" not in code or code.lstrip().startswith("."):
            i += 1
            continue
        j = i
        while j < len(lines) and not lines[j].split("//")[0].rstrip().endswith("."):
            j += 1
        if j == len(lines):
            break
        spans.append((i, j))
        i = j + 1
    return spans


def _drop_atom(code: str, start: int, end: int) -> str:
    """Remove code[start:end] plus one adjoining comma separator."""
    after = code[end:].lstrip()
    if after.startswith(","):
        return code[:start] + after[1:].lstrip()
    before = code[:start].rstrip()
    if before.endswith(","):
        return before[:-1] + code[end:]
    return code[:start] + code[end:]


def mutants(source: str):
    """Yield (lineno, kind, text, mutated_source) structural mutants.

    Kinds: 'rule' deletes the whole rule; 'negation' deletes one negated
    body atom (the mutated rule collapses to one line). The Fit comp does
    not run in solve mode, so it is not mutated.
    """
    lines = source.splitlines()
    for a, b in _rule_spans(source):
        rule = " ".join(ln.split("//")[0].strip() for ln in lines[a:b + 1])
        head = rule.split(":-")[0].strip()
        yield (a + 1, "rule", head, "\n".join(lines[:a] + lines[b + 1:]) + "\n")
        for m in NEG_ATOM_RE.finditer(rule):
            depth, k = 0, m.end() - 1
            while k < len(rule):
                if rule[k] == "(":
                    depth += 1
                elif rule[k] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            atom = rule[m.start():k + 1]
            mutated = lines[:a] + [_drop_atom(rule, m.start(), k + 1)] + lines[b + 1:]
            yield (a + 1, "negation", atom, "\n".join(mutated) + "\n")


def mutation_report(stem: str) -> tuple[int, list[tuple[int, str, str]]] | None:
    """Structural mutants that survive every train+test pair.

    A surviving mutant keeps the full variant profile without the deleted
    structure: the pairs never instantiate it. Informational — a survivor
    points at an unwitnessed guard or rule, not a violation. None when the
    stored source itself fails.
    """
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    task = load_task(stem.split("_", 1)[0])
    examples = list(task.train) + list(task.test)
    reference = _profile(source, examples)
    if reference is None:
        return None
    muts = list(mutants(source))

    def test(m):
        lineno, kind, text, mod = m
        return (lineno, kind, text) if _profile(mod, examples) == reference else None

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        survivors = [r for r in executor.map(test, muts) if r]
    return (len(muts), sorted(survivors))


def train_facts(task) -> dict[str, str]:
    """Fact-file contents for a task's train pairs, example-keyed."""
    def emit(grids: list[list[list[int]]]) -> str:
        return "".join(
            f"{e}\t{line}\n"
            for e, rows in enumerate(grids)
            for line in grid_to_facts(rows).splitlines()
        )
    return {
        "train_in.facts": emit([ex.input for ex in task.train]),
        "train_out.facts": emit([ex.output for ex in task.train]),
    }


def _parse_block(stdout: str) -> list[str]:
    """Rows of the single relation block in Souffle's -D- output."""
    parts = re.split(r"^={3,}$", stdout, flags=re.MULTILINE)
    if len(parts) < 3:
        raise ValueError(f"unexpected souffle output:\n{stdout}")
    data = parts[1].strip()
    return [line for line in data.splitlines() if line] if data else []


@dataclass
class FitResult:
    slots: list[str]        # fitted (Consts-mirrored) Fit relations
    unfitted: list[str]     # Consts slots with no Fit mirror
    diff: list[str]         # slots where fit and fill disagree
    error: str | None = None


def run_fit(stem: str) -> FitResult | None:
    """Fit check for one solver; None when the file has no Fit comp."""
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    slots = fit_slots(source)
    if slots is None:
        return None
    unfitted = sorted(set(comp_decls(source, "Consts")) - set(slots))
    task = load_task(stem.split("_", 1)[0])
    try:
        with tempfile.TemporaryDirectory() as facts_dir:
            for name, text in train_facts(task).items():
                (Path(facts_dir) / name).write_text(text)
            stdout = _run_source(
                build_fit_source(source, slots), "", ["-F", facts_dir]
            )
        diff = sorted({row.strip() for row in _parse_block(stdout)})
        return FitResult(slots=sorted(slots), unfitted=unfitted, diff=diff)
    except Exception as e:
        return FitResult(
            slots=sorted(slots), unfitted=unfitted, diff=[],
            error=f"{type(e).__name__}: {e}",
        )


def render_fit(fit: FitResult) -> list[str]:
    if fit.error:
        lines = [f"fit: ERROR {fit.error}"]
    elif fit.diff:
        lines = [f"fit: DIFF on {', '.join(fit.diff)}"]
    else:
        lines = [f"fit: ok ({', '.join(fit.slots)})"]
    if fit.unfitted:
        lines.append(f"fit: unfitted slots: {', '.join(fit.unfitted)}")
    return lines


@dataclass
class VariantResult:
    name: str  # '' when out has no trailing column
    ok: bool
    actual: list[list[int]]
    conflicts: list[tuple[int, int]] = field(default_factory=list)
    missing: list[tuple[int, int]] = field(default_factory=list)


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


def case_coverage(pairs: list[PairResult]) -> list[str]:
    """Cases silent on some pair. A case is a complete model, so the
    emitted variant set must be the same across all pairs."""
    sets: dict[str, set[str]] = {}
    for p in pairs:
        if p.error or not p.variants:
            return []  # pair-level failure already reported
        sets[f"{p.kind}[{p.idx}]"] = {v.name for v in p.variants}
    union = set().union(*sets.values())
    return [
        f"case {name or '(out)'} silent on {pair}"
        for pair, s in sorted(sets.items())
        for name in sorted(union - s)
    ]


def run_pair(stem: str, task_id: str, kind: str, idx: int, ex) -> PairResult:
    try:
        actuals = run_dl(task_id, ex.input, stem=stem)
        accepted: list[list[list[int]]] = [ex.output]
        if ex.alt is not None and ex.alt.kind == "tiebreak":
            accepted.append(ex.alt.grid)
        variants = [
            VariantResult(
                name=v,
                ok=(g in accepted) and not c and not m,
                actual=g,
                conflicts=c,
                missing=m,
            )
            for v, g, c, m in actuals
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


def _pool_workers() -> int | None:
    """Cap Souffle-spawning pools at the performance-core count.

    A full sweep queues hundreds of CPU-bound Souffle processes; the default
    pool size (cores + 4) oversubscribes onto efficiency cores and inflates
    wall times.
    """
    try:
        out = subprocess.run(
            ["sysctl", "-n", "hw.perflevel0.logicalcpu"],
            capture_output=True, text=True, check=True,
        )
        return int(out.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None  # no asymmetric cores to avoid: default sizing


def run_task(stem: str) -> TaskResult:
    """Single-task entry: pairs run in parallel."""
    work = _pair_work(stem)
    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
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

    # Group failing variants by (actual output, conflict cells, missing cells)
    # so duplicates share one diff block.
    groups: dict[tuple, list[str]] = defaultdict(list)
    for v in p.variants:
        if v.ok:
            continue
        key = (
            tuple(tuple(r) for r in v.actual) if v.actual else (),
            tuple(v.conflicts),
            tuple(v.missing),
        )
        groups[key].append(v.name or "(out)")

    for (actual_key, conflicts_tup, missing_tup), names in groups.items():
        actual = [list(r) for r in actual_key]
        lines.append("")
        if has_named or multi:
            lines.append(f"  {', '.join(names)}:")
        if conflicts_tup:
            lines.append(f"    conflicts at: {list(conflicts_tup)}")
        if missing_tup:
            lines.append(f"    missing cells at: {list(missing_tup)}")
        if not conflicts_tup and not missing_tup:
            for dl in render_diff(p.expected or [], actual):
                lines.append(f"    {dl}")

    return lines


def all_stems() -> list[str]:
    return sorted(p.stem for p in SOLVERS_DIR.glob("*.dl"))


def cmd_one(stem: str) -> int:
    build_functors()
    result = run_task(stem)
    for p in result.pairs:
        if p.ok:
            n = len(p.variants)
            suffix = f" ({n} variants)" if n > 1 else ""
            print(f"{p.kind}[{p.idx}]: PASS{suffix}")
        else:
            for line in render_pair_failure(p):
                print(line)

    coverage = case_coverage(result.pairs)
    if coverage:
        print()
        print(f"--- {len(coverage)} case-coverage finding(s) in {stem}.dl ---")
        for line in coverage:
            print(f"  {line}")

    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    findings = lint_body(source)
    if findings:
        print()
        print(f"--- {len(findings)} lint finding(s) in {stem}.dl ---")
        for cat, lineno, match, line in findings:
            print(f"  L{lineno}: {cat} `{match}`  →  {line.strip()}")

    fit = run_fit(stem)
    if fit is not None:
        print()
        for line in render_fit(fit):
            print(line)

    return 0 if result.all_pass else 1


def cmd_all() -> int:
    build_functors()
    stems = all_stems()

    # Flatten all (stem, pair) work so the pool sees one big queue.
    all_work: list[tuple] = []
    for stem in stems:
        all_work.extend(_pair_work(stem))

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        all_pairs = list(executor.map(lambda w: run_pair(*w), all_work))

    by_stem: dict[str, list[PairResult]] = defaultdict(list)
    for w, p in zip(all_work, all_pairs, strict=True):
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

    coverage_findings = {
        r.stem: cov for r in results if (cov := case_coverage(r.pairs))
    }
    if coverage_findings:
        print()
        total = sum(len(v) for v in coverage_findings.values())
        print(f"--- case-coverage findings: {total} across "
              f"{len(coverage_findings)} solver(s) ---")
        for stem in sorted(coverage_findings):
            for line in coverage_findings[stem]:
                print(f"  {stem}.dl: {line}")

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

    fit_results: dict[str, FitResult] = {}
    for stem in stems:
        r = run_fit(stem)
        if r is not None:
            fit_results[stem] = r
    if fit_results:
        problems = {
            s: r for s, r in fit_results.items() if r.diff or r.error or r.unfitted
        }
        print()
        ok = len(fit_results) - len(problems)
        print(f"--- fit checks: {ok}/{len(fit_results)} ok ---")
        for s in sorted(problems):
            for line in render_fit(problems[s]):
                print(f"  {s}.dl: {line}")

    print()
    print(f"summary: {len(results) - len(failed)}/{len(results)} solvers")
    return 0 if not failed else 1


def cmd_sweep(stem: str, max_candidates: int = 64) -> int:
    build_functors()
    for line in render_sweep(sweep_report(stem, max_candidates)):
        print(line)
    return 0


def _print_mutation(stem: str) -> int:
    report = mutation_report(stem)
    if report is None:
        print("baseline fails: stored source does not pass train+test")
        return 1
    total, survivors = report
    if not survivors:
        print(f"no surviving mutants ({total} tested)")
    else:
        print(f"{len(survivors)}/{total} mutants survive:")
        for lineno, kind, text in survivors:
            print(f"  L{lineno}: {kind} `{text}`")
    return 0


def cmd_mutate(stem: str) -> int:
    build_functors()
    return _print_mutation(stem)


def cmd_audit(stem: str) -> int:
    """Both evidence audits of a finished solver: fill sweep + mutation."""
    build_functors()
    print("--- sweep ---")
    for line in render_sweep(sweep_report(stem)):
        print(line)
    print()
    print("--- mutation ---")
    return _print_mutation(stem)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.exit(cmd_all())
    if len(sys.argv) == 2:
        sys.exit(cmd_one(sys.argv[1]))
    if len(sys.argv) == 3 and sys.argv[1] == "--sweep":
        sys.exit(cmd_sweep(sys.argv[2]))
    if len(sys.argv) == 4 and sys.argv[1] == "--sweep":
        sys.exit(cmd_sweep(sys.argv[2], int(sys.argv[3])))
    if len(sys.argv) == 3 and sys.argv[1] == "--mutate":
        sys.exit(cmd_mutate(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] == "--audit":
        sys.exit(cmd_audit(sys.argv[2]))
    print(
        f"usage: {sys.argv[0]} "
        "[--audit <stem> | --sweep <stem> [cap] | --mutate <stem> | <stem>]",
        file=sys.stderr,
    )
    sys.exit(2)
