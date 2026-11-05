import json
from pathlib import Path

MARK = 4


def pockets(g):
    """Zero-cell 4-connected components, ordered by leftmost column."""
    h, w = len(g), len(g[0])
    seen = set()
    cs = []
    for c in range(w):
        for r in range(h):
            if g[r][c] == 0 and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cc = []
                while st:
                    y, x = st.pop()
                    cc.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        a, b = y + dy, x + dx
                        if 0 <= a < h and 0 <= b < w and g[a][b] == 0 and (a, b) not in seen:
                            seen.add((a, b))
                            st.append((a, b))
                cs.append(cc)
    cs.sort(key=lambda c: min(x for _, x in c))
    return cs


def paint(inp, cells, color=MARK):
    g = [row[:] for row in inp]
    for y, x in cells:
        g[y][x] = color
    return g


def by_rank(inp, pred, color=MARK, ps=None):
    ps = pockets(inp) if ps is None else ps
    cells = [p for i, c in enumerate(ps) if pred(i, len(ps)) for p in c]
    return paint(inp, cells, color)


def wrong_color(inp, out):
    return [[3 if v == MARK else v for v in row] for row in out]


def mark_all(inp, out):
    return by_rank(inp, lambda i, n: True)


def mark_complement(inp, out):
    return by_rank(inp, lambda i, n: i % 3 != 0)


def shifted_one(inp, out):
    return by_rank(inp, lambda i, n: i % 3 == 1)


def every_second(inp, out):
    return by_rank(inp, lambda i, n: i % 2 == 0)


def every_fourth(inp, out):
    return by_rank(inp, lambda i, n: i % 4 == 0)


def first_only(inp, out):
    return by_rank(inp, lambda i, n: i == 0)


def from_right_edge(inp, out):
    return by_rank(inp, lambda i, n: (n - 1 - i) % 3 == 0)


def from_bottom_row_order(inp, out):
    # order pockets by lowest row first instead of by column
    ps = sorted(pockets(inp), key=lambda c: (-max(y for y, _ in c), min(x for _, x in c)))
    return by_rank(inp, lambda i, n: i % 3 == 0, ps=ps)


def bbox_fill(inp, out):
    g = [row[:] for row in inp]
    for i, c in enumerate(pockets(inp)):
        if i % 3 == 0:
            y0, y1 = min(y for y, _ in c), max(y for y, _ in c)
            x0, x1 = min(x for _, x in c), max(x for _, x in c)
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    g[y][x] = MARK
    return g


def drop_last_marked(inp, out):
    ps = pockets(inp)
    idx = [i for i in range(len(ps)) if i % 3 == 0]
    return by_rank(inp, lambda i, n: i in idx[:-1])


def first_row_only(inp, out):
    ps = pockets(inp)
    cells = [(y, x) for i, c in enumerate(ps) if i % 3 == 0 for y, x in c if y == 0]
    return paint(inp, cells)


ALTERNATIVES = [
    ("marked pockets painted 3 instead of 4", wrong_color),
    ("every pocket is marked", mark_all),
    ("the kept pockets are marked and the marked ones kept", mark_complement),
    ("marking starts at the second pocket instead of the first", shifted_one),
    ("every second pocket is marked", every_second),
    ("every fourth pocket is marked", every_fourth),
    ("only the first pocket is marked", first_only),
    ("pocket sequence counted from the right edge", from_right_edge),
    ("pockets ranked from the bottom row up instead of left to right", from_bottom_row_order),
    ("marked pockets fill their whole bounding box", bbox_fill),
    ("the last marked pocket is left unmarked", drop_last_marked),
    ("only the top row of each marked pocket is painted", first_row_only),
]


def valid(g, out):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/7447852a.json").read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} pairs")
    for name, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {name}")
