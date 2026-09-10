"""Commands the runner exposes, and the argv dispatch over them."""

import argparse
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from arc.task import Alt, Example
from dl.corpus import literal_count
from dl.deletions import deletion_report, render_deletions
from dl.derived_constant import derived_constant_report, render_derived_constant
from dl.determination_plan import probe_report, render_determination_plan
from dl.determine import DetermineResult, render_determine, run_determine
from dl.dlparse import ParseError, TypeDecl, parse
from dl.drop_one import drop_one_report, render_drop_one
from dl.facts import parse_grid
from dl.lint import LIB_NAME_CAT, RESERVED_CAT, SHADOWED_TYPE_CAT, lint_program
from dl.paths import REPO_ROOT, SOLVERS_DIR, all_stems
from dl.render import _grid_lines, render_pair_failure, render_stem_failures
from dl.rewrite_lint import HINTS, lint_rewrites
from dl.solve import (
    PairResult,
    TaskResult,
    _pair_work,
    case_coverage,
    compile_error,
    res_out_stem,
    run_dl,
    run_pair,
    run_task,
)
from dl.souffle import _pool_workers, build_functors
from dl.source import expand_macros
from dl.sweep import MAX_CANDIDATES, render_sweep, sweep_report

type Findings = list[tuple[str, int, str, str]]

LINT_TIERS = ("lint", "rewrite", "hint")


def _lint_tiers(source: str, hints: bool) -> list[Findings]:
    """Findings per tier, in LINT_TIERS order; the hint tier is empty
    unless enabled."""
    style: Findings = lint_program(source)
    dec: Findings = []
    adv: Findings = []
    for f in lint_rewrites(source, hints):
        (adv if f[0] in HINTS else dec).append(f)
    return [style, dec, adv]


def _finding_line(stem: str, tier: str, cat: str, lineno: int, match: str) -> str:
    if tier == "lint" and " " not in match:
        match = f"`{match}`"  # a bare code fragment; a sentence quotes itself
    return f"{stem}.dl:{lineno}: {cat}: {match}"


def _lint_verdict(counts: list[int]) -> str | None:
    """The verdict line for per-tier finding counts in LINT_TIERS order;
    None when a lint or rewrite finding stands. The hint tier is
    advisory: the corpus both inlines and keeps its shapes, so a hint
    is a call the session makes, and it counts toward neither the
    verdict nor the exit code."""
    style, dec, adv = counts
    if style or dec:
        return None
    if adv:
        return f"lint: ok, {adv} hint{'s' if adv > 1 else ''}"
    return "lint: ok"


def _print_findings(stems: list[str], hints: bool) -> str | None:
    """Print the tier sections for `stems`; return the verdict line."""
    by_tier: list[dict[str, Findings]] = [{}, {}, {}]
    for stem in stems:
        source = (SOLVERS_DIR / f"{stem}.dl").read_text()
        for held, tier in zip(by_tier, _lint_tiers(source, hints),
                              strict=True):
            if tier:
                held[stem] = tier

    counts = [sum(len(v) for v in held.values()) for held in by_tier]
    for label, held, count in zip(LINT_TIERS, by_tier, counts, strict=True):
        if not held:
            continue
        print()
        print(f"--- {label} findings: {count} across {len(held)} solver(s) ---")
        for stem in sorted(held):
            for cat, lineno, match, _ in held[stem]:
                print(f"  {_finding_line(stem, label, cat, lineno, match)}")
    return _lint_verdict(counts)


def cmd_lint(
    stem: str | None, hints: bool = False,
) -> int:
    """Lint only: no solver runs, no determination checks, no Souffle needed."""
    if stem is not None and _missing(stem):
        return 2
    verdict = _print_findings([stem] if stem else all_stems(), hints)
    if verdict is None:
        return 1
    print(verdict)
    return 0


def _missing(stem: str) -> bool:
    if (SOLVERS_DIR / f"{stem}.dl").exists():
        return False
    print(f"no solver at {SOLVERS_DIR / f'{stem}.dl'}", file=sys.stderr)
    return True


def _compile_failed(stem: str) -> bool:
    """Print a source-level Souffle error, once, before anything runs it.

    Every grid the solver would see fails on the same error, so the pair
    loop and the determination check would each print another copy of it. Souffle
    decides; a reserved name or a shadowed type argument prints beside its
    message, since that message names a token class or a rule variable
    where the collision is what the author has to read."""
    err = compile_error(stem)
    if err is None:
        return False
    print(f"{stem}.dl: {err}")
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    collisions = [f for f in lint_program(source)
                  if f[0] in (RESERVED_CAT, SHADOWED_TYPE_CAT, LIB_NAME_CAT)]
    if collisions:
        print("likely cause:")
        for cat, lineno, match, _ in collisions:
            print(f"  {_finding_line(stem, 'lint', cat, lineno, match)}")
    return True


def _print_lint_tiers(stem: str, hints: bool) -> str | None:
    """Print one solver's tier sections; return the verdict line. Lint
    needs no Souffle, so it stands whether or not the solver compiles."""
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    tiers = _lint_tiers(source, hints)
    for label, findings in zip(LINT_TIERS, tiers, strict=True):
        if not findings:
            continue
        print()
        print(f"--- {len(findings)} {label} finding(s) ---")
        for cat, lineno, match, _ in findings:
            print(f"  {_finding_line(stem, label, cat, lineno, match)}")
    return _lint_verdict([len(t) for t in tiers])


def cmd_one(stem: str, hints: bool = False, timed: bool = False) -> int:
    if _missing(stem):
        return 2
    build_functors()
    if _compile_failed(stem):
        verdict = _print_lint_tiers(stem, hints)
        print()
        if verdict is not None:
            print(verdict)
        return 1
    t0 = time.perf_counter()
    result = run_task(stem)
    pair_secs = time.perf_counter() - t0
    for p in result.pairs:
        if p.ok:
            n = len(p.variants)
            suffix = f" ({n} variants)" if n > 1 else ""
            print(f"{p.kind}[{p.idx}]: PASS{suffix}")
        else:
            for line in render_pair_failure(p, stem):
                print(line)

    coverage = [] if res_out_stem(stem) else case_coverage(result.pairs)
    if coverage:
        print()
        print(f"--- {len(coverage)} case-coverage finding(s) in {stem}.dl ---")
        for line in coverage:
            print(f"  {line}")

    verdict = _print_lint_tiers(stem, hints)

    t0 = time.perf_counter()
    determination = run_determine(stem)
    determine_secs = time.perf_counter() - t0
    print()
    if verdict is not None:
        print(verdict)
    if determination is not None:
        for line in render_determine(determination):
            print(line)

    if timed:
        parts = [f"pairs {pair_secs:.1f}s"]
        if determination is not None:
            parts.append(f"determination {determine_secs:.1f}s")
        print()
        print(f"time: {', '.join(parts)}")

    return 0 if result.all_pass else 1


def cmd_pairs(stem: str, path: str) -> int:
    """Run one solver against ad-hoc pairs from a JSON file, in place of the
    stored task: either a {train, test} object or a bare list of examples.
    An example without "output" is a probe — its emitted grids print instead
    of a comparison."""
    if _missing(stem):
        return 2
    p = Path(path)
    if not p.exists():
        print(f"no pairs file at {p}", file=sys.stderr)
        return 2
    data = json.loads(p.read_text())
    sections = ([("pair", data)] if isinstance(data, list)
                else [(k, data.get(k) or []) for k in ("train", "test")])
    build_functors()
    if _compile_failed(stem):
        return 1
    task_id = stem.split("_", 1)[0]
    failed = False
    for kind, examples in sections:
        for idx, e in enumerate(examples):
            if e.get("output") is None:
                for c in run_dl(task_id, e["input"], stem=stem):
                    print(f"{kind}[{idx}] {c.variant or '(out)'}:")
                    if c.error:
                        print(f"  {c.error}")
                        continue
                    for line in _grid_lines(c.grid):
                        print(f"  {line}")
                    if c.conflicts or c.missing:
                        print(f"  conflicts {len(c.conflicts)}, "
                              f"missing {len(c.missing)}")
                continue
            alt = (Alt(kind=e["alt"]["kind"], grid=e["alt"]["grid"])
                   if "alt" in e else None)
            ex = Example(input=e["input"], output=e["output"], alt=alt)
            r = run_pair(stem, task_id, kind, idx, ex)
            if r.ok:
                n = len(r.variants)
                suffix = f" ({n} variants)" if n > 1 else ""
                print(f"{kind}[{idx}]: PASS{suffix}")
            else:
                failed = True
                for line in render_pair_failure(r, stem):
                    print(line)
    return 1 if failed else 0


GRID_HELP = """\
Grid format: one line per row, one character per cell — a digit 0-9, or `.`
for 0. Spaces and commas between cells are optional; blank lines and lines
starting with `#` are skipped. Text starting with `[` is read as JSON, so a
grid pasted out of a task file works unchanged.

    uv run python scripts/run_dl.py grid 1b60fb0c <<'EOF'
    . 1 .
    1 1 .
    . . .
    EOF

Each case of the solver's Choice prints its own grid, which is what a
divergence witness needs: one input, one output per case.

Without the runner, the same run by hand. `-L programs` is what loads
libfunctors.dylib, which lib.dl's primitives call, and the built file has to
sit in programs/solvers/ for `#include "../lib.dl"` to resolve:

    { cat programs/solvers/<stem>.dl
      echo '.input in(IO=stdin)'
      echo '.output out(IO=stdout)'
    } > programs/solvers/.tmp.dl
    souffle -D- -w -L programs -lfunctors programs/solvers/.tmp.dl

Souffle then reads one fact line per cell on stdin, `[top, bottom, left,
right]`, a tab, then the color — so the 3x3 grid above starts with

    [0, 2, 0, 2]<TAB>0
    [0, 2, 1, 1]<TAB>1

A solver with GRID or RIGID call sites needs dl.source.expand_macros over
the source first; the runner does that for you.
"""


def _case_branches(stem: str) -> list[str]:
    """The branch names of the solver's Choice ADT, in source order. A solver
    with one case has no Choice, and gets no branches."""
    try:
        program = parse((SOLVERS_DIR / f"{stem}.dl").read_text())
    except (OSError, ParseError):
        return []
    return [
        b
        for it in program.items
        if isinstance(it, TypeDecl) and it.name == "Choice"
        for b in it.branches
    ]


def cmd_grid(stem: str, path: str | None = None) -> int:
    """Run one solver on a grid the caller wrote, in place of a stored pair,
    and print what each case emits."""
    if _missing(stem):
        return 2
    if path in (None, "-"):
        text = sys.stdin.read()
    else:
        p = Path(str(path))
        if not p.exists():
            print(f"no grid file at {p}", file=sys.stderr)
            return 2
        text = p.read_text()
    try:
        grid = parse_grid(text)
    except (ValueError, json.JSONDecodeError, TypeError) as e:
        print(f"bad grid: {e}", file=sys.stderr)
        return 2

    build_functors()
    if _compile_failed(stem):
        return 1
    try:
        actuals = run_dl(stem.split("_", 1)[0], grid, stem=stem)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print("input:")
    for line in _grid_lines(grid):
        print(f"  {line}")
    for c in actuals:
        print()
        print(f"{c.variant or '(out)'}:")
        if c.error:
            print(f"  {c.error}")
            continue
        for line in _grid_lines(c.grid):
            print(f"  {line}")
        if c.conflicts:
            print(f"  conflicts at: {c.conflicts}")
        if c.missing:
            print(f"  missing cells at: {c.missing}")

    emitted = {c.variant.split("(", 1)[0].removeprefix("$") for c in actuals}
    silent = [b for b in _case_branches(stem) if b not in emitted]
    if silent:
        print()
        for name in silent:
            print(f"${name}: emits nothing")
    cases = len(actuals) + len(silent)
    if cases > 1:
        distinct = {tuple(tuple(row) for row in c.grid)
                    for c in actuals if not c.error}
        print()
        print(f"{cases} cases, {len(distinct)} distinct grid(s)")
    return 0


SOLVER_PATH_RE = re.compile(r"programs/solvers/([^/]+)\.dl$")


def _git(*args: str) -> str | None:
    """Git's stdout, or None when the call fails."""
    run = subprocess.run(["git", *args], cwd=REPO_ROOT,
                         capture_output=True, text=True)
    return run.stdout if run.returncode == 0 else None


def _commit_stems(log: str) -> list[set[str]]:
    """The solver stems each commit touches, one set per commit, from
    `git log --name-only` output."""
    commits: list[set[str]] = []
    for line in log.splitlines():
        if line.startswith("commit "):
            commits.append(set())
        elif (m := SOLVER_PATH_RE.match(line.strip())) and commits:
            commits[-1].add(m.group(1))
    return commits


def _worktree_stems(status: str) -> set[str]:
    """The solver stems with an uncommitted or untracked change, from
    `git status --porcelain` output."""
    stems = set()
    for line in status.splitlines():
        path = line[3:].strip().split(" -> ")[-1].strip('"')
        if m := SOLVER_PATH_RE.match(path):
            stems.add(m.group(1))
    return stems


def cmd_since(when: str) -> int:
    """Print the solver stems a survey since `when` covers: the ones the
    commits since then touch, plus the ones whose working-tree content differs
    from HEAD. A commit touching more than half the corpus is a corpus-wide
    mechanical rewrite, and the solvers it touches are out of scope."""
    log = _git("log", f"--since={when}", "--name-only", "--pretty=format:commit %H",
               "--", "programs/solvers")
    status = _git("status", "--porcelain", "--", "programs/solvers")
    if log is None or status is None:
        print(f"git found no history for {when!r}", file=sys.stderr)
        return 1
    corpus = set(all_stems())
    stems: set[str] = _worktree_stems(status)
    for touched in _commit_stems(log):
        if len(touched) * 2 <= len(corpus):
            stems |= touched
    for stem in sorted(stems & corpus):
        print(stem)
    return 0


def cmd_all(hints: bool = False, timed: bool = False) -> int:
    build_functors()
    stems = all_stems()

    # Flatten all (stem, pair) work so the pool sees one big queue.
    all_work: list[tuple] = []
    for stem in stems:
        all_work.extend(_pair_work(stem))

    def timed_pair(w) -> tuple[PairResult, float]:
        t0 = time.perf_counter()
        return run_pair(*w), time.perf_counter() - t0

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        outcomes = list(executor.map(timed_pair, all_work))

    by_stem: dict[str, list[PairResult]] = defaultdict(list)
    pair_secs: dict[str, float] = defaultdict(float)
    for w, (p, dt) in zip(all_work, outcomes, strict=True):
        by_stem[w[0]].append(p)
        pair_secs[w[0]] += dt
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
            for line in render_stem_failures(r.stem, r.pairs):
                print(f"  {line}")

    coverage_findings = {
        r.stem: cov
        for r in results
        if not res_out_stem(r.stem) and (cov := case_coverage(r.pairs))
    }
    if coverage_findings:
        print()
        total = sum(len(v) for v in coverage_findings.values())
        print(f"--- case-coverage findings: {total} across "
              f"{len(coverage_findings)} solver(s) ---")
        for stem in sorted(coverage_findings):
            for line in coverage_findings[stem]:
                print(f"  {stem}.dl: {line}")

    _print_findings(stems, hints)

    determine_results: dict[str, DetermineResult] = {}
    determine_secs: dict[str, float] = {}
    for stem in stems:
        t0 = time.perf_counter()
        r = run_determine(stem)
        if r is not None:
            determine_results[stem] = r
            determine_secs[stem] = time.perf_counter() - t0
    if determine_results:
        problems = {
            s: r for s, r in determine_results.items()
            if r.diff or r.error or r.circular
        }
        print()
        ok = len(determine_results) - len(problems)
        print(f"--- determination checks: {ok}/{len(determine_results)} ok ---")
        for s in sorted(problems):
            for line in render_determine(problems[s]):
                print(f"  {s}.dl: {line}")

    if timed:
        ranked = sorted(
            ((pair_secs[s] + determine_secs.get(s, 0.0), s) for s in stems),
            reverse=True,
        )
        print()
        print("--- times: slowest 15 (wall seconds) ---")
        for total, s in ranked[:15]:
            determine_part = (f", determination {determine_secs[s]:.1f}"
                              if s in determine_secs else "")
            print(f"  {total:5.1f}  {s}  (pairs {pair_secs[s]:.1f}{determine_part})")

    print()
    print(f"summary: {len(results) - len(failed)}/{len(results)} solvers")
    return 0 if not failed else 1


def cmd_sweep(stem: str, max_candidates: int = MAX_CANDIDATES) -> int:
    if _missing(stem):
        return 2
    build_functors()
    for line in render_sweep(sweep_report(stem, max_candidates)):
        print(line)
    return 0


def _print_deletions(stem: str) -> int:
    report = deletion_report(stem)
    for line in render_deletions(stem, report):
        print(line)
    return 1 if report is None else 0


def cmd_deletions(stem: str) -> int:
    if _missing(stem):
        return 2
    build_functors()
    return _print_deletions(stem)


def cmd_audit(stem: str) -> int:
    """Both evidence audits of a finished solver: parameter value sweep +
    deletions."""
    if _missing(stem):
        return 2
    build_functors()
    print("--- sweep ---")
    for line in render_sweep(sweep_report(stem)):
        print(line)
    print()
    print("--- deletions ---")
    return _print_deletions(stem)


def cmd_drop_one(stem: str) -> int:
    """Which stored facts of a multi-fact parameter no pair needs. Opt-in:
    the audit does not run it."""
    if _missing(stem):
        return 2
    build_functors()
    for line in render_drop_one(stem, drop_one_report(stem)):
        print(line)
    return 0


def cmd_derived_constant(stem: str) -> int:
    """Which program relations derive from the input yet hold the same
    tuples on every example. Opt-in: the audit does not run it."""
    if _missing(stem):
        return 2
    build_functors()
    for line in render_derived_constant(stem, derived_constant_report(stem)):
        print(line)
    return 0


def cmd_determination_plan(stem: str) -> int:
    """Which Params parameters need determination relations, from the
    proposer probe."""
    if _missing(stem):
        return 2
    build_functors()
    for line in render_determination_plan(probe_report(stem)):
        print(line)
    return 0


def cmd_size(stem: str | None = None) -> int:
    """The literal count of each named solver, count first so the listing
    sorts numerically. A file outside the parser's dialect reports on
    stderr and the command exits non-zero."""
    if stem and _missing(stem):
        return 2
    stems = [stem] if stem else all_stems()
    bad = False
    for s in stems:
        try:
            print(f"{literal_count(parse((SOLVERS_DIR / f'{s}.dl').read_text()))}\t{s}")
        except ParseError as e:
            print(f"{s}: {e}", file=sys.stderr)
            bad = True
    return 1 if bad else 0


KEYWORDS_DOC = REPO_ROOT / "docs" / "wf-solver" / "keywords.md"

# The sections of keywords.md each header line draws its keywords from.
KEYWORD_SECTIONS = {"concept": ("Setup", "Prior"), "shape": ("Shape",)}

HEADER_RE = re.compile(r"^// (concept|shape): (.*)$")
BULLET_RE = re.compile(r"^- `([^`]+)`")


def _doc_keywords(text: str) -> dict[str, list[str]]:
    """The keywords of keywords.md, in doc order, per `##` section. A
    keyword is the leading code span of a bullet."""
    sections: dict[str, list[str]] = {}
    held: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            held = sections.setdefault(line[3:].strip(), [])
        elif m := BULLET_RE.match(line):
            held.append(m.group(1))
    return sections


def _header_keywords(source: str) -> list[tuple[str, str]]:
    """The (header kind, keyword) pairs of a solver's `// concept:` and
    `// shape:` lines. The header runs to the first line that is neither
    blank nor a comment."""
    pairs: list[tuple[str, str]] = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("//"):
            break
        if m := HEADER_RE.match(line):
            pairs.extend((m.group(1), word) for word in m.group(2).split())
    return pairs


def cmd_keywords(stems: list[str] | None = None) -> int:
    """The keyword vocabulary in use: how many solvers carry each keyword of
    keywords.md, and which header keyword the doc does not list. An unknown
    keyword is reported, not failed: this is analysis, and `lint` decides
    what a solver has to fix."""
    for s in stems or []:
        if _missing(s):
            return 2
    stems = stems or all_stems()
    sections = _doc_keywords(KEYWORDS_DOC.read_text())
    known = {kind: {w for name in names for w in sections.get(name, ())}
             for kind, names in KEYWORD_SECTIONS.items()}

    carriers: dict[str, set[str]] = defaultdict(set)
    unknown: list[str] = []
    for stem in stems:
        source = (SOLVERS_DIR / f"{stem}.dl").read_text()
        for kind, word in _header_keywords(source):
            if word in known[kind]:
                carriers[word].add(stem)
            else:
                unknown.append(f"{stem}: {word} is not in keywords.md")

    for name in ("Setup", "Prior", "Shape"):
        words = sections.get(name)
        if not words:
            continue
        print(f"--- {name} ---")
        for word in words:
            print(f"  {len(carriers[word]):4d}  {word}")
        print()
    for line in unknown:
        print(line)
    print(f"unknown keywords: {len(unknown)}")
    return 0


def cmd_expand(stem: str) -> int:
    """The solver source after the runner's GRID and RIGID expansions,
    which is the text Souffle compiles."""
    if _missing(stem):
        return 2
    sys.stdout.write(expand_macros((SOLVERS_DIR / f"{stem}.dl").read_text()))
    return 0


COMMANDS = ("run", "lint", "grid", "sweep", "deletions", "audit", "determination-plan", "size",
            "keywords", "expand", "since", "drop-one", "derived-constant")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Souffle solvers and their checks.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser(
        "run",
        help="pairs, lint, determination checks; the default when no command "
             "is named",
    )
    lint = sub.add_parser("lint", help="lint only, no solver runs")
    for p in (run, lint):
        p.add_argument("stem", nargs="?",
                       help="one solver; all of them when omitted")
        p.add_argument("--hints", action=argparse.BooleanOptionalAction,
                       default=True, help="include the hint tier")
    run.add_argument("--time", action="store_true", dest="timed",
                     help="print wall times: per phase for one solver, "
                          "slowest 15 for a full run")
    run.add_argument("--pairs", metavar="FILE",
                     help="run the named solver against ad-hoc pairs from "
                          "this JSON file (e.g. .scratch/<task>/pairs.json) "
                          "instead of the stored task; an example without "
                          '"output" prints the emitted grids')

    grid = sub.add_parser(
        "grid",
        help="run one solver on a grid you write, printing each case's output",
        description="Run one solver on a grid the caller writes, in place of "
                    "a stored pair, and print what each case emits.",
        epilog=GRID_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    grid.add_argument("stem")
    grid.add_argument("file", nargs="?",
                      help="grid file; stdin when omitted or `-`")

    sweep = sub.add_parser("sweep", help="parameter value sweep only")
    sweep.add_argument("stem")
    sweep.add_argument("cap", nargs="?", type=int, default=MAX_CANDIDATES,
                       help="max candidates per parameter")

    sub.add_parser("deletions", help="deletion report only").add_argument("stem")
    sub.add_parser(
        "audit", help="parameter value sweep + deletion report",
    ).add_argument("stem")
    sub.add_parser(
        "drop-one",
        help="which stored facts of a multi-fact parameter no pair needs",
        description="Drop each stored fact of each Params parameter holding "
                    "more than one fact, one fact at a time, and report the "
                    "facts whose removal reproduces the stored variant "
                    "profile on the train pairs. Each such fact runs again "
                    "over the test pairs, so a fact the test pairs need "
                    "reports apart from one dead on both. The cut is "
                    "textual, so a parameter with an Ident, a Grid, or any "
                    "other column no domain enumerates is covered as well. "
                    "Opt-in: the audit does not run it.",
    ).add_argument("stem")
    sub.add_parser(
        "derived-constant",
        help="program relations that hold the same tuples on every example",
        description="Report each program relation that reads `in` by "
                    "dataflow, feeds `out` by dataflow, and holds the same "
                    "tuples on every train and test example. Such a relation "
                    "derives from the input yet takes one value over the "
                    "task, so what it holds is stored in the program rather "
                    "than read off the grid. A relation empty everywhere is "
                    "out, and so is one that keeps its tuples on control "
                    "grids drawn from each example's palette, since it does "
                    "not really read the input. Opt-in: the audit does not "
                    "run it.",
    ).add_argument("stem")
    sub.add_parser(
        "determination-plan",
        help="which Params parameters need determination relations",
    ).add_argument("stem")

    size = sub.add_parser(
        "size", help="literal count per solver, for ordering by complexity",
        description="Print each named solver's literal count, count first, "
                    "so the listing sorts numerically.",
    )
    size.add_argument("stem", nargs="?",
                      help="one solver; all of them when omitted")

    keywords = sub.add_parser(
        "keywords", help="how many solvers carry each keyword of keywords.md",
        description="Read the `// concept:` and `// shape:` header line of "
                    "each named solver, count the solvers carrying each "
                    "keyword of keywords.md, and name every header keyword "
                    "the doc does not list. A concept keyword comes from the "
                    "Setup and Prior sections, a shape keyword from the "
                    "Shape section.",
    )
    keywords.add_argument("stem", nargs="*",
                          help="solvers to read; all of them when omitted")

    since = sub.add_parser(
        "since",
        help="the solvers in scope for a delta survey since a date-time",
        description="Print the stem of each solver a survey since the given "
                    "date-time covers: the ones the commits since then touch, "
                    "plus the ones whose working-tree content differs from "
                    "HEAD. A commit touching more than half of the solvers "
                    "is a corpus-wide mechanical rewrite, and the solvers "
                    "it touches are out of scope.",
    )
    since.add_argument("when", help="a date-time git reads, e.g. "
                                    '"2026-09-08 14:30"')

    sub.add_parser(
        "expand",
        help="the source after GRID and RIGID expansion, as Souffle sees it",
        description="Print the solver source with each GRID and RIGID call "
                    "replaced by what it emits and nothing else changed. "
                    "A GRID_HxW cell fact carries the cell's Position as its "
                    "four edge distances [top, bottom, left, right] in the "
                    "HxW frame; a RIGID block keeps its body as the chart, "
                    "each declared relation renamed _rigid_<block>_<rel>, "
                    "and adds per relation a <block>_<rel>(d4: D4, ...) "
                    "derived as every D4 placement of that chart.",
    ).add_argument("stem")
    return parser


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in (*COMMANDS, "-h", "--help"):
        argv = ["run", *argv]
    args = _parser().parse_args(argv)
    match args.cmd:
        case "lint":
            return cmd_lint(args.stem, args.hints)
        case "grid":
            return cmd_grid(args.stem, args.file)
        case "sweep":
            return cmd_sweep(args.stem, args.cap)
        case "deletions":
            return cmd_deletions(args.stem)
        case "audit":
            return cmd_audit(args.stem)
        case "drop-one":
            return cmd_drop_one(args.stem)
        case "derived-constant":
            return cmd_derived_constant(args.stem)
        case "determination-plan":
            return cmd_determination_plan(args.stem)
        case "size":
            return cmd_size(args.stem)
        case "keywords":
            return cmd_keywords(args.stem)
        case "expand":
            return cmd_expand(args.stem)
        case "since":
            return cmd_since(args.when)
        case _:
            if args.pairs:
                if not args.stem:
                    print("--pairs needs a solver stem", file=sys.stderr)
                    return 2
                return cmd_pairs(args.stem, args.pairs)
            if args.stem:
                return cmd_one(args.stem, args.hints, args.timed)
            return cmd_all(args.hints, args.timed)
