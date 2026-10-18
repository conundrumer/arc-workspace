"""The pairs of `run`: a pair's pass line, or its failure with the grids
it does not accept, and a pair with no output."""

from collections.abc import Sequence

from arc.task import Example
from checker.render import counted
from checker.render.cases import cases_text
from checker.render.grids import grid_lines, shifted
from checker.render.no_result import failure_text
from checker.render.surveys import giving_text
from checker.sweep import GivingValues
from controlled_markdown import mctx
from engine import Grid, RunFailure
from engine.program import grid_size
from solver.aggregate import Solver
from solver.model import Case
from solver.names import name as case_name
from solver.outcome import Grids, Outcome, is_result
from engine.program import as_grid
from solver.pair_runs import AltKind, CaseOnPair, alt_kind
from solver.out_grids import out_columns
from solver.undefined import Undefined
from solver.witness_groups import output_key

NO_GRID = mctx("no case emitted a grid")
"""The line under a pair or a probe on whose input every case is
undefined."""


def resolved(solver: Solver) -> bool:
    """Whether `out` has a resolution column
    (docs/handbook/solver-file.md#cases)."""
    return bool(out_columns(solver.program).resolution)


def pass_suffix(solver: Solver, cases: Sequence[CaseOnPair]) -> str:
    """What a passing pair gave: the count of cases where more than one
    gave grids, and for a solver whose `out` holds resolutions, the count
    of distinct grids where some case gives more than one."""
    given = [c.outcome for c in cases if isinstance(c.outcome, Grids)]
    parts: list[str] = []
    if len(given) > 1:
        parts.append(counted(len(given), mctx("witnessed case")))
    if resolved(solver) and any(len(g.grids) > 1 for g in given):
        grids = {grid for g in given for grid in g.grids}
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
    eh, ew = grid_size(expected)
    ah, aw = grid_size(actual)
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
    the stored output, or why it is undefined (`undefined_lines`), one
    group per reason, under the fewest names of the cases that give it
    (`pair_failure_lines`)."""
    from checker.render.built import undefined_lines

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
        by.setdefault(o.reason if isinstance(o, Undefined)
                      else output_key(o), (o, []))[1].append(c.case)
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
