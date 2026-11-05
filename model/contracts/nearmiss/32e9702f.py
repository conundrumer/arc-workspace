import json
from pathlib import Path


def _shape(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def _shifted(inp, dr, dc, fill=5, keep_old=False, wrap=False):
    h, w = len(inp), len(inp[0])
    g = [[fill] * w for _ in range(h)]
    cells = _shape(inp)
    if keep_old:
        for r, c, v in cells:
            g[r][c] = v
    for r, c, v in cells:
        nr, nc = r + dr, c + dc
        if wrap:
            nr, nc = nr % h, nc % w
        if 0 <= nr < h and 0 <= nc < w:
            g[nr][nc] = v
    return g


def right(inp, out):
    return _shifted(inp, 0, 1)


def up(inp, out):
    return _shifted(inp, -1, 0)


def down(inp, out):
    return _shifted(inp, 1, 0)


def left2(inp, out):
    return _shifted(inp, 0, -2)


def diag_up_left(inp, out):
    return _shifted(inp, -1, -1)


def no_move(inp, out):
    return _shifted(inp, 0, 0)


def union(inp, out):
    return _shifted(inp, 0, -1, keep_old=True)


def bg_zero(inp, out):
    return _shifted(inp, 0, -1, fill=0)


def swapped(inp, out):
    color = _shape(inp)[0][2]
    return [[color if v == 5 else 5 for v in row] for row in out]


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def fill_shape_color(inp, out):
    color = _shape(inp)[0][2]
    return _shifted(inp, 0, -1, fill=color)


ALTERNATIVES = [
    ("shape moves right instead of left", right),
    ("shape moves up instead of left", up),
    ("shape moves down instead of left", down),
    ("shape moves left by two cells", left2),
    ("shape moves diagonally up-left", diag_up_left),
    ("shape does not move, background only becomes 5", no_move),
    ("old shape cells stay colored, new shifted cells added", union),
    ("background stays 0 instead of becoming 5", bg_zero),
    ("roles swapped: shifted shape gets 5, rest gets shape color", swapped),
    ("correct output transposed", transpose),
    ("background filled with shape color, shifted shape cells keep it", fill_shape_color),
]


def _valid(g):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    return all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/32e9702f.json"))
    train = task["train"]
    print("readings:", len(ALTERNATIVES), "pairs:", len(train))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
