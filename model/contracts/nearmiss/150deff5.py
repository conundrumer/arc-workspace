import json
from pathlib import Path


def _copy(g):
    return [r[:] for r in g]


def _swap(inp, out):
    m = {8: 2, 2: 8}
    return [[m.get(v, v) for v in r] for r in out]


def _all(color):
    def f(inp, out):
        return [[color if v == 5 else v for v in r] for r in inp]
    return f


def _only(keep, other):
    # paint only cells of one color; the other piece kind stays 5
    def f(inp, out):
        return [[(5 if v == other else v) for v in r] for r in out]
    return f


def _greedy(order):
    def f(inp, out):
        h, w = len(inp), len(inp[0])
        g = _copy(inp)
        for r in range(h):
            for c in range(w):
                if g[r][c] != 5:
                    continue
                for kind in order:
                    if kind == "sq":
                        cells = [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]
                        col = 8
                    elif kind == "h":
                        cells = [(r, c), (r, c + 1), (r, c + 2)]
                        col = 2
                    else:
                        cells = [(r, c), (r + 1, c), (r + 2, c)]
                        col = 2
                    if all(0 <= a < h and 0 <= b < w and g[a][b] == 5 for a, b in cells):
                        for a, b in cells:
                            g[a][b] = col
                        break
        return g if g != out else None
    return f


def _vertical_bars_as_8(inp, out):
    h, w = len(out), len(out[0])
    g = _copy(out)
    for r in range(h):
        for c in range(w):
            if out[r][c] == 2 and ((r > 0 and out[r - 1][c] == 2) or (r + 1 < h and out[r + 1][c] == 2)):
                g[r][c] = 8
    return g


def _shift(dr, dc):
    def f(inp, out):
        h, w = len(out), len(out[0])
        g = [[0] * w for _ in range(h)]
        for r in range(h):
            for c in range(w):
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w:
                    g[rr][cc] = out[r][c]
        return g
    return f


def _crop(inp, out):
    rows = [r for r, row in enumerate(out) if any(row)]
    cols = [c for c in range(len(out[0])) if any(row[c] for row in out)]
    return [row[cols[0]:cols[-1] + 1] for row in out[rows[0]:rows[-1] + 1]]


def _overlap_squares(inp, out):
    # every 2x2 block of shape cells is painted 8; remaining cells 2
    h, w = len(inp), len(inp[0])
    g = [[2 if v == 5 else v for v in r] for r in inp]
    for r in range(h - 1):
        for c in range(w - 1):
            if all(inp[a][b] == 5 for a in (r, r + 1) for b in (c, c + 1)):
                for a in (r, r + 1):
                    for b in (c, c + 1):
                        g[a][b] = 8
    return g


def _unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("squares painted 2 and bars painted 8 (colors swapped)", _swap),
    ("whole shape painted 8, no bars", _all(8)),
    ("whole shape painted 2, no squares", _all(2)),
    ("only the 2x2 squares painted 8; bars left 5", _only(8, 2)),
    ("only the bars painted 2; squares left 5", _only(2, 8)),
    ("greedy raster tiling, square first then horizontal then vertical bar", _greedy(["sq", "h", "v"])),
    ("greedy raster tiling, horizontal bar first then vertical bar then square", _greedy(["h", "v", "sq"])),
    ("vertical bars painted 8 like squares, only horizontal bars 2", _vertical_bars_as_8),
    ("correct tiling shifted one row down", _shift(1, 0)),
    ("correct output cropped to the shape's bounding box", _crop),
    ("every 2x2 block of the shape painted 8 (overlaps allowed), rest 2", _overlap_squares),
    ("input returned unchanged", _unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/150deff5.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
