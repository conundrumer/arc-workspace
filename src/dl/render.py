"""Render grids and failing pairs as text."""

from collections import defaultdict

from dl.solve import PairResult
from dl.souffle import TEMP_NAME_RE


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


def _short(name: str) -> str:
    """Variant label for listings; a resolution enumeration term gets elided."""
    return name if len(name) <= 40 else name[:37] + "..."


def _error_lines(error: str) -> list[str]:
    """An error indented under its pair. A Souffle failure carries what it
    hit on lines of its own, and each of them sits at that indent."""
    return [f"  {line}" for line in error.splitlines()]


def render_stem_failures(stem: str, pairs: list[PairResult]) -> list[str]:
    """Failure lines for one stem's pairs. A source-level error fails every
    pair the same way, so a single error shared by all of them prints once.

    Each pair runs from a tempfile of its own and Souffle names that file,
    so the solver stands in for the name before the errors are compared —
    and in what prints, which names a file the reader can open.
    """
    bad = [p for p in pairs if not p.ok]
    shared = {TEMP_NAME_RE.sub(f"{stem}.dl", p.error) for p in bad if p.error}
    if len(bad) > 1 and len(shared) == 1 and all(p.error for p in bad):
        names = ", ".join(f"{p.kind}[{p.idx}]" for p in bad)
        return [f"{names}: FAIL", *_error_lines(shared.pop())]
    return [line for p in bad for line in render_pair_failure(p, stem)]


def render_pair_failure(p: PairResult, stem: str | None = None) -> list[str]:
    """Lines describing a failing pair: variant breakdown + diff per failing
    actual. With the stem given, the solver's name stands in for the
    tempfile's in the error."""
    lines = [f"{p.kind}[{p.idx}]: FAIL"]
    if p.error:
        error = TEMP_NAME_RE.sub(f"{stem}.dl", p.error) if stem else p.error
        lines.extend(_error_lines(error))
        return lines
    if not p.variants:
        lines.append("  (no variants emitted)")
        return lines

    if all(v.ok for v in p.variants):
        # Resolution semantics: some accepted grid was never emitted.
        produced = {tuple(tuple(r) for r in v.actual) for v in p.variants}
        absent = [
            g for g in (p.accepted or [])
            if tuple(tuple(r) for r in g) not in produced
        ]
        lines.append(f"  {len(absent)} accepted grid(s) never emitted:")
        for g in absent:
            lines.append("")
            lines.extend(f"    {gl}" for gl in _grid_lines(g))
        return lines

    has_named = any(v.name for v in p.variants)
    multi = len(p.variants) > 1

    if has_named or multi:
        pass_v = [_short(v.name) or "(out)" for v in p.variants if v.ok]
        fail_v = [_short(v.name) or "(out)" for v in p.variants if not v.ok]
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
            v.error,
        )
        groups[key].append(_short(v.name) or "(out)")

    for (actual_key, conflicts_tup, missing_tup, error), names in groups.items():
        actual = [list(r) for r in actual_key]
        lines.append("")
        if has_named or multi:
            lines.append(f"  {', '.join(names)}:")
        if error:
            lines.append(f"    {error}")
        if conflicts_tup:
            lines.append(f"    conflicts at: {list(conflicts_tup)}")
        if missing_tup:
            lines.append(f"    missing cells at: {list(missing_tup)}")
        if not error and not conflicts_tup and not missing_tup:
            for dl in render_diff(p.expected or [], actual):
                lines.append(f"    {dl}")

    return lines
