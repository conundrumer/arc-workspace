import json
from pathlib import Path


def _field_and_mark(inp, out):
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if out[r][c] != v:
                return v, out[r][c]
    return None, None


def _centers(inp, col, arms=((-1, 0), (1, 0), (0, -1), (0, 1))):
    h, w = len(inp), len(inp[0])
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != col:
                continue
            ok = True
            for dr, dc in arms:
                rr, cc = r + dr, c + dc
                if not (0 <= rr < h and 0 <= cc < w and inp[rr][cc] == col):
                    ok = False
                    break
            if ok:
                res.append((r, c))
    return res


PLUS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _paint(inp, cells, mark):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for r, c in cells:
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = mark
    return g


def _plus_cells(centers, offsets=PLUS, center=True):
    cells = set()
    for r, c in centers:
        if center:
            cells.add((r, c))
        for dr, dc in offsets:
            cells.add((r + dr, c + dc))
    return cells


def only_centers(inp, out):
    f, m = _field_and_mark(inp, out)
    return _paint(inp, _centers(inp, f), m)


def arms_only(inp, out):
    f, m = _field_and_mark(inp, out)
    cells = _plus_cells(_centers(inp, f), center=False)
    return _paint(inp, cells, m)


def horizontal_only(inp, out):
    f, m = _field_and_mark(inp, out)
    cells = _plus_cells(_centers(inp, f), offsets=((0, -1), (0, 1)))
    return _paint(inp, cells, m)


def vertical_only(inp, out):
    f, m = _field_and_mark(inp, out)
    cells = _plus_cells(_centers(inp, f), offsets=((-1, 0), (1, 0)))
    return _paint(inp, cells, m)


def other_color_plus(inp, out):
    f, m = _field_and_mark(inp, out)
    cols = {v for row in inp for v in row}
    others = cols - {f}
    if len(others) != 1:
        return None
    o = others.pop()
    return _paint(inp, _plus_cells(_centers(inp, o)), m)


def both_colors_plus(inp, out):
    f, m = _field_and_mark(inp, out)
    cells = set()
    for col in {v for row in inp for v in row}:
        cells |= _plus_cells(_centers(inp, col))
    return _paint(inp, cells, m)


def square_3x3(inp, out):
    f, m = _field_and_mark(inp, out)
    sq = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0))
    return _paint(inp, _plus_cells(_centers(inp, f), offsets=sq), m)


def x_shape(inp, out):
    f, m = _field_and_mark(inp, out)
    diag = ((-1, -1), (-1, 1), (1, -1), (1, 1))
    return _paint(inp, _plus_cells(_centers(inp, f, arms=diag), offsets=diag), m)


def long_plus(inp, out):
    f, m = _field_and_mark(inp, out)
    arms = tuple((k * dr, k * dc) for dr, dc in PLUS for k in (1, 2))
    return _paint(inp, _plus_cells(_centers(inp, f), offsets=arms), m)


def first_plus_only(inp, out):
    f, m = _field_and_mark(inp, out)
    cs = _centers(inp, f)
    if not cs:
        return None
    return _paint(inp, _plus_cells(cs[:1]), m)


def skip_first_plus(inp, out):
    f, m = _field_and_mark(inp, out)
    cs = _centers(inp, f)
    return _paint(inp, _plus_cells(cs[1:]), m)


def clipped_edge_pluses(inp, out):
    # centers on the border count when the in-bounds arms match
    f, m = _field_and_mark(inp, out)
    h, w = len(inp), len(inp[0])
    cells = set()
    for r in range(h):
        for c in range(w):
            if inp[r][c] != f:
                continue
            ok = True
            for dr, dc in PLUS:
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] != f:
                    ok = False
                    break
            if ok:
                cells.add((r, c))
                for dr, dc in PLUS:
                    cells.add((r + dr, c + dc))
    return _paint(inp, cells, m)


def wrong_mark_color(inp, out):
    f, m = _field_and_mark(inp, out)
    wrong = 1 if m != 1 else 2
    return [[wrong if out[r][c] == m and inp[r][c] != m else out[r][c]
             for c in range(len(out[0]))] for r in range(len(out))]


ALTERNATIVES = [
    ("paint only the plus centers", only_centers),
    ("paint the plus arms but leave the center unchanged", arms_only),
    ("paint only the horizontal 3-cell bar of each plus", horizontal_only),
    ("paint only the vertical 3-cell bar of each plus", vertical_only),
    ("look for pluses of the other background color", other_color_plus),
    ("accept pluses of both colors", both_colors_plus),
    ("paint a full 3x3 square around each plus center", square_3x3),
    ("stamp an X (diagonal) shape instead of a plus", x_shape),
    ("paint arms of length 2 around each plus center", long_plus),
    ("paint only the first plus in reading order", first_plus_only),
    ("let pluses clipped by the border count", clipped_edge_pluses),
    ("paint the plus in the wrong color", wrong_mark_color),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/7e02026e.json").read_text())
    pairs = task["train"]

    def valid(g, out):
        if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
            return False
        if len({len(r) for r in g}) != 1 or not g[0]:
            return False
        if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
            return False
        return g != out

    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
