"""The frame lines of the commands: what a command prints around the
renderer's sections (a summary table, a section header, a wrote-witness
line, a count line), the constructors no case takes after `grid`'s
output, the pairs of `run`, the rows of `relation`, and the
lines of `record`, `keywords`, `since` and `size`."""

from collections.abc import Sequence
from pathlib import Path

from arc.task import Example
from checker.finding import Finding
from checker.judged import value_constructors
from checker.sweep import GivingValues
from checker.render import (
    GridRow,
    LineForm,
    Section,
    _ticked,
    cases_text,
    counted,
    derive_line_to_add,
    detail_text,
    failure_text,
    file_name,
    finding_lines,
    grid_lines,
    header_line,
    in_line_order,
    joined,
    lint_line,
    noun,
    pass_line,
    render,
    shifted,
    solver_name,
)
from checker.render.surveys import giving_text
from solver.names import ctor_text
from solver.names import name as case_name
from controlled_markdown import mctx
from engine import AdtValue, Grid, ParseFailure, RecordValue, RunFailure, Value
from engine.program import RelationDecl
from engine.text import text as code_text
from solver.annotations import verdict_text
from solver.model import Case, Solver, takes_constructor
from solver.problems import Fault
from solver.solve import (
    AltKind,
    Candidate,
    CaseOnPair,
    Grids,
    Outcome,
    alt_kind,
    as_grid,
    is_result,
    out_columns,
)
from solver.vocabulary import CHOICE
from solver.witness import (
    GridChanged,
    GroupsKept,
    JudgedKept,
    NamesRewritten,
    PartitionChanged,
    RecordChange,
    Undefined,
    output_key,
)

# Files and the stamp

NO_WITNESS_FILE = mctx("no witness file at {path}: the first witness that "
                       "`record`, `derive` or `store` writes creates it")
CORPUS_READ_ONLY = mctx("read-only over every solver: a run on this stem "
                        "alone records the witnesses below")
STAMP = mctx("runner and lib: {stamp}")
UNCAUGHT = mctx("{kind}: {error}")

# `run`

NO_GRID = mctx("no case emitted a grid")
"""The line under a pair or a probe on whose input every case is
undefined."""


def resolved(solver: Solver) -> bool:
    """Whether `out` has a resolution column (solver-file.md, under
    "Alt outputs")."""
    return out_columns(solver.program)[1] is not None


def pass_suffix(solver: Solver, cases: Sequence[CaseOnPair]) -> str:
    """What a passing pair gave: the count of cases where more than one
    gave grids, and for a solver whose `out` holds resolutions, the count
    of resolutions and of distinct grids where more than one resolution
    stands."""
    given = [c for c in cases if isinstance(c.outcome, Grids)]
    parts: list[str] = []
    if len(given) > 1:
        parts.append(counted(len(given), mctx("witnessed case")))
    if resolved(solver):
        n_res = max((len(c.outcome.grids) for c in given
                     if isinstance(c.outcome, Grids)), default=1)
        if n_res > 1:
            parts.append(counted(n_res, mctx("resolution")))
            grids = {g for c in given if isinstance(c.outcome, Grids)
                     for g in c.outcome.grids}
            parts.append(counted(len(grids), mctx("grid")))
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
        if not is_result(only):
            return only
    return None


def pair_failure_lines(solver: Solver, name: str,
                       cases: Sequence[CaseOnPair], ex: Example,
                       shown: set[Case] | None = None,
                       giving: Sequence[GivingValues] = ()) -> list[str]:
    """A failing pair: what its run hit, or each case whose grids are
    none of the pair's candidates with why, the count of the cases that
    fit, fail and give no output, then each grid the pair does not
    accept, against the stored output; then, for each distinct output of
    the cases the reasons name, its grids against the stored output, or
    the cells at which it is undefined, under the fewest names of the
    cases that give it (`solver.names.cover`). With `shown`, the cases whose output an
    earlier pair drew, an output is drawn on the first pair where its
    cases fail alone, and the cases drawn here join it. Under the line of
    each case, each of `giving` at that case (`giving_text`): `giving` holds
    those whose first train pair with no output is this one."""
    lines = [mctx("{pair}: FAIL").format(pair=name)]
    whole = _one_failure(cases)
    if whole is not None:
        return _failed_on(name, whole)

    def guided(members: Sequence[Case]) -> list[str]:
        return [f"    {giving_text(solver, g)}" for g in giving
                if g.case in members]

    if not any(isinstance(c.outcome, Grids) for c in cases):
        return [*lines, f"  {NO_GRID}", *guided([c.case for c in cases])]
    accepted = {g for stored in _stored(ex) for _n, g in stored}
    every = [c.case for c in cases]
    bad: list[CaseOnPair] = []
    groups: dict[tuple[str, ...], list[Case]] = {}
    for c in cases:
        o = c.outcome
        if isinstance(o, Grids) and any(g not in accepted for g in o.grids):
            bad.append(c)
            continue
        if not is_result(o):
            groups.setdefault((failure_text(o),), []).append(c.case)
            continue
        grids = o.grids if isinstance(o, Grids) else ()
        if reasons := _reasons(grids, ex):
            groups.setdefault(reasons, []).append(c.case)
    for reasons, members in groups.items():
        lines.append(
            f"  {cases_text(solver, members, every)}: {'; '.join(reasons)}")
        lines += guided(members)
    drawn = _drawn_outputs(solver, cases, ex, shown)
    empty = sum(not isinstance(c.outcome, Grids) for c in cases)
    many = len(cases) > 1 or resolved(solver)
    if many and (bad or empty):
        fit = sum(bool(c.matches) for c in cases)
        count = mctx("cases: {p} pass / {f} fail / {n} no output") if empty \
            else mctx("cases: {p} pass / {f} fail")
        lines.append("  " + count.format(p=fit, f=len(bad), n=empty))
    if not bad:
        return lines + drawn
    if many:
        lines.append("    " + mctx("fail: {cases}").format(
            cases=cases_text(solver, [c.case for c in bad], every)))
    by_grid: dict[Grid, list[Case]] = {}
    for c in bad:
        assert isinstance(c.outcome, Grids)
        for g in c.outcome.grids:
            if g not in accepted:
                by_grid.setdefault(g, []).append(c.case)
    expected = as_grid(ex.output)
    for grid, members in by_grid.items():
        lines.append("")
        if many:
            lines.append(f"  {cases_text(solver, members, every)}:")
        lines += [f"    {ln}" for ln in _diff(expected, grid)]
    return lines + drawn


def _drawn_outputs(solver: Solver, cases: Sequence[CaseOnPair],
                   ex: Example, shown: set[Case] | None) -> list[str]:
    """For each distinct output of the cases whose grids, all accepted
    or none, are no candidate of the pair (`_reasons`), its grids against
    the stored output, or why it is undefined (`undefined_lines`), under
    the fewest names of the cases that give it (`pair_failure_lines`)."""
    from checker.render.branches import undefined_lines

    by: dict[object, tuple[Grids | Undefined, list[Case]]] = {}
    for c in cases:
        o = c.outcome
        if not is_result(o) \
                or (shown is not None and c.case in shown):
            continue
        if isinstance(o, Grids) and any(
                g not in {g for stored in _stored(ex) for _n, g in stored}
                for g in o.grids):
            continue
        grids = o.grids if isinstance(o, Grids) else ()
        if not _reasons(grids, ex):
            continue
        by.setdefault(output_key(o), (o, []))[1].append(c.case)
    expected = as_grid(ex.output)
    every = [c.case for c in cases]
    lines: list[str] = []
    for out, members in by.values():
        if isinstance(out, Grids):
            body = [f"    {ln}" for grid in sorted(set(out.grids))
                    for ln in _diff(expected, grid)]
        else:
            body = [f"    {ln}" for ln in undefined_lines(out.reason)]
        if not body:
            continue
        lines += ["", f"  {cases_text(solver, members, every)}:", *body]
        if shown is not None:
            shown.update(members)
    return lines


def pair_lines(solver: Solver, name: str, cases: Sequence[CaseOnPair],
               ex: Example, shown: set[Case] | None = None,
               giving: Sequence[GivingValues] = ()) -> list[str]:
    """One pair of `run`: its pass line, or its failure
    (`pair_failure_lines`, `shown` the cases an earlier pair drew)."""
    if passed(cases):
        return [mctx("{pair}: PASS{suffix}").format(
            pair=name, suffix=pass_suffix(solver, cases))]
    return pair_failure_lines(solver, name, cases, ex, shown, giving)


def enumeration_failed_lines(names: Sequence[str], failure: RunFailure
                             ) -> list[str]:
    """Pairs that fail on the failure of the run that enumerates the
    cases."""
    return [ln for n in names for ln in _failed_on(n, failure)]


def shared_failure_lines(names: Sequence[str], failure: RunFailure
                         ) -> list[str]:
    """Pairs that all fail on one failure, in one line."""
    return _failed_on(", ".join(names), failure)


def _failed_on(pairs: str, failure: RunFailure) -> list[str]:
    """The pairs `pairs` names failing on one run failure."""
    return [mctx("{pairs}: FAIL").format(pairs=pairs),
            f"  {failure_text(failure)}"]


def stem_failure_lines(solver: Solver,
                       failing: Sequence[tuple[str, Sequence[CaseOnPair],
                                               Example,
                                               Sequence[GivingValues]]]
                       ) -> list[str]:
    """The failing pairs of one solver, as a report over several solvers
    gives them: once where more than one fails on one and the same
    failure."""
    shared = {_one_failure(cases) for _n, cases, _ex, _g in failing}
    if len(failing) > 1 and len(shared) == 1:
        (only,) = shared
        if only is not None:
            return shared_failure_lines([n for n, _c, _e, _g in failing],
                                        only)
    shown: set[Case] = set()
    return [ln for n, cases, ex, giving in failing
            for ln in pair_failure_lines(solver, n, cases, ex, shown,
                                         giving)]


def probe_lines(solver: Solver, name: str,
                given: Sequence[tuple[Case, Outcome]]) -> list[str]:
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
            lines.append(f"{name} {label}:")
            lines.append(f"  {failure_text(o)}")
            continue
        for i, g in enumerate(o.grids):
            suffix = f" {i + 1}" if len(o.grids) > 1 else ""
            lines.append(f"{name} {label}{suffix}:")
            lines += [shifted(ln, "  ") for ln in grid_lines(g)]
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
    return ["", header_line(header)]


FAILING_PAIRS = mctx("{n} solver(s) with a failing pair")
LINT_FINDINGS = mctx("findings: {count} across {solvers} solver(s)")
LINT_HINTS = mctx("hints: {count} across {solvers} solver(s)")
DETERMINATION_CHECKS = mctx("determination checks: {ok}/{n} ok")
SLOWEST = 15
"""How many solvers the `times` section of a run over several lists."""
TIMES = mctx("times: slowest {n} (wall seconds)").format(n=SLOWEST)
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
def judgment_first(lines: Sequence[str]) -> list[str]:
    """A section's lines with the blocks that draw no grid first, in
    their order, then those that draw one, in theirs, so that the first
    screen holds the section's findings, count and pass lines. A block is
    a line and the lines below it that are indented further, the blank
    lines between them included; it draws a grid where it holds a
    `GridRow`."""
    blocks: list[list[str]] = []
    head = -1
    pending: list[str] = []
    for line in lines:
        if not line.strip():
            pending.append(line)
            continue
        indent = len(line) - len(line.lstrip(" "))
        if blocks and indent > head:
            blocks[-1] += [*pending, line]
        else:
            blocks.append([*pending, line])
            head = indent
        pending = []
    if pending:
        if blocks:
            blocks[-1] += pending
        else:
            blocks.append(pending)

    def draws(block: list[str]) -> bool:
        return any(isinstance(line, GridRow) for line in block)

    return [line for b in (*(b for b in blocks if not draws(b)),
                           *(b for b in blocks if draws(b)))
            for line in b]


WROTE = mctx("wrote witness `{id}` to {path}")
REMOVED = mctx("removed witness `{id}` from {path}")
RESEPARATED = mctx("rewrote the `separates` text of witness `{id}` in {path}")


def not_written(id: str, names: Sequence[str], kind: Section, lineless: bool
                ) -> str:
    """The line of a witness a survey built and did not write, since its
    groups hold `names`, which denote no case of the solver; `lineless`
    where the survey built it with a `@derive` or `@store` line (`kind`)
    the solver does not hold."""
    if lineless:
        return mctx("wrote no witness `{id}`: the solver has no `@{kind}` "
                    "line for `{id}`; once the line is written, `{kind}` "
                    "writes the witness").format(id=id, kind=kind.value)
    return mctx("wrote no witness `{id}`: its groups name {names}, which "
                "denote no case of the solver").format(
        id=id, names=_ticked(names))


def wrote_lineless(id: str, path: object, proposer: str,
                   decl: RelationDecl) -> str:
    """The line of a witness the `derive` survey wrote for a derivation
    with no `@derive` line: its groups name the branch, which the solver
    denotes once the line stands above the parameter's declaration."""
    return mctx("wrote witness `{id}` to {path}; its groups name `{id}`, so "
                "add `{line}` above `{decl}`, its verdict read from this "
                "witness").format(
        id=id, path=path, decl=code_text(decl),
        line=derive_line_to_add(proposer))


FORMATTED = mctx("formatted {path}")
RERECORDED_ONE = mctx("re-recorded witness `{id}` in {path}: {change}")


def _witnesses(n: int) -> str:
    return counted(n, mctx("witness"), mctx("witnesses"))


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
COUNT_LINE = mctx("{n} witnessed cases of {m}, {g} distinct grid(s)")
"""The count line of a built witness: the witnessed cases its groups were
built from, the solver's cases, and the distinct grids they give
(solver-file.md, under "Cases"). `grid` prints the same line
(`record_lines`)."""


def untaken_constructor_lines(solver: Solver, cases: Sequence[Case]
                              ) -> list[str]:
    """A line for each constructor of the solver's `Choice`, at any
    depth, that no case of `cases` takes, in point order."""
    choice = solver.choice
    if choice is None:
        return []
    return [mctx("no case takes {ctor}").format(ctor=ctor_text(c.name))
            for p in choice.points for c in p.constructors
            if not any(takes_constructor(choice, k.base, c) for k in cases)]


GROUPS_KEPT = mctx("groups unchanged")
JUDGED_KEPT = mctx("judged output kept")
GROUPS_CHANGED = mctx("groups changed: {newly} {cases} newly listed, {gone} "
                      "no longer listed")
GRID_CHANGED = mctx("grid changed in {groups}: {names}")
NAMES_REWRITTEN = mctx("names rewritten to the listed form")


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
        case PartitionChanged(newly=newly, gone=gone):
            return GROUPS_CHANGED.format(
                newly=newly, gone=gone,
                cases=noun(newly, "case"))
        case GridChanged(groups=groups):
            return GRID_CHANGED.format(
                groups=counted(len(groups), mctx("group")),
                names="; ".join(_ticked(g) for g in groups))


def judged_lines(grid: Grid) -> list[str]:
    return ["", JUDGED_OUTPUT, *(shifted(r, "  ") for r in grid_lines(grid))]


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
AUDIT_SECTION = mctx("{name} ({seconds:.0f}s)")


def audit_section(name: Section, seconds: float) -> str:
    """An audit section's header line, with the seconds the section
    took."""
    return header_line(AUDIT_SECTION.format(name=name.value,
                                            seconds=seconds))

def grids_run(n: int) -> str:
    return GRIDS_RUN.format(n=n, grids=noun(n, "grid"))


# `keywords`, `since` and `size`


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


def gathered_lint(shown: Sequence[tuple[Solver, Sequence[Finding]]]
                  ) -> list[str]:
    """The lint findings of several solvers under one header, each
    solver's lines indented, each solver's in line order."""
    return [f"  {ln}" for s, fs in shown for f in in_line_order(fs)
            for ln in finding_lines(s, f, LineForm.FILE)]


def failure_block(stem: str, lines: Sequence[str]) -> list[str]:
    """A solver's failing pairs in the report over several solvers."""
    return ["", f"{stem}:", *(f"  {ln}" for ln in lines)]


def determination_block(stem: str, lines: Sequence[str]) -> list[str]:
    """A solver's determination lines in the report over several
    solvers."""
    return [f"  {file_name(stem)}: {ln}" for ln in lines]


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
    return [shifted(ln, "  ") for ln in body] + ([ok] if ok is not None
                                                 else [])


def shape_problem_line(path: Path, problem: Fault) -> str:
    """A witness file's shape problem, checked with no solver."""
    return f"{path}: {problem.kind.value}: {detail_text(problem.detail)}"


def stem_head(stem: str) -> str:
    """The head of one solver's block in `derive` or `store` over every
    solver."""
    return f"{stem}:"


def entry_line(entry_id: str, what: object) -> str:
    """A witness entry's id and what running it again gave."""
    return f"{entry_id}: {what}"


def size_unread(stem: str, failure: ParseFailure) -> str:
    return SIZE_UNREAD.format(stem=stem, error=detail_text(failure))


def souffle_text(solver: Solver, value: Value, type_name: str) -> str:
    """A column's value of `relation` as Souffle prints it; a `Choice`
    value by its case's name, and a value of an ADT at a choice point by
    the branches of its constructors, each by its name, joined by
    ` & `."""
    if type_name == CHOICE and isinstance(value, AdtValue | RecordValue):
        return case_name(solver, value)
    points = set() if solver.choice is None \
        else {p.type for p in solver.choice.points}
    if type_name in points and isinstance(value, AdtValue):
        return joined(value_constructors(value))
    return code_text(value)
