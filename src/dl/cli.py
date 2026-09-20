"""Commands the runner exposes, and the argv dispatch over them."""

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType

from arc.task import Alt, Example
from dl.annotations import header_keywords
from dl.corpus import literal_count
from dl.deletions import deletion_report, render_deletions
from dl.derived_constant import derived_constant_report, render_derived_constant
from dl.determination_plan import (
    probe_report,
    render_determination_plan,
    settle_survivors,
)
from dl.determine import (
    DetermineResult,
    render_determine,
    reproduced,
    run_determine,
)
from dl.dlparse import ParseError, parse
from dl.drop_one import drop_one_report, render_drop_one
from dl.facts import parse_grid
from dl.features import (
    FileFeatures,
    case_branches,
    features_json,
    features_report,
    render_features,
)
from dl.features_run import case_label, run_features
from dl.lint import (
    HEADER_CAT,
    KEYWORD_CAT,
    LIB_NAME_CAT,
    RESERVED_CAT,
    SHADOWED_TYPE_CAT,
    concept_case,
    lint_program,
)
from dl.paths import REPO_ROOT, all_stems
from dl.render import (
    _grid_lines,
    pass_suffix,
    render_pair_failure,
    render_stem_failures,
)
from dl.rewrite_lint import HINTS, lint_rewrites
from dl.solve import (
    PairResult,
    TaskResult,
    _pair_work,
    case_coverage,
    compile_error,
    res_out_stem,
    run_dl,
    run_dl_source,
    run_pair,
    run_task,
    solver_file,
)
from dl.souffle import (
    _pool_workers,
    build_functors,
    expression_report,
    sweep_temp_sources,
)
from dl.source import (
    KEYWORDS_DOC,
    build_source,
    doc_keywords,
    expand_macros,
)
from dl.sweep import (
    MAX_CANDIDATES,
    TIME_LIMIT_SECONDS,
    render_sweep,
    sweep_report,
)
from dl.sweep_open import (
    SWEEP_CACHE,
    marked_params,
    open_params,
    settled_params,
)
from dl.witness import (
    WITNESS_OK,
    annotation_lines,
    assigned_source,
    case_outcomes,
    finding_lines,
    load_witnesses,
    put_entry,
    read_witness_data,
    render_witness,
    undefined_concept,
    witness_path,
    witness_report,
    write_witness_data,
)

type Findings = list[tuple[str, int, str, str]]

# The three kinds a source's findings fall into, in report order. The
# first two print under `findings`, the third under `hints`.
LINT_KINDS = ("lint", "rewrite", "hint")


def _lint_kinds(source: str, hints: bool) -> list[Findings]:
    """Findings per kind, in LINT_KINDS order; the hint kind is empty
    unless enabled."""
    style: Findings = []
    dec: Findings = []
    adv: Findings = []
    for f in lint_program(source):
        (adv if f[0] == KEYWORD_CAT else style).append(f)
    for f in lint_rewrites(source, hints):
        (adv if f[0] in HINTS else dec).append(f)
    return [style, dec, adv]


def _finding_line(stem: str, kind: str, cat: str, lineno: int, match: str) -> str:
    """One finding as a line. A hint carries no category: the categories
    `@allow` takes name themselves in the line the hint prints to paste."""
    if kind == "hint":
        return f"{stem}.dl:{lineno}: {match}"
    if kind == "lint" and " " not in match:
        match = f"`{match}`"  # a bare code fragment; a sentence quotes itself
    return f"{stem}.dl:{lineno}: {cat}: {match}"


def _lint_verdict(counts: list[int]) -> str | None:
    """The verdict line for per-kind finding counts in LINT_KINDS order;
    None when a finding stands. A hint is advisory: the corpus both
    inlines and keeps its shapes, so a hint is a call the session makes,
    and it counts toward neither the verdict nor the exit code."""
    style, dec, adv = counts
    if style or dec:
        return None
    if adv:
        return f"lint: ok, {adv} hint{'s' if adv > 1 else ''}"
    return "lint: ok"


# Each printed section: its name, the word for one of its entries, and
# the kinds of LINT_KINDS it gathers.
SECTIONS = (
    ("findings", "finding", ("lint", "rewrite")),
    ("hints", "hint", ("hint",)),
)


def _print_findings(stems: list[str], hints: bool) -> str | None:
    """Print the sections for `stems`; return the verdict line."""
    by_kind: list[dict[str, Findings]] = [{}, {}, {}]
    for stem in stems:
        source = solver_file(stem)[0].read_text()
        for held, found in zip(by_kind, _lint_kinds(source, hints),
                               strict=True):
            if found:
                held[stem] = found

    counts = [sum(len(v) for v in held.values()) for held in by_kind]
    held_by_kind = dict(zip(LINT_KINDS, by_kind, strict=True))
    count_by_kind = dict(zip(LINT_KINDS, counts, strict=True))
    for label, _one, kinds in SECTIONS:
        count = sum(count_by_kind[k] for k in kinds)
        solvers = sorted({s for k in kinds for s in held_by_kind[k]})
        if not solvers:
            continue
        print()
        print(f"--- {label}: {count} across {len(solvers)} solver(s) ---")
        for stem in solvers:
            for kind in kinds:
                for cat, lineno, match, _ in held_by_kind[kind].get(stem, []):
                    print(f"  {_finding_line(stem, kind, cat, lineno, match)}")
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
    path = solver_file(stem)[0]
    if path.exists():
        return False
    print(f"no solver at {path}", file=sys.stderr)
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
    source = solver_file(stem)[0].read_text()
    collisions = [f for f in lint_program(source)
                  if f[0] in (RESERVED_CAT, SHADOWED_TYPE_CAT, LIB_NAME_CAT)]
    if collisions:
        print("likely cause:")
        for cat, lineno, match, _ in collisions:
            print(f"  {_finding_line(stem, 'lint', cat, lineno, match)}")
    return True


def _print_lint_sections(stem: str, hints: bool) -> str | None:
    """Print one solver's findings and hints; return the verdict line. Lint
    needs no Souffle, so it stands whether or not the solver compiles."""
    source = solver_file(stem)[0].read_text()
    found = dict(zip(LINT_KINDS, _lint_kinds(source, hints), strict=True))
    for _label, one, kinds in SECTIONS:
        gathered = [(kind, f) for kind in kinds for f in found[kind]]
        if not gathered:
            continue
        print()
        print(f"--- {len(gathered)} {one}(s) ---")
        for kind, (cat, lineno, match, _) in gathered:
            print(f"  {_finding_line(stem, kind, cat, lineno, match)}")
    return _lint_verdict([len(v) for v in found.values()])


def cmd_one(stem: str, hints: bool = False, timed: bool = False) -> int:
    if _missing(stem):
        return 2
    build_functors()
    if _compile_failed(stem):
        verdict = _print_lint_sections(stem, hints)
        print()
        if verdict is not None:
            print(verdict)
        return 1
    t0 = time.perf_counter()
    result = run_task(stem)
    pair_secs = time.perf_counter() - t0
    for p in result.pairs:
        if p.ok:
            print(f"{p.kind}[{p.idx}]: PASS{pass_suffix(p, res_out_stem(stem))}")
        else:
            for line in render_pair_failure(p, stem):
                print(line)

    if result.all_pass:
        source_text = solver_file(stem)[0].read_text()
        report = expression_report(build_source(source_text))
        if report is not None:
            print(report)

    coverage = [] if res_out_stem(stem) else case_coverage(result.pairs)
    if coverage:
        print()
        print(f"--- {len(coverage)} case-coverage finding(s) in {stem}.dl ---")
        for line in coverage:
            print(f"  {line}")

    verdict = _print_lint_sections(stem, hints)

    t0 = time.perf_counter()
    determination = run_determine(stem)
    determine_secs = time.perf_counter() - t0
    print()
    if verdict is not None:
        print(verdict)
    if determination is not None:
        for line in render_determine(determination):
            print(line)
    else:
        print("determination: no Determine comp")

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
    task_id = solver_file(stem)[1]
    failed = False
    for kind, examples in sections:
        for idx, e in enumerate(examples):
            if e.get("output") is None:
                for c in run_dl(task_id, e["input"], stem=stem):
                    print(f"{kind}[{idx}] {c.case or '(out)'}:")
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
                print(f"{kind}[{idx}]: PASS{pass_suffix(r, res_out_stem(stem))}")
            else:
                failed = True
                for line in render_pair_failure(r, stem):
                    print(line)
    return 1 if failed else 0


TIME_LIMIT_HELP = ("wall-clock limit in seconds for the sweep runs; the "
               "parameter in flight reports as cut and the ones behind it "
               "report as not swept")

GRID_HELP = """\
Grid format: one line per row, one character per cell — a digit 0-9, or `.`
for 0. Spaces and commas between cells are optional; blank lines and lines
starting with `#` are skipped. Text starting with `[` is read as JSON.
"""

STEM_HELP = "a stem, or a path to a solver file named for the task id"

RUN_HELP = """\
To profile one grid by hand, build the file in programs/solvers/, so that
`#include "../lib.dl"` resolves, and link the functor library that lib.dl's
relations call:

    { echo '#include "../lib.dl"'
      cat programs/solvers/<stem>.dl
      echo '.input in(IO=stdin)'
      echo '.output out(IO=stdout)'
    } > programs/solvers/.tmp.dl
    souffle -D- -w -L programs -lfunctors programs/solvers/.tmp.dl

Souffle reads one fact line per cell on stdin: `[top, bottom, left, right]`
edge distances, a tab, then the color. In a 3x3 grid the top-left cell, in
color 7, is

    [0, 2, 0, 2]<TAB>7

Add `-p <file>` for a profile that souffleprof reads. A solver with GRID or
RIGID call sites runs on the `expand` command's output.
"""


SEPARATOR = "---"
"""The line that splits a witness input from the judged output behind it."""


def _grid_text(path: str | None) -> str | None:
    """The grid text a caller names, from stdin when the path is omitted or
    `-`. None when the file is missing, which is reported."""
    if path in (None, "-"):
        return sys.stdin.read()
    p = Path(str(path))
    if not p.exists():
        print(f"no grid file at {p}", file=sys.stderr)
        return None
    return p.read_text()


def _parse_grid(text: str) -> list[list[int]] | None:
    """The grid the text writes. None when it writes none, which is
    reported."""
    try:
        return parse_grid(text)
    except (ValueError, json.JSONDecodeError, TypeError) as e:
        print(f"bad grid: {e}", file=sys.stderr)
        return None


def _sections(text: str) -> list[str]:
    """The grid texts the caller wrote, split at each separator line."""
    sections: list[str] = [""]
    for line in text.splitlines():
        if line.strip() == SEPARATOR:
            sections.append("")
        else:
            sections[-1] += line + "\n"
    return sections


def _print_run(stem: str, grid: list[list[int]],
               actuals: list) -> list[str]:
    """Print the input, what each case emits, and the cases that emit
    nothing; return those silent cases."""
    print("input:")
    for line in _grid_lines(grid):
        print(f"  {line}")
    for c in actuals:
        print()
        print(f"{c.case or '(out)'}:")
        if c.error:
            print(f"  {c.error}")
            continue
        for line in _grid_lines(c.grid):
            print(f"  {line}")
        if c.conflicts:
            print(f"  conflicts at: {c.conflicts}")
        if c.missing:
            print(f"  missing cells at: {c.missing}")

    emitted = {case_label(c.case) for c in actuals}
    silent = [b for b in case_branches(stem) if b not in emitted]
    if silent:
        print()
        for name in silent:
            print(f"{name if name.startswith('[') else '$' + name}"
                  ": emits nothing")
    cases = len(actuals) + len(silent)
    if cases > 1:
        distinct = {tuple(tuple(row) for row in c.grid)
                    for c in actuals if not c.error}
        print()
        print(f"{cases} cases, {len(distinct)} distinct grid(s)")
    return silent


def cmd_grid(stem: str, path: str | None = None) -> int:
    """Run one solver on a grid the caller wrote, in place of a stored pair,
    and print what each case emits."""
    if _missing(stem):
        return 2
    text = _grid_text(path)
    if text is None:
        return 2
    if len(_sections(text)) > 1:
        print(f"`{SEPARATOR}` belongs to `record`; `grid` takes one grid",
              file=sys.stderr)
        return 2
    grid = _parse_grid(text)
    if grid is None:
        return 2

    build_functors()
    if _compile_failed(stem):
        return 1
    try:
        actuals = run_dl(solver_file(stem)[1], grid, stem=stem)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    _print_run(stem, grid, actuals)
    return 0


def _assign_arg(text: str | None) -> dict | None:
    """The `--assign` object, or an empty one when the flag is omitted. None
    when the text is no JSON object, which is reported."""
    if text is None:
        return {}
    try:
        assign = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"bad --assign JSON: {e}", file=sys.stderr)
        return None
    if not isinstance(assign, dict):
        print("--assign takes an object of replacement facts per parameter",
              file=sys.stderr)
        return None
    return assign


def cmd_format(stem: str) -> int:
    """Rewrite the task's witness file through the serializer."""
    if _missing(stem):
        return 2
    task_id = solver_file(stem)[1]
    path = witness_path(task_id)
    if not path.exists():
        print(f"no witness file at {path}", file=sys.stderr)
        return 2
    write_witness_data(task_id, read_witness_data(task_id))
    print(f"formatted {path}")
    return 0


def cmd_record(stem: str, entry_id: str, separates: str,
               path: str | None = None, assign_text: str | None = None) -> int:
    """Run one solver on a grid the caller wrote and write the run into the
    task's witness file, as the entry `entry_id`. A run that leaves the
    concept case undefined prints the witness check's finding on it, and the
    entry is written all the same."""
    if _missing(stem):
        return 2
    assign = _assign_arg(assign_text)
    if assign is None:
        return 2
    text = _grid_text(path)
    if text is None:
        return 2
    sections = _sections(text)
    if len(sections) > 2:
        print(f"record takes one `{SEPARATOR}` separator at most",
              file=sys.stderr)
        return 2
    grid = _parse_grid(sections[0])
    if grid is None:
        return 2
    judged = None
    if len(sections) == 2:
        judged = _parse_grid(sections[1])
        if judged is None:
            return 2

    solver, task_id = solver_file(stem)
    source = solver.read_text()
    build_functors()
    if _compile_failed(stem):
        return 1
    try:
        actuals = run_dl_source(
            assigned_source(source, assign), grid, solver_path=solver)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    silent = _print_run(stem, grid, actuals)
    outcomes = case_outcomes(actuals, res_out_stem(stem))
    for name in silent:
        outcomes.setdefault(name, None)
    findings = undefined_concept(entry_id, concept_case(source), outcomes)
    if findings:
        print()
        for line in finding_lines(findings):
            print(line)
    if judged is not None:
        print()
        print("judged output:")
        for line in _grid_lines(judged):
            print(f"  {line}")
        output: object = judged
    else:
        output = outcomes
    entry: dict = {"id": entry_id, "separates": separates, "input": grid}
    if assign:
        entry["assign"] = assign
    entry["output"] = output
    data = read_witness_data(task_id)
    put_entry(data, entry)
    try:
        path = write_witness_data(task_id, data)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    print()
    print(f"wrote entry `{entry_id}` to {path}")
    print(f"add: // @witness {entry_id}: <plausibility> <verdict>")
    return 0


SOLVER_PATH_RE = re.compile(r"programs/solvers/([^/]+)\.dl$")


def _git(*args: str) -> str | None:
    """Git's stdout, or None when the call fails."""
    run = subprocess.run(["git", *args], cwd=REPO_ROOT,
                         capture_output=True, text=True)
    return run.stdout if run.returncode == 0 else None


def _commit_stems(log: str) -> list[tuple[str, set[str]]]:
    """Each commit as its hash and the solver stems it touches, from
    `git log --name-only` output."""
    commits: list[tuple[str, set[str]]] = []
    for line in log.splitlines():
        if line.startswith("commit "):
            commits.append((line.split(" ", 1)[1].strip(), set()))
        elif (m := SOLVER_PATH_RE.match(line.strip())) and commits:
            commits[-1][1].add(m.group(1))
    return commits


REWRITE_SHARE = 0.5
"""The share of the corpus above which commits count as a mechanical
rewrite rather than solver work."""


def _is_mechanical_rewrite(touched: set[str], corpus: set[str]) -> bool:
    """Whether the commits that touch `touched` rewrite the corpus
    mechanically: a reach past REWRITE_SHARE of `corpus` is one."""
    return len(touched) > REWRITE_SHARE * len(corpus)


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
    from HEAD. An uncommitted change is newer than any commit, so the
    working-tree half takes every such solver and applies no time test.
    Commits reaching past REWRITE_SHARE of the corpus are a mechanical
    rewrite, tested one commit at a time and again over the window: a
    rewriting commit drops out, and a rewriting window keeps of its commits
    only the solvers they add. The working-tree half stands either way."""
    log = _git("log", f"--since={when}", "--name-only", "--pretty=format:commit %H",
               "--", "programs/solvers")
    status = _git("status", "--porcelain", "--", "programs/solvers")
    if log is None or status is None:
        print(f"git found no history for {when!r}", file=sys.stderr)
        return 1
    corpus = set(all_stems())
    committed: set[str] = set()
    for sha, touched in _commit_stems(log):
        if _is_mechanical_rewrite(touched, corpus):
            print(f"skipped {sha}: a mechanical rewrite, touching "
                  f"{len(touched)} solvers of {len(corpus)}, more than the "
                  f"{REWRITE_SHARE:.0%} share", file=sys.stderr)
        else:
            committed |= touched
    if _is_mechanical_rewrite(committed, corpus):
        added = _git("log", f"--since={when}", "--diff-filter=A", "--name-only",
                     "--pretty=format:commit %H", "--", "programs/solvers")
        if added is None:
            print(f"git found no history for {when!r}", file=sys.stderr)
            return 1
        kept = committed & {s for _, t in _commit_stems(added) for s in t}
        print(f"the window holds a corpus-wide rewrite: its commits touch "
              f"{len(committed)} solvers of {len(corpus)}, more than the "
              f"{REWRITE_SHARE:.0%} share. The scope is the {len(kept)} "
              f"solvers added since then.", file=sys.stderr)
        committed = kept
    in_scope = sorted((committed | _worktree_stems(status)) & corpus)
    for stem in in_scope:
        print(stem)
    print(f"{len(in_scope)} solvers in scope.", file=sys.stderr)
    return 0


def cmd_all(hints: bool = False, timed: bool = False,
            stems: list[str] | None = None) -> int:
    if stems is not None and any(_missing(s) for s in sorted(set(stems))):
        return 2
    build_functors()
    stems = stems if stems is not None else all_stems()

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


def _print_sweep(stem: str, max_candidates: int, time_limit: float) -> None:
    """The sweep report, with the time limit and the elapsed time as a
    footer."""
    determined = reproduced(run_determine(stem))
    start = time.monotonic()
    lines = render_sweep(
        sweep_report(stem, max_candidates, time_limit), determined)
    elapsed = time.monotonic() - start
    for line in lines:
        print(line)
    print(f"time limit {time_limit:.0f}s; elapsed {elapsed:.0f}s")


def cmd_sweep(stem: str, max_candidates: int = MAX_CANDIDATES,
              time_limit: float = TIME_LIMIT_SECONDS) -> int:
    if _missing(stem):
        return 2
    build_functors()
    _print_sweep(stem, max_candidates, time_limit)
    return 0


def _sweep_output(stem: str) -> str:
    """Everything one sweep prints, its stderr progress lines included."""
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        build_functors()
        _print_sweep(stem, MAX_CANDIDATES, TIME_LIMIT_SECONDS)
    return buf.getvalue()


def _code_hash(stem: str) -> str:
    """A hash of the solver's code, its comment lines left out. A line whose
    first non-blank characters are `//` does not count, so a review line
    written into the header leaves the hash as it was."""
    source = solver_file(stem)[0].read_text()
    code = [line for line in source.splitlines()
            if not line.lstrip().startswith("//")]
    return hashlib.sha256("\n".join(code).encode()).hexdigest()


def _sweep_text(stem: str, cached: bool) -> tuple[str | None, str | None]:
    """The stem's sweep output, and the reason there is none.

    A sweep is valid only for the solver code it was made from, so the cache
    keeps that code's hash beside the text, in a sidecar file `<stem>.sha`.
    A cache with the solver's current hash is read. A cache with a different
    hash is stale, and so is a stem the cache does not hold: without `cached`
    the sweep runs and both files are rewritten; with `cached` the stem gives
    None and a reason instead of running for minutes.

    A cache with no sidecar predates the sidecar, so the code behind it is
    unknown. With `cached` nothing runs, and the text is read with a note on
    stderr that it is unverified. Without `cached` the sweep runs, which gives
    the stem a text and a hash that go together."""
    path = SWEEP_CACHE / f"{stem}.txt"
    sha_path = SWEEP_CACHE / f"{stem}.sha"
    where = f".scratch/retro/sweep/{stem}.txt"
    held = path.exists()
    if held and sha_path.exists():
        if sha_path.read_text().strip() == _code_hash(stem):
            return path.read_text(), None
    elif held and cached:
        print(f"{stem}: the cached sweep at {where} is unverified: it was "
              "made before the cache kept the solver's code hash",
              file=sys.stderr)
        return path.read_text(), None
    if cached:
        if held:
            return None, (f"the cached sweep at {where} is stale: the solver's "
                          "code changed after it was made")
        return None, f"no cached sweep at {where}"
    text = _sweep_output(stem)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    sha_path.write_text(_code_hash(stem))
    return text, None


def _open_sweeps(
    stems: list[str], cached: bool,
) -> tuple[list[tuple[str, list[tuple[str, str, str]]]], list[dict[str, str]]]:
    """Per stem, the parameters its sweep leaves open; and the stems left
    out, each with its reason."""
    sweeps: list[tuple[str, list[tuple[str, str, str]]]] = []
    skipped: list[dict[str, str]] = []
    for stem in stems:
        path = solver_file(stem)[0]
        if not path.exists():
            skipped.append({"stem": stem, "reason": f"no solver at {path}"})
            continue
        text, reason = _sweep_text(stem, cached)
        if text is None:
            skipped.append({"stem": stem, "reason": reason})
            continue
        sweeps.append((stem, open_params(text)))
    return sweeps, skipped


def _emit(payload: dict[str, object]) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=1))
    return 0


def cmd_sweep_open(stems: list[str], cached: bool = False) -> int:
    """Report, as JSON, the parameters each stem's sweep leaves open, and the
    review line each of them takes."""
    sweeps, skipped = _open_sweeps(stems, cached)
    return _emit({
        "sweeps": [
            {"stem": stem,
             "params": [{"param": param, "reported": reported, "line": line}
                        for param, reported, line in params]}
            for stem, params in sweeps
        ],
        "skipped": skipped,
    })


def _console_solvers() -> ModuleType:
    """The console's reads and writes of the solver files. They sit outside
    the package, so the import puts their directory on the path."""
    path = str(REPO_ROOT / "tools" / "console")
    if path not in sys.path:
        sys.path.insert(0, path)
    from solver_console import solvers
    return solvers


def cmd_sweep_mark(stems: list[str], cached: bool = False) -> int:
    """Write the review line of each open parameter into its solver's header,
    then report what was written and what the lint's header category says."""
    sweeps, skipped = _open_sweeps(stems, cached)
    console = _console_solvers()
    marked: list[dict[str, object]] = []
    for stem, params in sweeps:
        standing = marked_params(console.needs_of(stem)["sweep"])
        written = [line for param, _, line in params
                   if param not in standing and console.append_review(stem, line)]
        lint_ok = True
        if written:
            source = solver_file(stem)[0].read_text()
            lint_ok = not any(f[0] == HEADER_CAT for f in lint_program(source))
        marked.append({"task_id": stem, "lines": written, "lint_ok": lint_ok})
    return _emit({"solvers": marked, "skipped": skipped})


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


def _print_witness(stem: str) -> int:
    """The features each `@witness` line of `stem` states, then its witness
    report. Non-zero on a differing output or an annotation finding."""
    path, task_id = solver_file(stem)
    witness = load_witnesses(task_id)
    print("`@witness` lines:")
    for line in annotation_lines(path.read_text()):
        print(f"  {line}")
    print()
    if witness is None:
        print(f"no witness file at {witness_path(task_id)}")
    else:
        grids = len(witness.entries)
        print(f"{grids} witness grid{'s' if grids != 1 else ''} run")
    lines = render_witness(witness_report(stem))
    passed = lines[-1] == WITNESS_OK
    for line in (lines[:-1] if passed else lines):
        print(f"  {line}")
    if passed:
        print(WITNESS_OK)
    return 0 if passed else 1


def cmd_witness(stem: str) -> int:
    """Run the task's witness grids through the solver and report each case
    whose output differs from the one its entry names."""
    if _missing(stem):
        return 2
    build_functors()
    return _print_witness(stem)


def cmd_audit(stem: str, time_limit: float = TIME_LIMIT_SECONDS) -> int:
    """The evidence audits of a finished solver: parameter value sweep,
    deletions, witness. The sweep runs under the time limit, and the other
    two run after it."""
    if _missing(stem):
        return 2
    build_functors()
    print("--- sweep ---")
    _print_sweep(stem, MAX_CANDIDATES, time_limit)
    print()
    print("--- deletions ---")
    deletions = _print_deletions(stem)
    print()
    print("--- witness ---")
    return deletions or _print_witness(stem)


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


def cmd_determination_plan(stem: str, verdicts: bool = False) -> int:
    """Which Params parameters need determination relations, from the
    proposer probe."""
    if _missing(stem):
        return 2
    build_functors()
    report = probe_report(stem)
    lines = render_determination_plan(
        report, settle_survivors(stem, report), verdicts)
    for line in lines:
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
            print(f"{literal_count(parse(solver_file(s)[0].read_text()))}\t{s}")
        except ParseError as e:
            print(f"{s}: {e}", file=sys.stderr)
            bad = True
    return 1 if bad else 0


def _sweep_counts(
    stem: str, skipped: list[dict[str, str]],
) -> tuple[int, int] | None:
    """How many parameters the stem's cached sweep leaves open, and how many
    it settles on one value. A stem whose cached sweep does not stand for its
    current code gets no counts: the reason goes to stderr and to `skipped`,
    and no sweep runs."""
    text, reason = _sweep_text(stem, cached=True)
    if text is None:
        print(f"{stem}: {reason}", file=sys.stderr)
        skipped.append({"stem": stem, "reason": reason})
        return None
    return len(open_params(text)), len(settled_params(text))


def cmd_features(stem: str | None = None, run: bool = False,
                 as_json: bool = False) -> int:
    """Per-case features of each named solver, one row per case. The static
    columns read the source; the dynamic ones need `--run`, which runs every
    pair of every named solver, train and test alike."""
    if stem and _missing(stem):
        return 2
    stems = [stem] if stem else all_stems()
    if run:
        build_functors()
    files: list[FileFeatures] = []
    skipped: list[dict[str, str]] = []
    bad = False
    for s in stems:
        try:
            dynamic = run_features(s, case_branches(s)) if run else None
            files.append(features_report(s, _sweep_counts(s, skipped), dynamic))
        except ParseError as e:
            print(f"{s}: {e}", file=sys.stderr)
            skipped.append({"stem": s, "reason": str(e)})
            bad = True
    if as_json:
        _emit(features_json(files, skipped))
    else:
        for line in render_features(files):
            print(line)
    return 1 if bad else 0


def cmd_keywords(stems: list[str] | None = None) -> int:
    """The keyword vocabulary in use: how many solvers carry each keyword of
    keywords.md, and which header keyword the doc does not list. An unknown
    keyword is reported, not failed: this is analysis, and `lint` decides
    what a solver has to fix."""
    for s in stems or []:
        if _missing(s):
            return 2
    stems = stems or all_stems()
    sections = doc_keywords(KEYWORDS_DOC.read_text())
    known = {w for words in sections.values() for w in words}

    carriers: dict[str, set[str]] = defaultdict(set)
    unknown: list[str] = []
    for stem in stems:
        source = solver_file(stem)[0].read_text()
        for word in header_keywords(source):
            if word in known:
                carriers[word].add(stem)
            else:
                unknown.append(f"{stem}: {word} is not in keywords.md")

    for name, words in sections.items():
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
    sys.stdout.write(expand_macros(solver_file(stem)[0].read_text()))
    return 0


COMMANDS = ("run", "lint", "grid", "record", "sweep", "deletions", "audit",
            "determination-plan", "size",
            "keywords", "expand", "since", "drop-one", "derived-constant", "features",
            "witness")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Souffle solvers and their checks.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser(
        "run",
        help="pairs, lint, determination checks; the default when no command "
             "is named",
        epilog=RUN_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    lint = sub.add_parser(
        "lint", help="lint only, no solver runs",
        description="The output has two sections. A finding has to be "
                    "fixed. A hint is the session's call, and changes "
                    "neither the verdict nor the exit code.",
    )
    run.add_argument("stems", nargs="*",
                     help="the solvers to run; one runs its pairs, lint and "
                          "determination check, several run as a corpus over "
                          "those solvers alone, and none runs the whole "
                          "corpus. Each one is a stem or a path to a solver "
                          "file whose name keeps the task id as its prefix")
    lint.add_argument("stem", nargs="?",
                      help="one solver; all of them when omitted")
    for p in (run, lint):
        p.add_argument("--hints", action=argparse.BooleanOptionalAction,
                       default=True, help="include the hints section")
    run.add_argument("--time", action="store_true", dest="timed",
                     help="print wall times: per phase for one solver, "
                          "slowest 15 for a full run")
    run.add_argument("--pairs", metavar="FILE",
                     help="run the named solver against ad-hoc pairs from "
                          "this JSON file instead of the stored task; an "
                          'example without "output" prints the emitted grids')

    grid = sub.add_parser(
        "grid",
        help="run one solver on a grid you write, printing each case's output",
        epilog=GRID_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    grid.add_argument("stem", help=STEM_HELP)
    grid.add_argument("file", nargs="?",
                      help="grid file; stdin when omitted or `-`")

    record = sub.add_parser(
        "record",
        help="run one solver on a grid you write and write the run into the "
             "task's witness file",
        description="The witness goes into programs/witnesses/<task>.wit.json "
                    "under <id>, replacing a witness of that id already "
                    "there. A `---` line in the grid text puts the judged "
                    "output an `other` verdict takes behind it, and that "
                    "grid is stored in place of the per-case outputs.",
        epilog=GRID_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    record.add_argument("stem", help=STEM_HELP)
    record.add_argument("id", nargs="?",
                        help="the witness's id, unique within the witness "
                             "file; required unless `--format`")
    record.add_argument("file", nargs="?",
                        help="grid file; stdin when omitted or `-`")
    record.add_argument("--separates", help="what the entry separates; "
                                            "required unless `--format`")
    record.add_argument("--assign", metavar="JSON", dest="assign",
                        help="replacement facts per parameter, as the "
                             "entry's `assign` object; the run takes the "
                             "reassigned source")
    record.add_argument("--format", action="store_true", dest="as_format",
                        help="rewrite the task's witness file through the "
                             "serializer and add no entry")

    sweep = sub.add_parser(
        "sweep", help="parameter value sweep only",
        description="Which values of each Params parameter's domain "
                    "reproduce every train pair. A ✓ marks a parameter the "
                    "pairs settle to its stored value; every other line names "
                    "what it leaves open.",
    )
    sweep.add_argument("stem", nargs="?", help="one solver")
    sweep.add_argument("cap", nargs="?", type=int, default=MAX_CANDIDATES,
                       help="candidate count the sweep holds to: above it "
                            "the sweep narrows to one-column and one-row "
                            "changes, and it bounds those too")
    sweep.add_argument("--time-limit", type=float, dest="time_limit",
                       default=TIME_LIMIT_SECONDS, help=TIME_LIMIT_HELP)
    over = sweep.add_mutually_exclusive_group()
    over.add_argument("--open", nargs="+", metavar="STEM", dest="open_stems",
                      help="report as JSON, over these stems, the parameters "
                           "each sweep leaves open and the `// review sweep:` "
                           "line each one takes")
    over.add_argument("--mark", nargs="+", metavar="STEM", dest="mark_stems",
                      help="the same reading, written into the solvers: each "
                           "open parameter without a `review sweep:` line yet "
                           "gets one as the last header line. The report names "
                           "each line written, and each lint finding the "
                           "header carries after the write")
    sweep.add_argument("--cached", action="store_true",
                       help="with `--open` or `--mark`, take only the stems "
                            "whose cached sweep matches their current code, "
                            "or carries no hash to match, and skip the rest "
                            "with a reason. A stem whose only change since "
                            "the sweep is a comment line still matches")

    sub.add_parser(
        "deletions", help="deletion report only",
        description="The rules and facts of the solver that no train pair "
                    "needs.",
    ).add_argument("stem", help="one solver")
    audit = sub.add_parser(
        "audit",
        help="parameter value sweep + deletion report + witness report",
        description="The sweep, the deletion report and the witness report "
                    "over one solver. Only the sweep runs under the time "
                    "limit.",
    )
    audit.add_argument("stem", help="one solver")
    audit.add_argument("--time-limit", type=float, dest="time_limit",
                       default=TIME_LIMIT_SECONDS, help=TIME_LIMIT_HELP)
    sub.add_parser(
        "drop-one",
        help="which stored facts of a multi-fact parameter no pair needs",
        description="The stored facts of a multi-fact Params parameter "
                    "that no train pair needs. A fact the test pairs still "
                    "need reports apart from one dead on both. The audit does "
                    "not run it.",
    ).add_argument("stem", help="one solver")
    sub.add_parser(
        "derived-constant",
        help="program relations that hold the same tuples on every example",
        description="Each program relation between `in` and `out` that "
                    "holds the same tuples on every train and test example. A "
                    "relation empty everywhere, and one that keeps its tuples "
                    "on control grids from each example's palette, are left "
                    "out. The audit does not run it.",
    ).add_argument("stem", help="one solver")
    sub.add_parser(
        "witness",
        help="run the task's hand-written witness grids and report where "
             "the solver and the file disagree",
        description="Where the solver and "
                    "programs/witnesses/<task>.wit.json disagree: a case "
                    "whose output differs from the one its entry names, and "
                    "a `@witness` line the file does not bear out. Without "
                    "a witness file, every `@witness` line of the solver "
                    "names no entry.",
    ).add_argument("stem", help="one solver")
    plan = sub.add_parser(
        "determination-plan",
        help="which Params parameters need determination relations",
        description="Each Params parameter under the action it needs: "
                    "write a determination relation, record its open "
                    "values, write determination relations until the product "
                    "of the remaining candidate counts is under the "
                    "enumeration limit, move data from clauses into fact "
                    "parameters, or none.",
    )
    plan.add_argument("stem", help="one solver")
    plan.add_argument("--verdicts", action="store_true",
                      help="append each proposer's verdict on each parameter")

    size = sub.add_parser(
        "size", help="literal count per solver",
        description="Print each named solver's literal count, count first.",
    )
    size.add_argument("stem", nargs="?",
                      help="one solver; all of them when omitted")

    features = sub.add_parser(
        "features", help="per-case features, one TSV row per Choice case",
        description="Print one row per case of each named solver. A rule "
                    "belongs to the cases whose constructors its head holds, "
                    "and so do the rules it reads, transitively. `atoms`, "
                    "`rules` and `facts` weigh what one case reaches and no "
                    "other; `shared_*` weigh what two cases reach, `reach_*` "
                    "weigh a case's whole reach, and `unreached_atoms` weighs "
                    "what no case reaches. The ratios stand against the "
                    "smallest case of the file. With `--run`, "
                    "`pairs_separating` and `pairs_undefined` count over "
                    "every pair of the task, train and test alike, keyed by "
                    "the grid a case emits.",
    )
    features.add_argument("stem", nargs="?",
                          help="one solver, as a stem or a path to a solver "
                               "file; all of them when omitted")
    features.add_argument("--run", action="store_true",
                          help="run every pair of the task, train and test, "
                               "and fill the separation columns from what "
                               "each case emits")
    features.add_argument("--json", action="store_true", dest="as_json",
                          help="print JSON instead of TSV, with the pairwise "
                               "matrix of separating pairs per solver")

    keywords = sub.add_parser(
        "keywords", help="how many solvers carry each keyword of keywords.md",
        description="Read the `// @keywords:` header line of each named "
                    "solver, count the solvers carrying each keyword of "
                    "keywords.md, and name every header keyword the doc "
                    "does not list.",
    )
    keywords.add_argument("stem", nargs="*",
                          help="solvers to read; all of them when omitted")

    since = sub.add_parser(
        "since",
        help="the solvers in scope for a delta survey since a date-time",
        description="Print the stem of each solver a survey since the given "
                    "date-time covers: the ones the commits since then touch, "
                    "plus the ones whose working-tree content differs from "
                    "HEAD. Commits touching more than half the corpus "
                    "count as a mechanical rewrite: the solvers a rewriting "
                    "commit touches are out of scope, and of a rewriting "
                    "window only the solvers its commits add stay in scope. "
                    "The working-tree half stands either way.",
    )
    since.add_argument("when", help="a date-time git reads, e.g. "
                                    '"2026-09-08 14:30"')

    sub.add_parser(
        "expand",
        help="the source after GRID and RIGID expansion, as Souffle sees it",
        description="Print the solver source with each GRID and RIGID call "
                    "replaced by what it emits and nothing else changed.",
    ).add_argument("stem", help="one solver")
    return parser


def main(argv: list[str]) -> int:
    # once per invocation, before any solver runs: the temp sources a killed
    # run left behind go here
    sweep_temp_sources()
    if not argv or argv[0] not in (*COMMANDS, "-h", "--help"):
        argv = ["run", *argv]
    args = _parser().parse_args(argv)
    match args.cmd:
        case "lint":
            return cmd_lint(args.stem, args.hints)
        case "grid":
            return cmd_grid(args.stem, args.file)
        case "record":
            if args.as_format:
                if args.id or args.file or args.separates or args.assign:
                    print("`--format` rewrites the file and takes no entry",
                          file=sys.stderr)
                    return 2
                return cmd_format(args.stem)
            if args.id is None or args.separates is None:
                print("record takes an entry id and `--separates`",
                      file=sys.stderr)
                return 2
            return cmd_record(args.stem, args.id, args.separates, args.file,
                              args.assign)
        case "sweep":
            stems = args.open_stems or args.mark_stems
            if stems:
                if args.stem is not None:
                    print("`--open` and `--mark` carry their own stems",
                          file=sys.stderr)
                    return 2
                if args.open_stems:
                    return cmd_sweep_open(stems, args.cached)
                return cmd_sweep_mark(stems, args.cached)
            if args.stem is None:
                print("sweep takes one stem, or `--open`/`--mark` with stems",
                      file=sys.stderr)
                return 2
            if args.cached:
                print("`--cached` goes with `--open` or `--mark`",
                      file=sys.stderr)
                return 2
            return cmd_sweep(args.stem, args.cap, args.time_limit)
        case "deletions":
            return cmd_deletions(args.stem)
        case "audit":
            return cmd_audit(args.stem, args.time_limit)
        case "drop-one":
            return cmd_drop_one(args.stem)
        case "derived-constant":
            return cmd_derived_constant(args.stem)
        case "determination-plan":
            return cmd_determination_plan(args.stem, args.verdicts)
        case "witness":
            return cmd_witness(args.stem)
        case "size":
            return cmd_size(args.stem)
        case "features":
            return cmd_features(args.stem, args.run, args.as_json)
        case "keywords":
            return cmd_keywords(args.stem)
        case "expand":
            return cmd_expand(args.stem)
        case "since":
            return cmd_since(args.when)
        case _:
            if args.pairs:
                if len(args.stems) != 1:
                    print("--pairs needs one solver stem", file=sys.stderr)
                    return 2
                return cmd_pairs(args.stems[0], args.pairs)
            if len(args.stems) == 1:
                return cmd_one(args.stems[0], args.hints, args.timed)
            if args.stems:
                return cmd_all(args.hints, args.timed, args.stems)
            return cmd_all(args.hints, args.timed)
