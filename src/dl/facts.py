"""Encode grids as Souffle facts and decode Souffle's text output."""

import json
import re

from dl.source import _split_args


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


def example_facts(task) -> dict[str, str]:
    """Fact-file contents for a task's examples: inputs for train then
    test, outputs for train only."""
    def emit(grids: list[list[list[int]]]) -> str:
        return "".join(
            f"{e}\t{line}\n"
            for e, rows in enumerate(grids)
            for line in grid_to_facts(rows).splitlines()
        )
    inputs = [ex.input for ex in task.train] + [ex.input for ex in task.test]
    return {
        "ex_in.facts": emit(inputs),
        "ex_out.facts": emit([ex.output for ex in task.train]),
    }


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


def _parse_block(stdout: str) -> list[str]:
    """Rows of the single relation block in Souffle's -D- output."""
    parts = re.split(r"^={3,}$", stdout, flags=re.MULTILINE)
    if len(parts) < 3:
        raise ValueError(f"unexpected souffle output:\n{stdout}")
    data = parts[1].strip()
    return [line for line in data.splitlines() if line] if data else []


def _parse_relations(stdout: str) -> dict[str, list[str]]:
    """Rows per relation block in Souffle's -D- output."""
    rels = {}
    for m in re.finditer(
        r"^-+\n(\S+)\n.*?\n=+\n(.*?)=+\n", stdout, flags=re.MULTILINE | re.DOTALL
    ):
        rels[m.group(1)] = [line for line in m.group(2).splitlines() if line]
    return rels


def _parse_value(text: str):
    """One output column: a Position record as an int tuple, else an int."""
    if text.startswith("["):
        return tuple(int(x) for x in _split_args(text[1:-1]))
    return int(text)


def parse_grid(text: str) -> list[list[int]]:
    """A hand-written grid as rows of colors.

    One line per row, one character per cell: a digit 0-9, or `.` for 0.
    Spaces and commas between cells are optional, blank lines and `#`
    comment lines are skipped. Text that starts with `[` is read as JSON
    instead, so a grid pasted out of a task file works unchanged.
    """
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty grid")
    if stripped.startswith("["):
        rows = json.loads(stripped)
    else:
        rows = [
            [0 if ch == "." else int(ch) for ch in re.sub(r"[\s,]", "", line)]
            for line in stripped.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    if not rows or not rows[0]:
        raise ValueError("empty grid")
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        raise ValueError(f"rows differ in width: {sorted(widths)}")
    for row in rows:
        for cell in row:
            if not isinstance(cell, int) or not 0 <= cell <= 9:
                raise ValueError(f"cell out of range: {cell!r}")
    return rows
