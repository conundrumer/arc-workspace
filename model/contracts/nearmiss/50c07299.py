"""Near-miss readings for ARC task 50c07299.

Input: a short diagonal segment of N ink cells (up-right direction) on a
uniform background. Output: the segment is erased and a new segment of N+1
cells is drawn, starting at the cell next to the old leading end and
continuing in the same direction.
"""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _marks(inp):
    b = _bg(inp)
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != b]
    cells.sort()  # smallest row first: the leading end for an up-right segment
    return cells, b


def _ink(inp):
    b = _bg(inp)
    return next(v for row in inp for v in row if v != b)


def _blank(inp):
    b = _bg(inp)
    return [[b] * len(inp[0]) for _ in inp]


def _paint(grid, cells, color):
    h, w = len(grid), len(grid[0])
    for r, c in cells:
        if 0 <= r < h and 0 <= c < w:
            grid[r][c] = color


def _draw(inp, start, step, n, keep_marks=False, color=None):
    g = [row[:] for row in inp] if keep_marks else _blank(inp)
    color = _ink(inp) if color is None else color
    r, c = start
    dr, dc = step
    _paint(g, [(r + i * dr, c + i * dc) for i in range(n)], color)
    return g


def _lead(inp):
    cells, _ = _marks(inp)
    return cells[0], cells[-1], len(cells)


def keep_marks(inp, out):
    (r, c), _, n = _lead(inp)
    return _draw(inp, (r - 1, c + 1), (-1, 1), n + 1, keep_marks=True)


def length_n(inp, out):
    (r, c), _, n = _lead(inp)
    return _draw(inp, (r - 1, c + 1), (-1, 1), n)


def length_n_plus_2(inp, out):
    (r, c), _, n = _lead(inp)
    return _draw(inp, (r - 1, c + 1), (-1, 1), n + 2)


def backward_from_trailing(inp, out):
    _, (r, c), n = _lead(inp)
    return _draw(inp, (r + 1, c - 1), (1, -1), n + 1)


def mirrored_direction(inp, out):
    (r, c), _, n = _lead(inp)
    return _draw(inp, (r - 1, c - 1), (-1, -1), n + 1)


def gap_before_segment(inp, out):
    (r, c), _, n = _lead(inp)
    return _draw(inp, (r - 2, c + 2), (-1, 1), n + 1)


def starts_on_leading_mark(inp, out):
    (r, c), _, n = _lead(inp)
    return _draw(inp, (r, c), (-1, 1), n + 1)


def ray_to_edge(inp, out):
    (r, c), _, n = _lead(inp)
    h, w = len(inp), len(inp[0])
    k = min(r, w - 1 - c)
    return _draw(inp, (r - 1, c + 1), (-1, 1), k)


def other_color(inp, out):
    used = {v for row in inp for v in row}
    col = next(v for v in range(10) if v not in used)
    (r, c), _, n = _lead(inp)
    return _draw(inp, (r - 1, c + 1), (-1, 1), n + 1, color=col)


def both_ends(inp, out):
    (r, c), (r2, c2), n = _lead(inp)
    g = _draw(inp, (r - 1, c + 1), (-1, 1), n + 1)
    _paint(g, [(r2 + i, c2 - i) for i in range(1, n + 2)], _ink(inp))
    return g


def horizontal_line(inp, out):
    (r, c), _, n = _lead(inp)
    return _draw(inp, (r, c + 1), (0, 1), n + 1)


def shifted_whole_segment(inp, out):
    cells, _ = _marks(inp)
    n = len(cells)
    g = _blank(inp)
    _paint(g, [(r - n, c + n) for r, c in cells], _ink(inp))
    return g


ALTERNATIVES = [
    ("new segment drawn but the original marks are left in place", keep_marks),
    ("new segment has N cells instead of N+1", length_n),
    ("new segment has N+2 cells", length_n_plus_2),
    ("new segment grows from the trailing end, backward", backward_from_trailing),
    ("new segment goes up-left, the mirrored diagonal", mirrored_direction),
    ("new segment starts one cell too far, leaving a gap", gap_before_segment),
    ("new segment starts on the old leading mark, off by one", starts_on_leading_mark),
    ("new segment runs on to the grid edge", ray_to_edge),
    ("new segment drawn in a color absent from the input", other_color),
    ("new segment grows from both ends of the old one", both_ends),
    ("new segment drawn as a horizontal line", horizontal_line),
    ("old segment moved along its direction by its length, same size", shifted_whole_segment),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/50c07299.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
