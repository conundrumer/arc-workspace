"""Render grids and failing pairs as text."""

from collections import defaultdict

from dl.solve import PairResult


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
