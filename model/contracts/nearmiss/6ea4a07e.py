import json
from pathlib import Path


def _color(inp):
    return next(v for r in inp for v in r if v)


def _fill(out):
    return next(v for r in out for v in r if v)


def _same(a, b):
    return a == b


def no_inversion(inp, out):
    f = _fill(out)
    return [[f if v else 0 for v in r] for r in inp]


def keep_input_color(inp, out):
    c = _color(inp)
    return [[0 if v else c for v in r] for r in inp]


def wrong_color_map(inp, out):
    m = {8: 4, 3: 2, 5: 1}
    f = m[_color(inp)]
    return [[0 if v else f for v in r] for r in inp]


def constant_two(inp, out):
    g = [[0 if v else 2 for v in r] for r in inp]
    return None if g == out else g


def constant_four(inp, out):
    g = [[0 if v else 4 for v in r] for r in inp]
    return None if g == out else g


def swap_colors(inp, out):
    c = _color(inp)
    f = _fill(out)
    return [[f if v else c for v in r] for r in inp]


def adjacent_only(inp, out):
    f = _fill(out)
    n, m = len(inp), len(inp[0])
    g = []
    for i in range(n):
        row = []
        for j in range(m):
            if inp[i][j]:
                row.append(0)
                continue
            adj = any(
                0 <= i + di < n and 0 <= j + dj < m and inp[i + di][j + dj]
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
            row.append(f if adj else 0)
        g.append(row)
    return None if g == out else g


def transposed(inp, out):
    g = [list(r) for r in zip(*out)]
    return None if g == out else g


def mirrored(inp, out):
    g = [r[::-1] for r in out]
    return None if g == out else g


def drop_first_row(inp, out):
    return [list(r) for r in out[1:]]


def drop_last_column(inp, out):
    return [list(r[:-1]) for r in out]


def last_row_unfilled(inp, out):
    g = [list(r) for r in out]
    g[-1] = [0] * len(g[-1])
    return None if g == out else g


ALTERNATIVES = [
    ("fill the object cells with the new color instead of the background cells", no_inversion),
    ("fill the background with the input object color (no recoloring)", keep_input_color),
    ("recolor with a wrong color mapping (8->4, 3->2, 5->1)", wrong_color_map),
    ("always use color 2 as fill color", constant_two),
    ("always use color 4 as fill color", constant_four),
    ("swap roles: object cells get the new color, background keeps the input color", swap_colors),
    ("fill only background cells that touch an object cell orthogonally", adjacent_only),
    ("transpose the correct output", transposed),
    ("mirror the correct output left to right", mirrored),
    ("output lacks the first row (off-by-one crop)", drop_first_row),
    ("output lacks the last column (off-by-one crop)", drop_last_column),
    ("last row left unfilled", last_row_unfilled),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/6ea4a07e.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
