import json
from pathlib import Path


def seeds(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def new_color(inp):
    used = {v for row in inp for v in row}
    return 2 if 2 not in used else min(k for k in range(1, 10) if k not in used)


def render(inp, rows=True, cols=True, cross=None, keep_seed=True, dr=0, dc=0,
           down_right_only=False, first_only=False, collide_off=False):
    """Draw lines through seeds; cross says what an intersection of two seeds' lines gets."""
    h, w = len(inp), len(inp[0])
    ss = seeds(inp)
    if first_only:
        ss = ss[:1]
    cross = new_color(inp) if cross is None else cross
    res = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            rs = [s for s in ss if s[0] + dr == r and rows and (not down_right_only or c >= s[1])]
            cs = [s for s in ss if s[1] + dc == c and cols and (not down_right_only or r >= s[0])]
            own = [s for s in ss if s[0] == r and s[1] == c]
            if own and keep_seed:
                res[r][c] = own[0][2]
            elif rs and cs:
                if callable(cross):
                    res[r][c] = cross(rs[0][2], cs[0][2])
                else:
                    res[r][c] = cross
            elif rs:
                res[r][c] = rs[0][2]
            elif cs:
                res[r][c] = cs[0][2]
    return res


def rows_only(inp, out):
    return render(inp, cols=False)


def cols_only(inp, out):
    return render(inp, rows=False)


def cross_row_color(inp, out):
    return render(inp, cross=lambda a, b: a)


def cross_col_color(inp, out):
    return render(inp, cross=lambda a, b: b)


def cross_background(inp, out):
    return render(inp, cross=0)


def seeds_become_cross(inp, out):
    g = render(inp)
    nc = new_color(inp)
    for r, c, v in seeds(inp):
        g[r][c] = nc
    return g


def rays_down_right(inp, out):
    return render(inp, down_right_only=True)


def shifted_column(inp, out):
    w = len(inp[0])
    if any(c + 1 >= w for _, c, _ in seeds(inp)):
        return None
    return render(inp, dc=1)


def only_first_seed(inp, out):
    return render(inp, first_only=True)


def diagonals(inp, out):
    h, w = len(inp), len(inp[0])
    res = [[0] * w for _ in range(h)]
    for r, c, v in seeds(inp):
        for i in range(-max(h, w), max(h, w)):
            for rr, cc in ((r + i, c + i), (r + i, c - i)):
                if 0 <= rr < h and 0 <= cc < w:
                    res[rr][cc] = v
    return res


def only_intersections(inp, out):
    h, w = len(inp), len(inp[0])
    nc = new_color(inp)
    res = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            if out[r][c] == nc:
                res[r][c] = nc
    for r, c, v in seeds(inp):
        res[r][c] = v
    return res


ALTERNATIVES = [
    ("only horizontal lines are drawn", rows_only),
    ("only vertical lines are drawn", cols_only),
    ("a crossing of two seeds' lines takes the row line's color", cross_row_color),
    ("a crossing of two seeds' lines takes the column line's color", cross_col_color),
    ("a crossing of two seeds' lines stays background", cross_background),
    ("the seed cells themselves also get the crossing color", seeds_become_cross),
    ("lines extend only down and right from each seed", rays_down_right),
    ("the vertical line is one column right of its seed", shifted_column),
    ("only the first seed in reading order draws lines", only_first_seed),
    ("seeds draw diagonals instead of rows and columns", diagonals),
    ("only the crossings and seeds are drawn, no lines", only_intersections),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/45bbe264.json"))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
