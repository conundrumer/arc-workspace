"""Near-miss rules for ARC task 6e02f1e3.

Rule: the output is 3x3, 0 background, 5 mark. The number of distinct colors
in the input picks the shape: 1 -> top row, 2 -> main diagonal,
3 -> anti-diagonal.
"""
import json
from pathlib import Path

ROW = [(0, 0), (0, 1), (0, 2)]
MAIN = [(0, 0), (1, 1), (2, 2)]
ANTI = [(0, 2), (1, 1), (2, 0)]
SHAPES = [ROW, MAIN, ANTI]


def _ncolors(inp):
    return len({v for r in inp for v in r})


def _draw(cells, n=3, mark=5, bg=0):
    g = [[bg] * n for _ in range(n)]
    for r, c in cells:
        if 0 <= r < n and 0 <= c < n:
            g[r][c] = mark
    return g


def _cells(out, mark=5):
    return [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v == mark]


def _same(a, b):
    return a == b


def _ok(g, out):
    return None if g == out else g


def flip_vertical(inp, out):
    """Shape flipped top to bottom: row at the bottom, diagonals swapped."""
    return _ok([list(r) for r in reversed(out)], out)


def shape_cycle(inp, out):
    """Shape picked by N mod 3 instead of N-1: off by one in the shape index."""
    n = _ncolors(inp)
    return _ok(_draw(SHAPES[n % 3]), out)


def mark_from_input(inp, out):
    """Correct shape, but drawn in the input's most common color."""
    flat = [v for r in inp for v in r]
    col = max(set(flat), key=flat.count)
    return _ok([[col if v == 5 else v for v in r] for r in out], out)


def swap_mark_bg(inp, out):
    """Mark and background colors exchanged."""
    return _ok([[0 if v == 5 else 5 for v in r] for r in out], out)


def x_shape(inp, out):
    """Both diagonals drawn when there is more than one color."""
    n = _ncolors(inp)
    if n == 1:
        return _ok(_draw(ROW), out)
    return _ok(_draw(MAIN + ANTI), out)


def size_by_n(inp, out):
    """Output size follows the color count: an N x N grid with the diagonal."""
    n = _ncolors(inp)
    shape = [(i, i) for i in range(n)]
    return _ok(_draw(shape, n), out)


def shifted_shape(inp, out):
    """Shape right but offset by one: row in the middle, diagonals shifted."""
    cells = _cells(out)
    if cells == ROW:
        new = [(1, 0), (1, 1), (1, 2)]
    elif cells == MAIN:
        new = [(0, 1), (1, 2)]
    else:
        new = [(0, 1), (1, 0)]
    return _ok(_draw(new), out)


def always_main(inp, out):
    """Every diagonal case uses the main diagonal."""
    n = _ncolors(inp)
    return _ok(_draw(ROW if n == 1 else MAIN), out)


def drop_last_cell(inp, out):
    """Shape one cell too short: last marked cell left as background."""
    cells = _cells(out)
    return _ok(_draw(cells[:-1]), out)


def transpose_shape(inp, out):
    """Row case drawn as the left column; anti-diagonal read as main."""
    n = _ncolors(inp)
    if n == 1:
        return _ok(_draw([(0, 0), (1, 0), (2, 0)]), out)
    if n == 2:
        return _ok(_draw(ANTI), out)
    return _ok(_draw(MAIN), out)


def identity(inp, out):
    """Input returned unchanged."""
    return _ok([list(r) for r in inp], out)


def cumulative_shapes(inp, out):
    """Shapes accumulate with N: row, row+main, row+main+anti."""
    n = _ncolors(inp)
    cells = []
    for s in SHAPES[:n]:
        cells += s
    return _ok(_draw(cells), out)


ALTERNATIVES = [
    ("shape flipped top to bottom (bottom row, diagonals swapped)", flip_vertical),
    ("shape index off by one (N mod 3 instead of N-1)", shape_cycle),
    ("shape drawn in the input's most common color instead of 5", mark_from_input),
    ("mark and background colors exchanged", swap_mark_bg),
    ("both diagonals drawn when more than one color", x_shape),
    ("output sized N x N from the color count", size_by_n),
    ("shape offset by one cell", shifted_shape),
    ("main diagonal used for every multi-color input", always_main),
    ("shape one cell too short", drop_last_cell),
    ("shape transposed or diagonal orientation swapped", transpose_shape),
    ("shapes accumulate with the color count", cumulative_shapes),
    ("input returned unchanged", identity),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/6e02f1e3.json").read_text())
    pairs = task["train"]
    print(f"pairs: {len(pairs)}")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
