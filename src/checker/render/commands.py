"""The frame lines of the commands: what a command prints around the
renderer's sections (a summary table, a section header, a wrote-witness
line, a count line), the pairs of `run`, the rows of `relation`, and the
lines of `record`, `keywords`, `since` and `size`."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from arc.task import Example, pair_name
from checker.finding import LINT_SHAPES, Finding
from checker.render import (
    LineForm,
    Section,
    case_name,
    failure_text,
    finding_lines,
    in_line_order,
    grid_lines,
    joined,
    lint_line,
    pass_line,
    render,
    solver_name,
)
from checker.render.branches import verdict_text
from controlled_markdown import mctx
from engine import AdtValue, Grid, ParseFailure, RecordValue, RunFailure, Value, value_text
from solver.model import Case, Solver
from solver.problems import Fault
from solver.solve import (
    AltKind,
    Candidate,
    CaseOnPair,
    Grids,
    PairRuns,
    alt_kind,
    as_grid,
    out_columns,
)
from solver.vocabulary import CHOICE
from solver.witness import Undefined

# Files and the stamp

NO_WITNESS_FILE = mctx("no witness file at {path}: the Write operation "
                       "copies the Analyze file there")
CORPUS_READ_ONLY = mctx("read-only over every solver: a run on this stem "
                        "alone records the witnesses below")
STAMP = mctx("runner and lib: {stamp}")
UNCAUGHT = mctx("{kind}: {error}")

# `run`

NO_GRID = mctx("no case emitted a grid")
"""The line under a pair or a probe on whose input every case is
undefined."""


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def resolved(solver: Solver) -> bool:
    """Whether `out` has a resolution column (solver-file.md:168)."""
    return out_columns(solver.program)[1] is not None


def pass_suffix(solver: Solver, cases: Sequence[CaseOnPair]) -> str:
    """What a passing pair gave: the count of cases where more than one
    gave grids, and for a solver whose `out` holds resolutions, the count
    of resolutions and of distinct grids where more than one resolution
    stands."""
    given = [c for c in cases if isinstance(c.outcome, Grids)]
    parts: list[str] = []
    if len(given) > 1:
        parts.append(_count(len(given), mctx("case")))
    if resolved(solver):
        n_res = max((len(c.outcome.grids) for c in given
                     if isinstance(c.outcome, Grids)), default=1)
        if n_res > 1:
            parts.append(_count(n_res, mctx("resolution")))
            grids = {g for c in given if isinstance(c.outcome, Grids)
                     for g in c.outcome.grids}
            parts.append(_count(len(grids), mctx("grid")))
    return f" ({', '.join(parts)})" if parts else ""


def passed(cases: Sequence[CaseOnPair]) -> bool:
    """Every case of the solver gives grids on the pair that are one of its
    candidates."""
    return bool(cases) and all(c.matches for c in cases)


ALT_NAME = {
    AltKind.RULE: mctx("the rule alt"),
    AltKind.TIEBREAK: mctx("the tiebreak alt"),
}
"""A pair's alt by name, in a reason."""


def _stored_name(candidate: Candidate, ex: Example) -> str:
    if candidate is Candidate.OUTPUT or ex.alt is None:
        return mctx("the stored output")
    return ALT_NAME[alt_kind(ex.alt)]


def _stored(ex: Example) -> list[list[tuple[str, Grid]]]:
    """The pair's candidates, each as the grids the task file stores for
    it, by the name each takes in a reason."""
    output = (mctx("the stored output"), as_grid(ex.output))
    if ex.alt is None:
        return [[output]]
    kind = alt_kind(ex.alt)
    alt = (ALT_NAME[kind], as_grid(ex.alt.grid))
    if kind is AltKind.TIEBREAK:
        return [[output, alt]]
    return [[output], [alt]]


def _reasons(grids: Sequence[Grid], ex: Example) -> tuple[str, ...]:
    """Why `grids`, one case's grids on the pair, are none of the pair's
    candidates, one reason per candidate."""
    given = set(grids)
    reasons: list[str] = []
    for stored in _stored(ex):
        miss = next((mctx("{stored} is not among the case's grids").format(
            stored=name) for name, g in stored if g not in given), None)
        if miss is None and given - {g for _n, g in stored}:
            miss = mctx("a grid of the case is not in the candidate of "
                        "{first}").format(first=stored[0][0])
        if miss is None:
            return ()
        reasons.append(miss)
    return tuple(reasons)


def _diff(expected: Grid, actual: Grid) -> list[str]:
    """Expected then actual, with the count of cells that differ."""
    lines = [mctx("expected:"), *grid_lines(expected), mctx("actual:"),
             *grid_lines(actual)]
    eh, ew = len(expected), len(expected[0]) if expected else 0
    ah, aw = len(actual), len(actual[0]) if actual else 0
    if (eh, ew) == (ah, aw) and eh > 0:
        n = sum(1 for r in range(eh) for c in range(ew)
                if expected[r][c] != actual[r][c])
        if n:
            lines.append(mctx("{n}/{total} cells differ").format(
                n=n, total=eh * ew))
    elif (eh, ew) != (ah, aw):
        lines.append(mctx("shape mismatch: {eh}x{ew} vs {ah}x{aw}").format(
            eh=eh, ew=ew, ah=ah, aw=aw))
    return lines


def _one_failure(cases: Sequence[CaseOnPair]) -> RunFailure | None:
    """The failure every case's run on the pair gives, where they give
    one and the same."""
    failures = {c.outcome for c in cases}
    if len(failures) == 1:
        (only,) = failures
        if not isinstance(only, Grids | Undefined):
            return only
    return None


def pair_failure_lines(solver: Solver, name: str,
                       cases: Sequence[CaseOnPair], ex: Example) -> list[str]:
    """A failing pair: what its run hit, or each case whose grids are
    none of the pair's candidates with why, then each grid the pair does
    not accept, against the stored output."""
    lines = [mctx("{pair}: FAIL").format(pair=name)]
    whole = _one_failure(cases)
    if whole is not None:
        return [*lines, f"  {failure_text(whole)}"]
    if not any(isinstance(c.outcome, Grids) for c in cases):
        return [*lines, f"  {NO_GRID}"]
    accepted = {g for stored in _stored(ex) for _n, g in stored}
    bad: list[CaseOnPair] = []
    groups: dict[tuple[str, ...], list[str]] = {}
    for c in cases:
        o = c.outcome
        if isinstance(o, Grids) and any(g not in accepted for g in o.grids):
            bad.append(c)
            continue
        if not isinstance(o, Grids | Undefined):
            groups.setdefault((failure_text(o),), []).append(
                case_name(solver, c.case))
            continue
        grids = o.grids if isinstance(o, Grids) else ()
        if reasons := _reasons(grids, ex):
            groups.setdefault(reasons, []).append(case_name(solver, c.case))
    lines += [f"  {', '.join(cases)}: {'; '.join(reasons)}"
              for reasons, cases in groups.items()]
    if not bad:
        return lines
    many = len(cases) > 1 or resolved(solver)
    if many:
        passing = len(cases) - len(bad)
        lines.append("  " + mctx("cases: {p} pass / {f} fail").format(
            p=passing, f=len(bad)))
        lines.append("    " + mctx("fail: {cases}").format(
            cases=", ".join(case_name(solver, c.case) for c in bad)))
    by_grid: dict[Grid, list[str]] = {}
    for c in bad:
        assert isinstance(c.outcome, Grids)
        for g in c.outcome.grids:
            if g not in accepted:
                by_grid.setdefault(g, []).append(case_name(solver, c.case))
    expected = as_grid(ex.output)
    for grid, names in by_grid.items():
        lines.append("")
        if many:
            lines.append(f"  {', '.join(dict.fromkeys(names))}:")
        lines += [f"    {ln}" for ln in _diff(expected, grid)]
    return lines


def pair_lines(solver: Solver, name: str, cases: Sequence[CaseOnPair],
               ex: Example) -> list[str]:
    """One pair of `run`: its pass line, or its failure."""
    if passed(cases):
        return [mctx("{pair}: PASS{suffix}").format(
            pair=name, suffix=pass_suffix(solver, cases))]
    return pair_failure_lines(solver, name, cases, ex)


def name_of(pair: PairRuns) -> str:
    return pair_name(pair.pair.section, pair.pair.index)


def enumeration_failed_lines(names: Sequence[str], failure: RunFailure
                             ) -> list[str]:
    """Pairs that fail on the failure of the run that enumerates the
    cases."""
    return [ln for n in names
            for ln in (mctx("{pair}: FAIL").format(pair=n),
                       f"  {failure_text(failure)}")]


def shared_failure_lines(names: Sequence[str], failure: RunFailure
                         ) -> list[str]:
    """Pairs that all fail on one failure, in one line."""
    return [mctx("{pairs}: FAIL").format(pairs=", ".join(names)),
            f"  {failure_text(failure)}"]


def stem_failure_lines(solver: Solver,
                       failing: Sequence[tuple[str, Sequence[CaseOnPair],
                                               Example]]) -> list[str]:
    """The failing pairs of one solver, as a report over several solvers
    gives them: once where more than one fails on one and the same
    failure."""
    shared = {_one_failure(cases) for _n, cases, _ex in failing}
    if len(failing) > 1 and len(shared) == 1:
        (only,) = shared
        if only is not None:
            return shared_failure_lines([n for n, _c, _e in failing], only)
    return [ln for n, cases, ex in failing
            for ln in pair_failure_lines(solver, n, cases, ex)]


def probe_lines(solver: Solver, name: str,
                given: Sequence[tuple[Case, object]]) -> list[str]:
    """A pair with no output: each case's grids under its name, or the
    line that says no case emitted one."""
    lines: list[str] = []
    shown = False
    for case, o in given:
        if isinstance(o, Undefined):
            continue
        shown = True
        label = case_name(solver, case)
        if not isinstance(o, Grids):
            assert not isinstance(o, Grids)
            lines.append(f"{name} {label}:")
            lines.append(f"  {failure_text(o)}")  # type: ignore[arg-type]
            continue
        for i, g in enumerate(o.grids):
            suffix = f" {i + 1}" if len(o.grids) > 1 else ""
            lines.append(f"{name} {label}{suffix}:")
            lines += [f"  {ln}" for ln in grid_lines(g)]
    if not shown:
        lines += [f"{name}:", f"  {NO_GRID}"]
    return lines


COMPILE_CAUSE = mctx("likely cause:")
TIME_LINE = mctx("time: {parts}")
TIME_PAIRS = mctx("pairs {secs:.1f}s")
TIME_DETERMINATION = mctx("determination {secs:.1f}s")


# A run over several solvers

def verdict_line(stem: str, passes: int, total: int, fails: bool) -> str:
    """One solver's line in a run over several: its pair count, and
    whether it passes."""
    return f"{stem}: {passes}/{total} {'FAIL' if fails else 'PASS'}"


def section_header(header: str) -> list[str]:
    return ["", f"--- {header} ---"]


FAILING_PAIRS = mctx("{n} solver(s) with a failing pair")
LINT_FINDINGS = mctx("findings: {count} across {solvers} solver(s)")
LINT_HINTS = mctx("hints: {count} across {solvers} solver(s)")
DETERMINATION_CHECKS = mctx("determination checks: {ok}/{n} ok")
TIMES = mctx("times: slowest 15 (wall seconds)")
SUMMARY = mctx("summary: {passing}/{total} solvers")


def time_row(total: float, stem: str, pairs: float,
             determination: float | None) -> str:
    part = "" if determination is None \
        else f", determination {determination:.1f}"
    return f"  {total:5.1f}  {stem}  (pairs {pairs:.1f}{part})"


# `grid`, `relation` and `record`

NO_ROWS = mctx("{head}: no rows")
JUDGED_OUTPUT = mctx("judged output:")
WOULD_RECORD = mctx("would record witness `{id}`")
WROTE = mctx("wrote witness `{id}` to {path}")
FORMATTED = mctx("formatted {path}")
RERECORDED_ONE = mctx("re-recorded witness `{id}` in {path}: {change}")


def _witnesses(n: int) -> str:
    return mctx("{n} witness").format(n=n) if n == 1 \
        else mctx("{n} witnesses").format(n=n)


def rerecorded_all(n: int, path: object, changed: int) -> str:
    """The line of `record --all` that wrote the file: how many witnesses
    ran, and how many of them changed groups."""
    return mctx("re-recorded {witnesses} in {path}: {changed} with changed "
                "groups").format(witnesses=_witnesses(n), path=path,
                                 changed=changed)


def unchanged_file(n: int, path: object) -> str:
    """The line of `record --all` that wrote nothing, since the file
    already holds the text the writer writes."""
    return mctx("re-ran {witnesses}: {path} holds them as the writer "
                "writes them, so nothing was written").format(
                    witnesses=_witnesses(n), path=path)


WROTE_NOTHING = mctx("wrote nothing to {path}: {failed} of {n} witnesses "
                     "could not be run")
RUN_FAILED = mctx("run failed: {error}")
WITNESS_HINT = mctx("when it is a branch's witness or a witness of the "
                    "concept case, add: // @witness {id}: <plausibility> "
                    "<verdict>")
COUNT_LINE = mctx("{bases} bases, {cases} cases, {g} distinct grid(s)")
"""The count line of a built witness: its cases' bases, its cases, and
the distinct grids they give (solver-file.md:99)."""
GROUPS_KEPT = mctx("groups unchanged")
JUDGED_KEPT = mctx("judged output kept")
GROUPS_CHANGED = mctx("groups changed: {newly} {cases} newly listed, {gone} "
                      "no longer listed")
NAMES_REWRITTEN = mctx("names rewritten to the listed form")


@dataclass(frozen=True)
class JudgedKept:
    """A judged output, which a run leaves as it is."""


@dataclass(frozen=True)
class GroupsKept:
    """The groups a run gives list the cases the file's groups list, each
    by the name the file gives it, with the same grids."""


@dataclass(frozen=True)
class NamesRewritten:
    """The file's groups list, by other names, the cases the run's groups
    list, with the same grids: the names of each file group denote
    together (`solver.names.denoted_cases`) the cases of the run's group
    (solver-file.md:185, :193-199), and the run's names replace them."""


@dataclass(frozen=True)
class GroupsChanged:
    """The groups a run gives differ from the file's in which cases a group
    lists or in a group's grid: `newly` cases of the solver the file lists
    in no group, and `gone` names of the file that denote no case of the
    solver."""

    newly: int
    gone: int


type RecordChange = JudgedKept | GroupsKept | NamesRewritten | GroupsChanged
"""What running a witness of the file again changes in its entry."""


def rerecord_text(change: RecordChange) -> str:
    """What running a witness again changed in its entry, as `record`
    prints it."""
    match change:
        case JudgedKept():
            return JUDGED_KEPT
        case GroupsKept():
            return GROUPS_KEPT
        case NamesRewritten():
            return NAMES_REWRITTEN
        case GroupsChanged(newly=newly, gone=gone):
            return GROUPS_CHANGED.format(
                newly=newly, gone=gone,
                cases="case" if newly == 1 else "cases")


def input_lines(grid: Grid) -> list[str]:
    return [mctx("input:"), *(f"  {r}" for r in grid_lines(grid))]


def judged_lines(grid: Grid) -> list[str]:
    return ["", JUDGED_OUTPUT, *(f"  {r}" for r in grid_lines(grid))]


def relation_lines(name: str, columns: Sequence[str],
                   rows: Sequence[Sequence[str]]) -> list[str]:
    """One relation's rows as Souffle prints them, under its columns."""
    head = f"{name}({', '.join(columns)})"
    if not rows:
        return [NO_ROWS.format(head=head)]
    return [f"{head}:", *("  " + "\t".join(r) for r in rows)]


# `witness`, `derive`, `store` and `audit`

WITNESS_LINES = mctx("`@witness` lines:")
NO_WITNESS_LINES = mctx("no witness lines")
GRIDS_RUN = mctx("{n} witness {grids} run")
WITNESS_FILE_OK = mctx("witness file: ok")
AUDIT_SECTION = mctx("--- {name} ---")
def grids_run(n: int) -> str:
    return GRIDS_RUN.format(n=n, grids="grid" if n == 1 else "grids")


# `keywords`, `since` and `size`

KEYWORDS_SECTION = mctx("--- {name} ---")
KEYWORD_ROW = "  {n:4d}  {word}"
UNKNOWN_KEYWORD = mctx("{stem}: {word} is not in keywords.md")
UNKNOWN_KEYWORDS = mctx("unknown keywords: {n}")
SKIPPED_REWRITE = mctx("skipped {sha}: a mechanical rewrite, touching {n} "
                       "solvers of {total}, more than the {share:.0%} share")
WINDOW_REWRITE = mctx("the window holds a corpus-wide rewrite: its commits "
                      "touch {n} solvers of {total}, more than the "
                      "{share:.0%} share. The scope is the {kept} solvers "
                      "added since then.")
IN_SCOPE = mctx("{n} solvers in scope.")
SIZE_ROW = "{count}\t{stem}"
SIZE_UNREAD = mctx("{stem}: {error}")


# Composed frames


def failed_line(solver: Solver, failure: RunFailure) -> str:
    """The line a compile failure prints once, before anything runs."""
    return f"{solver_name(solver)}: {failure_text(failure)}"


def compile_lines(solver: Solver, failure: RunFailure,
                  collisions: Sequence[Finding]) -> list[str]:
    """A solver whose program the engine rejects: the error, then the
    lint findings that likely cause it."""
    lines = [failed_line(solver, failure)]
    if collisions:
        lines.append(COMPILE_CAUSE)
        lines += [f"  {lint_line(solver, f)}" for f in collisions]
    return lines


def lint_section(solver: Solver, findings: Sequence[Finding]) -> list[str]:
    """The lint section of `run`, closed by a blank line and its pass line
    where the findings pass, and by a blank line otherwise."""
    lines = render(solver, Section.LINT, findings)
    return lines if pass_line(Section.LINT, findings) is not None \
        else [*lines, ""]


def time_line(pairs: float, determination: float | None) -> list[str]:
    """The time `run --time` gives one solver, after a blank line."""
    parts = [TIME_PAIRS.format(secs=pairs)]
    if determination is not None:
        parts.append(TIME_DETERMINATION.format(secs=determination))
    return ["", TIME_LINE.format(parts=", ".join(parts))]


def lint_entry_lines(solver: Solver, f: Finding) -> list[str]:
    """A lint finding in the report over several solvers: the lint line,
    or a fault's lines with the file's name."""
    if isinstance(f.payload, LINT_SHAPES):
        return [lint_line(solver, f)]
    return finding_lines(solver, f, LineForm.FILE)


def gathered_lint(shown: Sequence[tuple[Solver, Sequence[Finding]]]
                  ) -> list[str]:
    """The lint findings of several solvers under one header, each
    solver's lines indented, each solver's in line order."""
    return [f"  {ln}" for s, fs in shown for f in in_line_order(fs)
            for ln in lint_entry_lines(s, f)]


def failure_block(stem: str, lines: Sequence[str]) -> list[str]:
    """A solver's failing pairs in the report over several solvers."""
    return ["", f"{stem}:", *(f"  {ln}" for ln in lines)]


def determination_block(stem: str, lines: Sequence[str]) -> list[str]:
    """A solver's determination lines in the report over several
    solvers."""
    return [f"  {stem}.dl: {ln}" for ln in lines]


def annotation_lines(solver: Solver) -> list[str]:
    """What each `@witness` line states, one block per line."""
    lines: list[str] = []
    for w in solver.annotations.witnesses:
        lines.append(f"{w.id}: {w.plausibility.value} "
                     f"{verdict_text(w.verdict)}")
        lines += [f"  relaxed: {s}" for s in w.relaxed]
        lines += [f"  reassigned: {p}" for p in w.reassigned]
        if w.approximates:
            lines.append(f"  under @approximated: of {w.approximates}")
    return lines or [NO_WITNESS_LINES]


def witness_head(solver: Solver, grids: int | None, path: Path) -> list[str]:
    """The head of the witness report: the `@witness` lines, then the
    count of witness grids, or the missing file's line."""
    return [WITNESS_LINES, *(f"  {ln}" for ln in annotation_lines(solver)),
            "", NO_WITNESS_FILE.format(path=path) if grids is None
            else grids_run(grids)]


def indented(solver: Solver, section: Section,
             findings: Sequence[Finding]) -> list[str]:
    """A section as the `witness`, `derive` and `store` reports print it:
    each finding's lines indented, and the pass line as it stands."""
    lines = render(solver, section, findings)
    ok = pass_line(section, findings)
    body = lines[:-1] if ok is not None else lines
    return [f"  {ln}" for ln in body] + ([ok] if ok is not None else [])


def shape_problem_line(path: Path, problem: Fault) -> str:
    """A witness file's shape problem, checked with no solver."""
    return f"{path}: {problem.kind.value}: {problem.detail}"


def stem_head(stem: str) -> str:
    """The head of one solver's block in `derive` or `store` over every
    solver."""
    return f"{stem}:"


def entry_line(entry_id: str, what: object) -> str:
    """A witness entry's id and what running it again gave."""
    return f"{entry_id}: {what}"


def size_unread(stem: str, failure: ParseFailure) -> str:
    return SIZE_UNREAD.format(stem=stem, error=(
        f"{failure.line}:{failure.column}: {failure.message}"))


def _branch_names(value: Value) -> list[str]:
    """The constructors of a value, outermost first; a field that is no
    constructor and no record holds data, and no branch."""
    match value:
        case AdtValue(constructor=c, args=args):
            return [c, *(b for a in args for b in _branch_names(a))]
        case RecordValue(fields=fields):
            return [b for f in fields for b in _branch_names(f)]
        case _:
            return []


def souffle_text(solver: Solver, value: Value, type_name: str) -> str:
    """A column's value of `relation` as Souffle prints it; a `Choice`
    value by its case's name, and a value of an ADT at a choice point by
    the branches of its constructors, each by its name, joined by
    ` & `."""
    if type_name == CHOICE and isinstance(value, AdtValue | RecordValue):
        return case_name(solver, Case(value, ()))
    points = set() if solver.choice is None \
        else {p.type for p in solver.choice.points}
    if type_name in points and isinstance(value, AdtValue):
        return joined(_branch_names(value))
    return value_text(value)
