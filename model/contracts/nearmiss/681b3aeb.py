"""Near-miss rules for task 681b3aeb: two shapes fit together into one square."""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _shapes(inp):
    """Map color -> list of cells (r, c) for each non-background color."""
    bg = _bg(inp)
    cells = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != bg:
                cells.setdefault(v, []).append((r, c))
    return bg, cells


def _crop(cells):
    r0 = min(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    r1 = max(r for r, _ in cells)
    c1 = max(c for _, c in cells)
    return r0, c0, r1, c1


def _counts(out):
    return Counter(c for r in out for c in r).most_common()


def swap_colors(inp, out):
    cols = [c for c, _ in _counts(out)]
    if len(cols) != 2:
        return None
    a, b = cols
    return [[b if v == a else a if v == b else v for v in r] for r in out]


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def flip_vertical(inp, out):
    return [list(r) for r in out[::-1]]


def rotate_180(inp, out):
    return [list(r[::-1]) for r in out[::-1]]


def erase_minority(inp, out):
    cs = _counts(out)
    if len(cs) < 2 or cs[-1][1] == cs[-2][1]:
        return None
    m = cs[-1][0]
    return [[0 if v == m else v for v in r] for r in out]


def monochrome_majority(inp, out):
    cs = _counts(out)
    if len(cs) < 2 or cs[0][1] == cs[1][1]:
        return None
    m = cs[0][0]
    return [[m for _ in r] for r in out]


def drop_last_row_col(inp, out):
    return [list(r[:-1]) for r in out[:-1]]


def crop_all_nonbg(inp, out):
    bg, cells = _shapes(inp)
    allc = [p for v in cells.values() for p in v]
    r0, c0, r1, c1 = _crop(allc)
    return [list(inp[r][c0:c1 + 1]) for r in range(r0, r1 + 1)]


def side_by_side(inp, out):
    bg, cells = _shapes(inp)
    crops = []
    for col, cs in sorted(cells.items(), key=lambda kv: min(c for _, c in kv[1])):
        r0, c0, r1, c1 = _crop(cs)
        g = [[bg] * (c1 - c0 + 1) for _ in range(r1 - r0 + 1)]
        for r, c in cs:
            g[r - r0][c - c0] = col
        crops.append(g)
    h = max(len(g) for g in crops)
    rows = []
    for i in range(h):
        row = []
        for g in crops:
            row += g[i] if i < len(g) else [bg] * len(g[0])
        rows.append(row)
    return rows


def overlay_top_left(inp, out):
    bg, cells = _shapes(inp)
    n = len(out)
    grid = [[bg] * len(out[0]) for _ in range(n)]
    for col in sorted(cells):
        r0, c0, _, _ = _crop(cells[col])
        for r, c in cells[col]:
            if r - r0 < n and c - c0 < len(out[0]):
                grid[r - r0][c - c0] = col
    return grid


def input_corner(inp, out):
    return [list(r[:len(out[0])]) for r in inp[:len(out)]]


def _guard(f):
    def g(inp, out):
        res = f(inp, out)
        if res is None or res == out:
            return None
        return res
    return g


ALTERNATIVES = [
    ("the two shapes swap colors", swap_colors),
    ("the filled square is transposed", transpose),
    ("the filled square is flipped top to bottom", flip_vertical),
    ("the filled square is rotated 180 degrees", rotate_180),
    ("the smaller shape is left out, its cells stay background", erase_minority),
    ("the whole square takes the color of the larger shape", monochrome_majority),
    ("the square is one row and one column too small", drop_last_row_col),
    ("the answer is the crop of all non-background cells", crop_all_nonbg),
    ("the shape crops are placed side by side, not fitted together", side_by_side),
    ("both shapes are pasted at the square's top-left corner, later color over earlier", overlay_top_left),
    ("the answer is the input's top-left corner of the output size", input_corner),
]
ALTERNATIVES = [(d, _guard(f)) for d, f in ALTERNATIVES]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/681b3aeb.json').read_text())
    pairs = task["train"]
    print(f"{len(pairs)} train pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
