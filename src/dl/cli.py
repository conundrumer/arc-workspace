"""Commands the runner exposes, and the argv dispatch over them."""

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path
from types import ModuleType

from arc.task import Alt, Example
from controlled_markdown import mctx
from dl.annotations import (
    STORED,
    branch_lines,
    header_keywords,
    witness_blocks,
)
from dl.corpus import literal_count
from dl.deletions import deletion_report, render_deletions
from dl.derive import (
    DERIVE_OK,
    derive_hint,
    derive_report,
    render_derive,
    render_findings,
)
from dl.derived_constant import derived_constant_report, render_derived_constant
from dl.determination_plan import (
    per_grid_candidates,
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
from dl.facts import Candidate, parse_grid
from dl.features import (
    FileFeatures,
    case_branches,
    features_json,
    features_report,
    held_cases,
    held_input_findings,
    render_features,
)
from dl.features_run import run_features
from dl.lint import (
    HEADER_CAT,
    HINT_CATS,
    LIB_NAME_CAT,
    RESERVED_CAT,
    SHADOWED_TYPE_CAT,
    lint_program,
)
from dl.models import (
    CaseId,
    Cases,
    case_label,
    case_space,
    enumeration,
    model_label,
)
from dl.paths import REPO_ROOT, all_stems
from dl.render import (
    _grid_lines,
    pass_suffix,
    render_pair_failure,
    render_stem_failures,
)
from dl.relation import MissingRelations, relation_rows
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
    solver_name,
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
from dl.store import (
    OWNED,
    STORE_OK,
    lined,
    relation_site,
    render_store,
    store_hint,
    store_report,
)
from dl.store import render_findings as render_store_findings
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
    DROPPED,
    WITNESS_FILE_OK,
    Drift,
    Outcome,
    annotation_lines,
    assign_findings,
    assigned_source,
    branch_outcomes,
    file_shape,
    finding_lines,
    grouped_output,
    held_outcomes,
    line_branch_witness,
    load_witness_file,
    load_witnesses,
    pass_line,
    passes,
    read_witness_data,
    recorded_models,
    witness_path,
    witness_report,
    write_entries,
)

type Findings = list[tuple[str, int, str, str]]

# The three kinds a source's findings fall into, in report order. The
# first two print under `findings`, the third under `hints`.
LINT_KINDS: tuple[str, ...] = ("lint", "rewrite", "hint")


def _lint_kinds(source: str, hints: bool,
                task_id: str | None = None) -> list[Findings]:
    """Findings per kind, in LINT_KINDS order; the hint kind is empty
    unless enabled. With `task_id`, the lint kind also holds the finding
    on an `impl_choice` that depends on the input
    (`dl.features.held_input_findings`), which runs Souffle."""
    style: Findings = []
    dec: Findings = []
    adv: Findings = []
    for f in lint_program(source):
        (adv if f[0] in HINT_CATS else style).append(f)
    if task_id is not None:
        style += held_input_findings(task_id, source)
    for f in lint_rewrites(source, hints):
        (adv if f[0] in HINTS else dec).append(f)
    return [style, dec, adv]


def _finding_line(stem: str, kind: str, cat: str, lineno: int, match: str) -> str:
    """One finding as a line. A hint carries no category: the categories
    `@ignore` takes name themselves in the line the hint prints to paste."""
    if kind == "hint":
        return f"{solver_name(stem)}:{lineno}: {match}"
    if kind == "lint" and " " not in match:
        match = f"`{match}`"  # a bare code fragment; a sentence quotes itself
    return f"{solver_name(stem)}:{lineno}: {cat}: {match}"


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

    def kinds(stem: str) -> list[Findings]:
        path, task_id = solver_file(stem)
        return _lint_kinds(path.read_text(), hints, task_id)

    # The `impl_choice` check runs Souffle, so the solvers lint in threads.
    with ThreadPoolExecutor(max_workers=_pool_workers()) as pool:
        for stem, found_kinds in zip(stems, pool.map(kinds, stems),
                                     strict=True):
            for held, found in zip(by_kind, found_kinds, strict=True):
                if found:
                    held[stem] = found

    counts = [sum(len(v) for v in held.values()) for held in by_kind]
    held_by_kind = dict(zip(LINT_KINDS, by_kind, strict=True))
    count_by_kind = dict(zip(LINT_KINDS, counts, strict=True))
    for label, _one, section_kinds in SECTIONS:
        count = sum(count_by_kind[k] for k in section_kinds)
        solvers = sorted({s for k in section_kinds for s in held_by_kind[k]})
        if not solvers:
            continue
        print()
        print(f"--- {label}: {count} across {len(solvers)} solver(s) ---")
        for stem in solvers:
            for kind in section_kinds:
                for cat, lineno, match, _ in held_by_kind[kind].get(stem, []):
                    print(f"  {_finding_line(stem, kind, cat, lineno, match)}")
    return _lint_verdict(counts)


def cmd_lint(
    stem: str | None, hints: bool = False,
) -> int:
    """Lint only: no pair runs and no determination checks. Souffle runs
    only for `impl_choice` (`dl.features.held_input_findings`)."""
    if stem is not None and _missing(stem):
        return 2
    build_functors()
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
    print(f"{solver_name(stem)}: {err}")
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
    stands whether or not the solver compiles: the one check that runs
    Souffle gives no finding when the run fails."""
    path, task_id = solver_file(stem)
    found = dict(zip(LINT_KINDS, _lint_kinds(path.read_text(), hints,
                                             task_id), strict=True))
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
        print(f"--- {len(coverage)} case-coverage finding(s) in {solver_name(stem)} ---")
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


TIME_LIMIT_HELP = mctx("wall-clock limit in seconds on the sweep's solver "
                       "runs; once they take that long, the parameter in "
                       "progress reports as cut, and each parameter not yet "
                       "started reports as not swept")

GRID_HELP = mctx("Grid format: one line per row, one digit 0-9 per cell. "
                 "Spaces and commas between cells are optional; blank lines "
                 "and lines starting with `#` are skipped. Text starting with "
                 "`[` is read as JSON.")

STEM_HELP = mctx("a task id, or the path to a solver file whose name starts "
                 "with the task id")

ASSIGN_HELP = mctx("an `assign` object, in the witness file's shape")

STEM_OR_ALL_HELP = mctx("a task id, or the path to a solver file whose name "
                        "starts with the task id; every solver when omitted")

RUN_HELP = mctx("""
    - To profile one grid by hand, write a file beside the solvers, so that `#include "../lib.dl"` resolves, and link the functor library that the lib's relations call:
        ```
        { echo '#include "../lib.dl"'
          cat programs/solvers/<stem>.dl
          echo '.input in(IO=stdin)'
          echo '.output out(IO=stdout)'
        } > programs/solvers/.tmp.dl
        souffle -D- -w -L programs -lfunctors programs/solvers/.tmp.dl
        ```
    - Souffle reads one fact line per cell on stdin: `[top, bottom, left, right]` edge distances, a tab, then the color. In a 3x3 grid the top-left cell, in color 7, is `[0, 2, 0, 2]<TAB>7`.
    - For a solver with GRID calls or RIGID blocks, put the `expand` command's output in place of the `cat` line.
    - Add `-p <file>` for a profile that souffleprof reads.
    """)


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


def _run_body(c) -> list[str]:
    """What one case emits, indented under its name."""
    if c.error:
        return [f"  {c.error}"]
    lines = [f"  {line}" for line in _grid_lines(c.grid)]
    if c.conflicts:
        lines.append(f"  conflicts at: {c.conflicts}")
    if c.missing:
        lines.append(f"  missing cells at: {c.missing}")
    return lines


def _model_body(cands: list, resolution: bool) -> list[str]:
    """What one model emits: each grid under its resolution when it emits
    more than one."""
    if len(cands) == 1:
        return _run_body(cands[0])
    lines: list[str] = []
    for c in cands:
        tail = c.case.split("\t")[-1] if resolution else c.case
        lines.append(f"  {tail}:")
        lines += [f"  {line}" for line in _run_body(c)]
    return lines


def _print_run(grid: list[list[int]], actuals: list, space: Cases,
               resolution: bool,
               runner: dict[CaseId, Outcome],
               held: list[CaseId] | None = None,
               listed: dict[str, CaseId] | None = None,
               kind: str = "branch models") -> None:
    """Print the input, what each branch model of `space` emits and what
    each case the runner holds gives, then the ones that
    emit nothing. Models that emit the same thing are listed together above
    the one printing of it: on one line, joined by ", ", or one per indented
    line, then a line of ":", when that one line would pass 100 characters. A case the runner holds that gives no grid is
    undefined there. `held`, when given, stands in for the branch models:
    each held case, by the label the run spells it with. `listed`, when
    given, stands in for them as well: each case by the name it has there
    (`dl.witness.listed_models`), and `kind` is what the last line calls
    them."""
    print("input:")
    for line in _grid_lines(grid):
        print(f"  {line}")
    by_case: dict[CaseId, list] = {}
    for c in actuals:
        fine = model_label(c.case, resolution)
        by_case.setdefault(fine, []).append(c)
        if (coarse := case_label(c.case, resolution)) != fine:
            by_case.setdefault(coarse, []).append(c)
    models: dict[str, CaseId] = ({c: c for c in held} if held is not None
                                 else dict(listed) if listed is not None
                                 else space.models())
    for name, got in runner.items():
        by_case[name] = [Candidate(name, got, [], [])] if got else []
        models[name] = name
    bodies: dict[str, list[str]] = {}
    named: dict[str, list[str]] = {}
    silent: list[str] = []
    grids: set = set()
    for name, case in models.items():
        cands = by_case.get(case)
        if not cands:
            silent.append(name)
            continue
        grids |= {tuple(tuple(row) for row in c.grid)
                  for c in cands if not c.error}
        body = _model_body(cands, resolution)
        key = "\n".join(body)
        bodies.setdefault(key, body)
        named.setdefault(key, []).append(name)
    for key, body in bodies.items():
        print()
        joined = ", ".join(named[key])
        if len(joined) > 100:
            for name in named[key]:
                print(f"  {name}")
            print(":")
        else:
            print(f"{joined}:")
        for line in body:
            print(line)
    if silent:
        print()
        for name in silent:
            print(f"{name}: undefined" if name in runner
                  else f"{name}: emits nothing")
    if len(models) > 1:
        extra = (f", {len(runner)} case(s) that take a `@derive` or "
                 f"`@store` branch" if runner else "")
        print()
        if held is not None:
            kind = "held cases"
        print(f"{len(models) - len(runner)} {kind}{extra}, "
              f"{len(grids)} distinct grid(s)")


def cmd_grid(stem: str, path: str | None = None, every: bool = False,
             only: list[str] | None = None,
             assign_text: str | None = None) -> int:
    """Run one solver on a grid the caller wrote, in place of a stored pair,
    and print what each case `record` writes emits, as `record` prints it,
    or with `every` what each held case emits, spelled in full, or with
    `only` what each case those names resolve to emits, or the held cases
    that stand for it (`dl.models.CaseSpace.stand_ins`). With
    `assign_text`, every run, the cases that take a `@derive` or `@store`
    branch too, reads the assigned source."""
    if _missing(stem):
        return 2
    assign = _assign_arg(assign_text)
    if assign is None:
        return 2
    solver, _ = solver_file(stem)
    source = solver.read_text()
    if bad := assign_findings(assign, source):
        for line in bad:
            print(line, file=sys.stderr)
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
        run = _case_run(stem, solver, source, grid, assign)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    space, actuals, runner, held = run.space, run.actuals, run.runner, run.held

    if only:
        given: dict[CaseId, str] = {}
        for value in only:
            case = space.denoted(value)
            if case is None:
                print(f"no case of {stem} is `{value}`", file=sys.stderr)
                return 2
            stand_ins = space.stand_ins(value, held)
            if not stand_ins:
                print(f"`impl_choice` holds no case of {stem} that takes the "
                      f"branches of `{value}`", file=sys.stderr)
                return 2
            for stand_in in stand_ins:
                given.setdefault(stand_in, value if stand_in == case
                                 else space.short_name(stand_in))
        kept = {c: runner[c] for c in given if c in runner}
        _print_run(grid, actuals, space, res_out_stem(stem), kept,
                   listed={v: c for c, v in given.items() if c not in runner},
                   kind="other case(s)")
    elif every:
        _print_run(grid, actuals, space, res_out_stem(stem), runner,
                   space.plain)
    else:
        _print_run(grid, actuals, space, res_out_stem(stem), runner,
                   listed=recorded_models(space, held), kind="cases")
    return 0


def cmd_relation(stem: str, args: list[str],
                 assign_text: str | None = None) -> int:
    """Run one solver on a grid the caller wrote and print the rows of each
    relation `args` names. The last of `args` is the grid file when it is
    `-` or names a file; stdin gives the grid otherwise."""
    if _missing(stem):
        return 2
    path = None
    if len(args) > 1 and (args[-1] == "-" or Path(args[-1]).is_file()):
        args, path = args[:-1], args[-1]
    assign = _assign_arg(assign_text)
    if assign is None:
        return 2
    solver, _ = solver_file(stem)
    source = solver.read_text()
    if bad := assign_findings(assign, source):
        for line in bad:
            print(line, file=sys.stderr)
        return 2
    text = _grid_text(path)
    if text is None:
        return 2
    if len(_sections(text)) > 1:
        print(f"`{SEPARATOR}` belongs to `record`; `relation` takes one grid",
              file=sys.stderr)
        return 2
    grid = _parse_grid(text)
    if grid is None:
        return 2

    build_functors()
    if _compile_failed(stem):
        return 1
    run_source = assigned_source(source, assign)
    try:
        space = case_space(run_source,
                           case_branches(stem, run_source, grid))
        rels = relation_rows(run_source, args, grid, space,
                             solver_path=solver)
    except MissingRelations as e:
        for name in e.names:
            print(f"no relation `{name}`", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    for i, name in enumerate(args):
        rel = rels[name]
        if i:
            print()
        head = f"{name}({', '.join(rel.columns)})"
        if not rel.rows:
            print(f"{head}: no rows")
            continue
        print(f"{head}:")
        for row in rel.rows:
            print("  " + "\t".join(row))
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
        print("--assign takes a JSON object",
              file=sys.stderr)
        return None
    return assign


def cmd_format(stem: str, witness_file: str | None = None) -> int:
    """Rewrite the task's witness file, or `witness_file` in its place,
    through the serializer."""
    if _missing(stem):
        return 2
    task_id = solver_file(stem)[1]
    path = _witness_file(task_id, witness_file)
    if path is None:
        return 2
    if not path.exists():
        print(f"no witness file at {path}", file=sys.stderr)
        return 2
    if not _write_record(task_id, path, []):
        return 2
    print(f"formatted {path}")
    return 0


def _witness_file(task_id: str, witness_file: str | None,
                  corpus: bool = False) -> Path | None:
    """The witness file a writing command writes: `witness_file` when
    given, and the task's otherwise. None when the command writes nothing,
    with the reason printed: a run over every solver is read-only, and no
    command creates a file in the witness directory, whichever path names
    it."""
    if corpus:
        print(CORPUS_READ_ONLY)
        return None
    path = Path(witness_file) if witness_file else witness_path(task_id)
    witness_dir = witness_path(task_id).parent.resolve()
    if not path.exists() and path.resolve().is_relative_to(witness_dir):
        shown = path.resolve()
        if shown.is_relative_to(REPO_ROOT.resolve()):
            shown = shown.relative_to(REPO_ROOT.resolve())
        print(NO_WITNESS_FILE.format(path=shown), file=sys.stderr)
        return None
    return path


CORPUS_READ_ONLY = mctx("read-only over every solver: a run on this stem alone "
                        "records the witnesses below")
NO_WITNESS_FILE = mctx("no witness file at {path}: the Write operation "
                       "copies the Analyze file there")


def _record_outcomes(stem: str, solver: Path, source: str,
                     grid: list[list[int]], assign: dict,
                     show: bool) -> dict[str, Outcome]:
    """What each case `record` writes gives on `grid` at `assign`: the
    cases `dl.witness.recorded_models` names, and the cases that take a
    `@derive` or `@store` branch (`dl.models.enumeration` of `source`).
    With `show`, the run is printed as `record` prints it. A failed or
    timed-out run raises."""
    run = _case_run(stem, solver, source, grid, assign)
    resolution = res_out_stem(stem)
    if show:
        _print_run(grid, run.actuals, run.space, resolution, run.runner,
                   listed=recorded_models(run.space, run.held), kind="cases")
    return branch_outcomes(run.space, run.actuals, resolution,
                           run.held) | run.runner


@dataclass(frozen=True)
class CaseRun:
    """One run of a solver on one grid at one assignment: its case space
    (`dl.models.enumeration`), what the run emits (`actuals`), what each
    case that takes a `@derive` or `@store` branch gives (`runner`), and
    the cases `impl_choice` holds on the grid, spelled in full, None when
    the solver declares no `impl_choice` (`held`)."""

    space: Cases
    actuals: list
    runner: dict[CaseId, Outcome]
    held: list[CaseId] | None


def _case_run(stem: str, solver: Path, source: str, grid: list[list[int]],
              assign: dict) -> CaseRun:
    """What `record` and `grid` read of one run of `source` at `assign` on
    `grid`. A failed or timed-out run raises."""
    space = enumeration(source)
    run_source = assigned_source(source, assign)
    actuals = run_dl_source(run_source, grid, solver_path=solver)
    runner = held_outcomes(stem, space, list(space.runner), grid,
                           run_source)
    try:
        held = held_cases(parse(run_source), run_source, grid, full=True)
    except ParseError:
        held = None
    return CaseRun(space, actuals, runner, held)


def _write_record(task_id: str, path: Path, entries: list[dict]) -> bool:
    """Put `entries` into the witness file at `path` and write it
    (`dl.witness.write_entries`). False when the shape check stops the
    write, which is reported."""
    try:
        write_entries(task_id, path, entries)
    except ValueError as e:
        print(e, file=sys.stderr)
        return False
    return True


def _record(stem: str, source: str, entry_id: str, separates: str,
            grid: list[list[int]], target: Path | None,
            assign: dict | None = None,
            judged: list[list[int]] | None = None) -> int:
    """Run the solver `source` on `grid` and write the run into the witness
    file at `target` as the entry `entry_id`, printing the run as `record`
    prints it: one group per distinct outcome of the cases
    `_record_outcomes` runs, or the judged output `judged`. The entry
    replaces an entry of its id. With no `target`, nothing is written."""
    solver, task_id = solver_file(stem)
    assign = assign or {}
    try:
        outcomes = _record_outcomes(stem, solver, source, grid, assign, True)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if judged is not None:
        _print_judged(judged)
        output: object = judged
    else:
        output = grouped_output(outcomes)
    entry: dict = {"id": entry_id, "separates": separates, "input": grid}
    if assign:
        entry["assign"] = assign
    entry["output"] = output
    print()
    if target is None:
        print(f"would record witness `{entry_id}`")
        return 0
    if not _write_record(task_id, target, [entry]):
        return 2
    print(f"wrote witness `{entry_id}` to {target}")
    return 0


def _print_judged(judged: list[list[int]]) -> None:
    print()
    print("judged output:")
    for line in _grid_lines(judged):
        print(f"  {line}")


def cmd_record(stem: str, entry_id: str, separates: str,
               path: str | None = None, assign_text: str | None = None,
               witness_file: str | None = None) -> int:
    """Run one solver on a grid the caller wrote and write the run into the
    task's witness file, or `witness_file` in its place, as the entry
    `entry_id`: one group per distinct outcome of the cases
    `_record_outcomes` runs. An `assign` that `dl.witness.assign_findings`
    finds fault with stops the run."""
    if _missing(stem):
        return 2
    assign = _assign_arg(assign_text)
    if assign is None:
        return 2
    solver, task_id = solver_file(stem)
    source = solver.read_text()
    if bad := assign_findings(assign, source):
        for line in bad:
            print(f"{entry_id}: {line}", file=sys.stderr)
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
    target = _witness_file(task_id, witness_file)
    if target is None:
        return 2
    read_witness_data(task_id, target)  # a file that fails the shape check stops the run

    build_functors()
    if _compile_failed(stem):
        return 1
    code = _record(stem, source, entry_id, separates, grid, target, assign,
                   judged)
    if code:
        return code
    if hint := _record_hint(stem, source, entry_id, separates):
        print(hint)
    return 0


def _groups_change(old: dict[str, Outcome] | list[dict], new: list[dict]) -> str:
    """How a witness's new groups differ from its old output: unchanged, or
    changed with the count of cases they list that the old groups did not,
    and the reverse."""
    before = grouped_output(old) if isinstance(old, dict) else old
    if before == new:
        return "groups unchanged"
    listed = {c for g in before for c in g["cases"]}
    now = {c for g in new for c in g["cases"]}
    new_n, gone_n = len(now - listed), len(listed - now)
    return (f"groups changed: {new_n} case{'s' if new_n != 1 else ''} "
            f"newly listed, {gone_n} no longer listed")


class AssignFault(ValueError):
    """A stored `assign` that `dl.witness.assign_findings` finds fault
    with."""


def _failure(e: Exception) -> str:
    """The line a witness `record` could not run again gets."""
    if isinstance(e, AssignFault):
        return str(e)
    return f"run failed: {type(e).__name__}: {e}"


def _rerecorded(stem: str, solver: Path, source: str, entry: dict,
                show: bool) -> tuple[dict, str]:
    """The witness `entry` with its groups recomputed as `record` computes
    them, on its stored input and `assign`, and a line on what changed. A
    witness of the `other` verdict keeps its judged output; it is run only
    with `show`. A faulty `assign` or a failed run raises."""
    assign = entry.get("assign", {})
    if bad := assign_findings(assign, source):
        raise AssignFault("; ".join(bad))
    judged = not _is_groups_output(entry["output"])
    if judged and not show:
        return entry, "judged output kept"
    outcomes = _record_outcomes(stem, solver, source, entry["input"], assign,
                                show)
    if judged:
        _print_judged(entry["output"])
        return entry, "judged output kept"
    groups = grouped_output(outcomes)
    return {**entry, "output": groups}, _groups_change(entry["output"],
                                                       groups)


def _is_groups_output(output: object) -> bool:
    """The output holds per-case outcomes, in groups or in the object form;
    a judged output is a grid."""
    return isinstance(output, dict) or (
        isinstance(output, list) and all(isinstance(g, dict) for g in output))


def cmd_rerecord(stem: str, entry_id: str,
                 witness_file: str | None = None) -> int:
    """Run the witness `entry_id` of the task's witness file, or of
    `witness_file` in its place, again on its stored input and `assign`,
    and rewrite its groups as `record` writes them. Its id, separates,
    input and `assign` stay as they are."""
    if _missing(stem):
        return 2
    solver, task_id = solver_file(stem)
    target = _witness_file(task_id, witness_file)
    if target is None:
        return 2
    data = read_witness_data(task_id, target)
    entry = next((e for e in data["witnesses"] if e["id"] == entry_id), None)
    if entry is None:
        print(f"no witness `{entry_id}` in {target}; a new witness takes "
              f"`--separates`", file=sys.stderr)
        return 2
    build_functors()
    if _compile_failed(stem):
        return 1
    try:
        entry, change = _rerecorded(stem, solver, solver.read_text(), entry,
                                    True)
    except Exception as e:
        print(f"{entry_id}: {_failure(e)}", file=sys.stderr)
        return 1
    if not _write_record(task_id, target, [entry]):
        return 2
    print()
    print(f"re-recorded witness `{entry_id}` in {target}: {change}")
    return 0


def cmd_record_all(stem: str, witness_file: str | None = None) -> int:
    """Re-record every witness of the task's witness file, or of
    `witness_file` in its place, as `cmd_rerecord` does one. The file is
    written once, after every run; when any run fails, it is not written."""
    if _missing(stem):
        return 2
    solver, task_id = solver_file(stem)
    target = _witness_file(task_id, witness_file)
    if target is None:
        return 2
    if not target.exists():
        print(f"no witness file at {target}", file=sys.stderr)
        return 2
    data = read_witness_data(task_id, target)
    build_functors()
    if _compile_failed(stem):
        return 1
    source = solver.read_text()
    entries = data["witnesses"]
    with ThreadPoolExecutor(max_workers=_pool_workers()) as pool:
        runs = [pool.submit(_rerecorded, stem, solver, source, e, False)
                for e in entries]
    failed = 0
    changed = 0
    for i, (entry, run) in enumerate(zip(entries, runs, strict=True)):
        try:
            entries[i], change = run.result()
        except Exception as e:
            failed += 1
            print(f"{entry['id']}: {_failure(e)}")
            continue
        changed += change.startswith("groups changed")
        print(f"{entry['id']}: {change}")
    n = len(entries)
    if failed:
        print(f"wrote nothing to {target}: {failed} of {n} witnesses could "
              f"not be run")
        return 1
    if not _write_record(task_id, target, entries):
        return 2
    print(f"re-recorded {n} witness{'es' if n != 1 else ''} in {target}: "
          f"{changed} with changed groups")
    return 0


def _record_hint(stem: str, source: str, entry_id: str,
                 separates: str) -> str | None:
    """The line the session adds for the entry: the `@derive` form when the
    id is a derivation of the solver that no line is yet, the `@store` form
    when it is a relation the runner stores that no line is yet, and
    otherwise the `@witness` form, which a witness of a claim takes and a
    witness that only separates cases does not. What the id's parts that
    hold `=` are comes from the case space (`CaseSpace.branch_parts`):
    `<param>=stored` of a `@derive` parameter is its stored value, which
    takes the `@witness` form. Nothing when that line already stands, and
    nothing for a further witness of a `@derive` or `@store` line's branch
    (`line_branch_witness`)."""
    if any(b.name == entry_id for b in branch_lines(source)):
        return None
    named = [p.strip() for p in entry_id.split("&") if "=" in p]
    if len(named) == 1 and case_space(source).branch_parts(entry_id) is None:
        name, _, tail = named[0].partition("=")
        if tail == STORED:
            return store_hint(name, relation_site(source, name))
        if tail in per_grid_candidates(stem).get(name, []):
            return derive_hint(tail)
    if (line_branch_witness(separates, source)
            or any(w.id == entry_id for w in witness_blocks(source))):
        return None
    return (f"when it is a branch's witness or a witness of the concept "
            f"case, add: // @witness {entry_id}: <plausibility> <verdict>")


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
                print(f"  {solver_name(stem)}: {line}")

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
                print(f"  {solver_name(s)}: {line}")

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


def _sweep_text(stem: str, cached: bool) -> tuple[str, None] | tuple[None, str]:
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
        swept = _sweep_text(stem, cached)
        if swept[0] is None:
            skipped.append({"stem": stem, "reason": swept[1]})
            continue
        sweeps.append((stem, open_params(swept[0])))
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


REPORT_FAILURES = (ValueError, RuntimeError, subprocess.TimeoutExpired)
"""What a witness report raises when it cannot finish: a solver or witness
file it cannot read, a Souffle run that fails, or one that times out. A
process pool that breaks raises a RuntimeError as well."""


def _print_witness(stem: str, file: Path | None = None,
                   every_case: bool = False, own: bool = False) -> int:
    """The features each `@witness` line of `stem` states, then its witness
    report, against `file` when given, with `impl_choice` holding every case
    under `every_case`. With `own`, `file` is read as the task's own witness
    file. Non-zero on a failing finding."""
    path, task_id = solver_file(stem)
    witness = load_witness_file(file) if file else load_witnesses(task_id)
    print("`@witness` lines:")
    for line in annotation_lines(path.read_text()):
        print(f"  {line}")
    print()
    if witness is None:
        print(f"no witness file at {file or witness_path(task_id)}")
    else:
        grids = len(witness.entries)
        print(f"{grids} witness grid{'s' if grids != 1 else ''} run")
    try:
        findings = witness_report(stem, file, every_case, own)
    except REPORT_FAILURES as err:
        command = "witness --every-case" if every_case else "witness"
        print(f"{command}: {err}", file=sys.stderr)
        return 2
    for line in finding_lines(findings):
        print(f"  {line}")
    passed = passes(findings, file is not None and not own)
    if passed:
        print(pass_line(findings))
    return 0 if passed else 1


def _print_shape(path: Path) -> int:
    """The shape findings of the witness file at `path`. Non-zero on a
    finding."""
    findings = file_shape(path)
    for line in findings:
        print(line)
    return 1 if findings else 0


def cmd_witness(stem: str | None, file: str | None = None,
                every_case: bool = False,
                witness_file: str | None = None) -> int:
    """Run the task's witness grids through the solver, or the grids of
    `file`, and report each case whose output differs from the one its entry
    names. `witness_file` stands in for the task's witness file, and the
    report is whole. The file's shape is checked first. Without a stem, the
    shape check of `file` is the whole report."""
    if file is not None and witness_file is not None:
        print("witness: give `--file` or `--witness-file`, not both",
              file=sys.stderr)
        return 2
    if stem is None and witness_file is not None:
        print("witness: `--witness-file` takes a task id", file=sys.stderr)
        return 2
    own = witness_file is not None
    file = file or witness_file
    if stem is None and file is None:
        print("witness: give a task id, `--file`, or both", file=sys.stderr)
        return 2
    if file is not None and not Path(file).exists():
        print(f"no witness file at {file}", file=sys.stderr)
        return 2
    if stem is None and file is not None:
        if _print_shape(Path(file)):
            return 1
        print(WITNESS_FILE_OK)
        return 0
    if stem is None or _missing(stem):
        return 2
    path = Path(file) if file else witness_path(solver_file(stem)[1])
    if path.exists() and _print_shape(path):
        return 1
    build_functors()
    if _compile_failed(stem):
        return 1
    return _print_witness(stem, Path(file) if file else None, every_case,
                          own)


def _print_derive(stem: str, file: Path | None = None) -> int:
    """The derive report's findings, against `file` in place of the task's
    witness file when given. Non-zero on a finding."""
    report = derive_report(stem, file)
    lines = render_findings(report)
    passed = lines[-1] == DERIVE_OK
    for line in (lines[:-1] if passed else lines):
        print(f"  {line}")
    if passed:
        print(DERIVE_OK)
    return 0 if passed else 1


def cmd_derive(stem: str, witness_file: str | None = None,
               corpus: bool = False) -> int:
    """The derivations of the solver's stored parameters, each with its
    witness and the line that records the judgment. Each witness the report
    builds is recorded under the branch's name into the task's witness
    file, or `witness_file` in its place, with the derivation's `@derive`
    line standing, and printed as `record` prints it. With `corpus`, the
    witnesses are printed and not recorded."""
    if _missing(stem):
        return 2
    build_functors()
    task_id = solver_file(stem)[1]
    report = derive_report(stem, Path(witness_file) if witness_file else None)
    for line in render_derive(report):
        print(line)
    built = [d for d in report.derivations
             if d.swap is not None and not d.entry and d.source]
    if not built:
        return 0
    target = _witness_file(task_id, witness_file, corpus)
    if target is None and not corpus:
        return 2
    code = 0
    for d in built:
        assert d.swap is not None
        print()
        code = code or _record(
            stem, d.source, d.case,
            mctx("`{case}` from the stored value: {grid} with {stored} and "
                 "{free} swapped").format(
                case=d.case, grid=d.swap.grid, stored=d.swap.stored,
                free=d.swap.free),
            d.swap.input, target)
    return code


def _print_store(stem: str, file: Path | None = None) -> int:
    """The store report's findings, against `file` in place of the task's
    witness file when given. Non-zero on a finding."""
    lines = render_store_findings(store_report(stem, file))
    passed = STORE_OK in lines
    for line in lines:
        print(line if line == STORE_OK else f"  {line}")
    return 0 if passed else 1


def cmd_store(stem: str, witness_file: str | None = None,
              corpus: bool = False) -> int:
    """The program relations that hold one value on every input, each with
    its witness and the line that records the judgment. Each witness the
    report builds for a relation with a value to store is recorded under
    the branch's name into the task's witness file, or `witness_file` in
    its place, with the relation's `@store` line standing, and printed as
    `record` prints it. With `corpus`, the witnesses are printed and not
    recorded."""
    if _missing(stem):
        return 2
    build_functors()
    solver, task_id = solver_file(stem)
    source = solver.read_text()
    report = store_report(stem, Path(witness_file) if witness_file else None)
    for line in render_store(report):
        print(line)
    built = []
    for f in report.found:
        if (f.kind != OWNED or not f.held or f.folded or f.entry
                or f.move is None or f.move.input is None
                or (f.colors and f.line is None)):
            continue
        run_source = source if f.line is not None else lined(source, f)
        if run_source is not None:
            built.append((f, run_source))
    if not built:
        return 0
    target = _witness_file(task_id, witness_file, corpus)
    if target is None and not corpus:
        return 2
    code = 0
    for f, run_source in built:
        assert f.move is not None and f.move.input is not None
        print()
        code = code or _record(
            stem, run_source, f.case_id,
            mctx("`{case}` from the derived value: {grid} {change}").format(
                case=f.case_id, grid=f.move.grid, change=f.move.change),
            f.move.input, target)
    return code


def cmd_audit(stem: str, time_limit: float = TIME_LIMIT_SECONDS,
              witness_file: str | None = None) -> int:
    """The evidence audits of a finished solver: parameter value sweep,
    deletions, witness, dropped cases, derive, store. The sweep runs under
    the time limit, and the others run after it. `witness_file` stands in
    for the task's witness file in every section that reads it."""
    if _missing(stem):
        return 2
    file = Path(witness_file) if witness_file else None
    if file is not None and not file.exists():
        print(f"no witness file at {file}", file=sys.stderr)
        return 2
    build_functors()
    if _compile_failed(stem):
        return 1
    # The every-case run is the audit's longest step, and it shares nothing
    # with the other steps, so it runs beside them. Its time goes to Python,
    # so it runs in a process of its own. The derive and store sections
    # print after it, in the order the audit gives.
    later = io.StringIO()
    with ProcessPoolExecutor(max_workers=1,
                             mp_context=get_context("spawn")) as pool:
        every_case = pool.submit(witness_report, stem, file, True,
                                 file is not None)
        print("--- sweep ---")
        _print_sweep(stem, MAX_CANDIDATES, time_limit)
        print()
        print("--- deletions ---")
        deletions = _print_deletions(stem)
        print()
        print("--- witness ---")
        witness = _print_witness(stem, file, own=file is not None)
        print()
        with redirect_stdout(later):
            print("--- derive ---")
            derive = _print_derive(stem, file)
            print()
            print("--- store ---")
            store = _print_store(stem, file)
        print("--- dropped cases ---")
        dropped = _print_dropped(every_case)
    print()
    print(later.getvalue(), end="")
    return deletions or witness or dropped or derive or store


DROPPED_OK = "dropped cases: ok"


def _print_dropped(run: Future[list[Drift]]) -> int:
    """Each case that `impl_choice` drops and that fails no case condition in
    the `witness --every-case` run of `run`. The run's other findings are
    the witness section's or follow from the drop. Non-zero on a line."""
    try:
        findings = run.result()
    except REPORT_FAILURES as err:
        print(f"dropped cases: not checked: {err}")
        return 0
    unmet = [d for d in findings if d.kind == DROPPED and not d.note]
    for line in finding_lines(unmet):
        print(f"  {line}")
    if unmet:
        return 1
    print(DROPPED_OK)
    return 0


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
    swept = _sweep_text(stem, cached=True)
    if swept[0] is None:
        print(f"{stem}: {swept[1]}", file=sys.stderr)
        skipped.append({"stem": stem, "reason": swept[1]})
        return None
    return len(open_params(swept[0])), len(settled_params(swept[0]))


def cmd_features(stem: str | None = None, run: bool = False,
                 as_json: bool = False) -> int:
    """Per-case features of each named solver, one row per case. The static
    columns read the source; the dynamic ones need `--run`, which runs every
    pair of every named solver, train and test alike."""
    if stem and _missing(stem):
        return 2
    stems = [stem] if stem else all_stems()
    build_functors()
    files: list[FileFeatures] = []
    skipped: list[dict[str, str]] = []
    bad = False
    for s in stems:
        try:
            source = solver_file(s)[0].read_text()
            dynamic = run_features(s, enumeration(source)) if run else None
            files.append(features_report(s, _sweep_counts(s, skipped), dynamic))
        except (ParseError, RuntimeError) as e:
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


COMMANDS = ("run", "lint", "grid", "relation", "record", "sweep", "deletions", "audit",
            "determination-plan", "size",
            "keywords", "expand", "since", "drop-one", "derived-constant", "features",
            "witness", "derive", "store")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=mctx("Run Souffle solvers and their checks."),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser(
        "run",
        help=mctx("pairs, lint and determination checks; the command run when "
                  "the first argument is not a command"),
        epilog=RUN_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    lint = sub.add_parser(
        "lint", help=mctx("lint only, no pair runs"),
        description=mctx("A hint changes neither the verdict nor the exit "
                         "code."),
    )
    run.add_argument("stems", nargs="*",
                     help=mctx("the solvers to run, each a stem or a path to "
                               "a solver file whose name starts with the task "
                               "id. One solver runs its pairs, lint and "
                               "determination check; several give the report "
                               "of a run over every solver, over those "
                               "solvers; none runs every solver."))
    lint.add_argument("stem", nargs="?", help=STEM_OR_ALL_HELP)
    for p in (run, lint):
        p.add_argument("--hints", action=argparse.BooleanOptionalAction,
                       default=True, help=mctx("include the hints section"))
    run.add_argument("--time", action="store_true", dest="timed",
                     help=mctx("print wall times: per phase for one solver, "
                               "the slowest 15 for more than one"))
    run.add_argument("--pairs", metavar="FILE",
                     help=mctx("run the one solver given against the pairs "
                               "of this JSON file in place of the task's; "
                               'for a pair without "output", print the '
                               "grids the solver emits"))

    grid = sub.add_parser(
        "grid",
        help=mctx("run one solver on a grid you write, printing what each "
                  "case the runner holds emits"),
        description=mctx("Prints the output of the concept case, of each "
                         "branch's model, and of each other case the runner "
                         "holds, by the names `record` writes. When "
                         "`impl_choice` does not contain the case of a branch's "
                         "model or of a `--case` name, the cases "
                         "`impl_choice` contains that take its branches and "
                         "differ from the concept case at the fewest choice "
                         "points are printed in its place. Cases that emit "
                         "the same output are listed "
                         "together above that output: on one line, joined by "
                         "`, ` and ending in `:`, or, when that line would "
                         "pass 100 characters, one per indented line and "
                         "then a line of `:`. After them come `<case>: emits "
                         "nothing` for each case that emits no grid, and "
                         "`<case>: undefined` for each case that takes a "
                         "`@derive` or `@store` branch and emits none."),
        epilog=GRID_HELP,
    )
    grid.add_argument("stem", help=STEM_HELP)
    grid.add_argument("file", nargs="?",
                      help=mctx("grid file; stdin when omitted or `-`"))
    shown = grid.add_mutually_exclusive_group()
    shown.add_argument("--all", action="store_true", dest="every",
                       help=mctx("spell each case `impl_choice` contains by "
                                 "its constructor at each choice point, in "
                                 "place of its name"))
    shown.add_argument("--case", action="append", dest="cases",
                       metavar="CASE",
                       help=mctx("print only this case; repeat for each "
                                 "case"))
    grid.add_argument("--assign", metavar="JSON", dest="assign",
                      help=ASSIGN_HELP)

    relation = sub.add_parser(
        "relation",
        help=mctx("run one solver on a grid you write, printing the rows of "
                  "the relations you name"),
        description=mctx("Prints each relation's rows as Souffle writes "
                         "them, one fact per line, under the relation's "
                         "attribute names. A column of type `Choice` holds "
                         "each case by its shortest name. The last argument "
                         "is the grid file when it is `-` or names a file; "
                         "otherwise the grid is read from stdin."),
        epilog=GRID_HELP,
    )
    relation.add_argument("stem", help=STEM_HELP)
    relation.add_argument("args", nargs="+", metavar="relation",
                          help=mctx("a relation, `inst.rel` for one of an "
                                    "instance; then the grid file, if any"))
    relation.add_argument("--assign", metavar="JSON", dest="assign",
                          help=ASSIGN_HELP)

    record = sub.add_parser(
        "record",
        help=mctx("run one solver on a grid you write and write the run into "
                  "the task's witness file"),
        description=mctx("The witness replaces a witness with the same id. "
                         "For an `other` verdict, put the judged output "
                         "after a `---` line of the grid text. Without "
                         "`--separates`, record runs the witness of that id "
                         "again on the input and `assign` the file holds "
                         "for it, and writes only its groups; `--all` does "
                         "this for every witness of the file. A witness "
                         "with verdict `other` keeps its judged output."),
        epilog=GRID_HELP,
    )
    record.add_argument("stem", help=STEM_HELP)
    record.add_argument("id", nargs="?",
                        help=mctx("the witness's id; required unless "
                                  "`--format` or `--all`"))
    record.add_argument("file", nargs="?",
                        help=mctx("grid file; stdin when omitted or `-`"))
    record.add_argument("--separates",
                        help=mctx("what the witness separates; required "
                                  "for a new witness"))
    record.add_argument("--assign", metavar="JSON", dest="assign",
                        help=mctx("the witness's `assign` object"))
    record.add_argument("--all", action="store_true", dest="every",
                        help=mctx("run every witness of the file again; the "
                                  "file is written only when every run "
                                  "succeeds"))
    record.add_argument("--witness-file", metavar="PATH",
                        dest="witness_file",
                        help=mctx("a witness file to read and write in "
                                  "place of the task's"))
    record.add_argument("--format", action="store_true", dest="as_format",
                        help=mctx("rewrite the task's witness file through "
                                  "the serializer and add no witness"))

    sweep = sub.add_parser(
        "sweep", help=mctx("parameter value sweep only"),
        description=mctx("For each Params parameter, the values of its "
                         "domain that reproduce every train pair. A ✓ marks "
                         "a parameter that a whole sweep finds the train "
                         "pairs fix to its stored value."),
    )
    sweep.add_argument("stem", nargs="?", help=STEM_HELP)
    sweep.add_argument("cap", nargs="?", type=int, default=MAX_CANDIDATES,
                       help=mctx("the most candidates the sweep tries for one "
                                 "parameter; when a parameter has more, the "
                                 "sweep tries only single-column changes of "
                                 "the stored facts, or single-row changes "
                                 "for a parameter swept as a set, up to that "
                                 "count"))
    sweep.add_argument("--time-limit", type=float, dest="time_limit",
                       default=TIME_LIMIT_SECONDS, help=TIME_LIMIT_HELP)
    over = sweep.add_mutually_exclusive_group()
    over.add_argument("--open", nargs="+", metavar="STEM", dest="open_stems",
                      help=mctx("report as JSON, for these solvers, the "
                                "parameters each sweep leaves open and the "
                                "`// review sweep:` line each one takes"))
    over.add_argument("--mark", nargs="+", metavar="STEM", dest="mark_stems",
                      help=mctx("write that `// review sweep:` line into the "
                                "solver for each open parameter that has none "
                                "yet. The report lists each line written, and "
                                "each lint finding on the header after the "
                                "write"))
    sweep.add_argument("--cached", action="store_true",
                       help=mctx("with `--open` or `--mark`, take only the "
                                 "solvers whose cached sweep matches their "
                                 "current code, or carries no hash to match, "
                                 "and skip the rest with a reason. A solver "
                                 "whose only change since the sweep is a "
                                 "comment line still matches"))

    sub.add_parser(
        "deletions", help=mctx("deletion report only"),
        description=mctx("The clauses and facts of the solver that no train "
                         "pair needs."),
    ).add_argument("stem", help=STEM_HELP)
    audit = sub.add_parser(
        "audit",
        help=mctx("parameter value sweep + deletion report + witness report "
                  "+ dropped case report + derive report + store report; writes no "
                  "witness"),
    )
    audit.add_argument("stem", help=STEM_HELP)
    audit.add_argument("--time-limit", type=float, dest="time_limit",
                       default=TIME_LIMIT_SECONDS, help=TIME_LIMIT_HELP)
    audit.add_argument("--witness-file", metavar="PATH", dest="witness_file",
                       help=mctx("a witness file to read in place of the "
                                 "task's"))
    sub.add_parser(
        "drop-one",
        help=mctx("which stored facts of a multi-fact parameter no train pair "
                  "needs"),
        description=mctx("A fact that only the test pairs need is reported "
                         "apart from one that no pair needs."),
    ).add_argument("stem", help=STEM_HELP)
    sub.add_parser(
        "derived-constant",
        help=mctx("program relations that hold the same tuples on every "
                  "example"),
        description=mctx("The examples are the train and test examples. A "
                         "relation that is empty on every example is left "
                         "out, and so is one that keeps its tuples on "
                         "grids made from each example's palette."),
    ).add_argument("stem", help=STEM_HELP)
    witness = sub.add_parser(
        "witness",
        help=mctx("run the task's witness grids and report where the solver "
                  "and the witness file disagree"),
        description=mctx("The report checks the file's shape first. With "
                         "--file and no stem, the shape check is the whole "
                         "report, and it needs no solver."),
    )
    witness.add_argument("stem", nargs="?",
                         help=mctx("a task id, or the path to a solver file "
                                   "whose name starts with the task id; a "
                                   "path run reads that task id's witness "
                                   "file too"))
    witness.add_argument("--file", metavar="PATH",
                         help=mctx("a witness file to read in place of the "
                                   "task's; the report has only the findings "
                                   "on its witnesses"))
    witness.add_argument("--witness-file", metavar="PATH",
                         dest="witness_file",
                         help=mctx("a witness file to read in place of the "
                                   "task's; the report is the one the "
                                   "task's file gets"))
    witness.add_argument("--every-case", action="store_true",
                         help=mctx("run with `impl_choice` holding every "
                                   "case of `Choice`; for each case the "
                                   "solver drops, print the first of these "
                                   "the runs show: it fails Fit, no witness "
                                   "separates it from another case, it "
                                   "fails Subsumption, or it fails none of "
                                   "them"))
    derive = sub.add_parser(
        "derive",
        help=mctx("the built-in derivations of stored parameters that fit, "
                  "each a branch; writes each witness it builds into the "
                  "task's witness file"),
        description=mctx("Each stored parameter whose value a proposer of "
                         "`programs/proposers.dl` derives on every input, "
                         "with the witness that separates the cases that "
                         "take the derivation's branch from the cases that "
                         "take the stored value there and the same branches "
                         "elsewhere. The command writes each witness it "
                         "builds into the task's witness file, as `record` "
                         "writes one, with the `@derive` line standing, and keeps "
                         "a witness the file already holds for the branch."),
    )
    store = sub.add_parser(
        "store",
        help=mctx("the program relations that hold one value on every "
                  "input; writes each witness it builds into the task's "
                  "witness file"),
        description=mctx("Each program relation between `in` and `out` whose "
                         "value over a subset of its columns is the same on "
                         "every input of the task, with the witness that "
                         "separates the cases that take its `<rel>=stored` "
                         "branch from the cases that take the derived value "
                         "there and the same branches elsewhere. The command "
                         "writes each witness it builds into the task's "
                         "witness file, as `record` writes one, with the `@store` "
                         "line standing, and keeps a witness the file "
                         "already holds for the branch. A relation with "
                         "more than 20000 rows on some input is not checked: "
                         "that is too many rows to be a stored value."),
    )
    for p in (derive, store):
        p.add_argument("stem", nargs="?",
                       help=mctx("a task id, or the path to a solver file "
                                 "whose name starts with the task id; every "
                                 "solver when omitted, and then the command "
                                 "writes nothing"))
        p.add_argument("--witness-file", metavar="PATH", dest="witness_file",
                       help=mctx("a witness file to read and write in place "
                                 "of the task's"))
    plan = sub.add_parser(
        "determination-plan",
        help=mctx("which Params parameters need determination relations"),
    )
    plan.add_argument("stem", help=STEM_HELP)
    plan.add_argument("--verdicts", action="store_true",
                      help=mctx("append each proposer's verdict on each "
                                "parameter"))

    size = sub.add_parser(
        "size", help=mctx("literal count per solver"),
        description=mctx("Print each solver's literal count, count first."),
    )
    size.add_argument("stem", nargs="?", help=STEM_OR_ALL_HELP)

    features = sub.add_parser(
        "features", help=mctx("per-case features, one TSV row per Choice case"),
        description=mctx("A clause belongs to the cases whose constructors "
                         "appear in its head, and so do the clauses it "
                         "reads, transitively. `rules` counts clauses. "
                         "`atoms`, `rules` and `facts` count "
                         "what one case reaches and no other; `shared_*` "
                         "count what two cases reach, `reach_*` count a "
                         "case's whole reach, and `unreached_atoms` counts "
                         "what no case reaches. A ratio divides a case's "
                         "count by the least count in that column among the "
                         "file's cases. "
                         "With `--run`, `pairs_separating` and "
                         "`pairs_undefined` count over every pair of the "
                         "task, train and test alike, keyed by the grid a "
                         "case emits."),
    )
    features.add_argument("stem", nargs="?", help=STEM_OR_ALL_HELP)
    features.add_argument("--run", action="store_true",
                          help=mctx("run every pair of the task, train and "
                                    "test, and fill the separation columns "
                                    "from what each case emits"))
    features.add_argument("--json", action="store_true", dest="as_json",
                          help=mctx("print JSON in place of TSV, with the "
                                    "pairwise matrix of separating pairs per "
                                    "solver"))

    keywords = sub.add_parser(
        "keywords",
        help=mctx("how many solvers carry each keyword of the Keywords doc"),
        description=mctx("Count, for each keyword of the Keywords doc, the "
                         "solvers whose `// @keywords:` line carries it, and "
                         "list each header keyword the doc does not."),
    )
    keywords.add_argument("stem", nargs="*",
                          help=mctx("solvers to read; all of them when "
                                    "omitted"))

    since = sub.add_parser(
        "since",
        help=mctx("the solvers in scope for a delta survey since a date-time"),
        description=mctx("Print the stem of each solver that the commits "
                         "since the given date-time touch, and of each "
                         "solver whose working-tree content differs from "
                         "HEAD. A commit that touches more than half the "
                         "solvers gives no stems. When the other commits "
                         "together touch more than half, only the solvers "
                         "that those commits create are printed from "
                         "them."),
    )
    since.add_argument("when", help=mctx("a date-time git reads, e.g. "
                                         '"2026-09-08 14:30"'))

    sub.add_parser(
        "expand",
        help=mctx("the source after GRID and RIGID expansion, as Souffle "
                  "sees it"),
        description=mctx("Print the solver source with each GRID call and "
                         "RIGID block replaced by what it emits and nothing else "
                         "changed."),
    ).add_argument("stem", help=STEM_HELP)
    return parser


# What a run's result depends on besides the solver and the task: the
# runner's code and the Souffle sources every solver includes.
RUNNER_SOURCES = ["src/dl/*.py", "programs/lib.dl", "programs/lib/*.dl",
                  "programs/proposers.dl", "programs/lib_functors.cpp"]


def runner_stamp() -> str:
    """A short hash of the runner's sources, the same for two runs with the
    same code."""
    digest = hashlib.sha256()
    for pattern in RUNNER_SOURCES:
        for path in sorted(REPO_ROOT.glob(pattern)):
            digest.update(str(path.relative_to(REPO_ROOT)).encode() + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()[:10]


def main(argv: list[str]) -> int:
    # taken before any command runs, so that it stamps the code this process
    # loaded
    stamp = runner_stamp()
    code = _dispatch(argv)
    sys.stdout.flush()
    # on stderr, so that output a command writes for a program (`--json`,
    # `expand`) stays as it is
    print(f"runner and lib: {stamp}", file=sys.stderr)
    return code


def _dispatch(argv: list[str]) -> int:
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
            return cmd_grid(args.stem, args.file, args.every, args.cases,
                            args.assign)
        case "relation":
            return cmd_relation(args.stem, args.args, args.assign)
        case "record":
            if args.as_format:
                if (args.id or args.file or args.separates or args.assign
                        or args.every):
                    print("`--format` rewrites the file and takes no id, grid, "
                          "`--separates`, `--assign` or `--all`",
                          file=sys.stderr)
                    return 2
                return cmd_format(args.stem, args.witness_file)
            if args.every:
                if args.id or args.file or args.separates or args.assign:
                    print("`--all` runs the file's witnesses again and takes no "
                          "id, grid, `--separates` or `--assign`",
                          file=sys.stderr)
                    return 2
                return cmd_record_all(args.stem, args.witness_file)
            if args.id is None:
                print("record takes a witness id, `--all` or `--format`",
                      file=sys.stderr)
                return 2
            if args.separates is None:
                if args.file or args.assign:
                    print("a new witness takes `--separates`; without it, "
                          "record runs the witness of that id again and "
                          "takes no grid or `--assign`", file=sys.stderr)
                    return 2
                return cmd_rerecord(args.stem, args.id, args.witness_file)
            return cmd_record(args.stem, args.id, args.separates, args.file,
                              args.assign, args.witness_file)
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
            return cmd_audit(args.stem, args.time_limit, args.witness_file)
        case "drop-one":
            return cmd_drop_one(args.stem)
        case "derived-constant":
            return cmd_derived_constant(args.stem)
        case "determination-plan":
            return cmd_determination_plan(args.stem, args.verdicts)
        case "witness":
            return cmd_witness(args.stem, args.file, args.every_case,
                               args.witness_file)
        case "derive" | "store":
            run = cmd_derive if args.cmd == "derive" else cmd_store
            if args.stem is not None:
                return run(args.stem, args.witness_file)
            if args.witness_file is not None:
                print("`--witness-file` takes a stem", file=sys.stderr)
                return 2
            code = 0
            for s in all_stems():
                print(f"{s}:")
                try:
                    code = run(s, corpus=True) or code
                except Exception as e:
                    print(f"{type(e).__name__}: {e}", file=sys.stderr)
                    code = 1
                print()
            return code
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
