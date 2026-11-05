import json
from pathlib import Path

FG = 2
NEW = 6


def components(inp, diag=False):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    nbrs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diag:
        nbrs += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for r in range(h):
        for c in range(w):
            if inp[r][c] != FG or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in nbrs:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == FG and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append(cells)
    return comps


def paint(inp, cells, color=NEW):
    g = [row[:] for row in inp]
    for r, c in cells:
        if 0 <= r < len(g) and 0 <= c < len(g[0]):
            g[r][c] = color
    return g


def bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def threshold(k, diag=False):
    def f(inp, out):
        cells = [p for comp in components(inp, diag) if len(comp) >= k for p in comp]
        return paint(inp, cells)
    return f


def wrong_color(inp, out):
    return [[8 if v == NEW else v for v in row] for row in out]


def only_largest(inp, out):
    comps = components(inp)
    m = max(len(c) for c in comps)
    return paint(inp, [p for c in comps if len(c) == m for p in c])


def inverted(inp, out):
    return paint(inp, [p for c in components(inp) if len(c) < 4 for p in c])


def first_left_unfilled(inp, out):
    comps = [c for c in components(inp) if len(c) >= 4]
    first = min(comps, key=lambda c: min(c))
    g = [row[:] for row in out]
    for r, c in first:
        g[r][c] = FG
    return g


def only_full_squares(inp, out):
    cells = []
    for comp in components(inp):
        r0, r1, c0, c1 = bbox(comp)
        if len(comp) == 4 and r1 - r0 == 1 and c1 - c0 == 1:
            cells += comp
    return paint(inp, cells)


def bbox_area_threshold(inp, out):
    cells = []
    for comp in components(inp):
        r0, r1, c0, c1 = bbox(comp)
        if (r1 - r0 + 1) * (c1 - c0 + 1) >= 6:
            cells += comp
    return paint(inp, cells)


def fill_bbox(inp, out):
    cells = []
    for comp in components(inp):
        if len(comp) >= 4:
            r0, r1, c0, c1 = bbox(comp)
            cells += [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    return paint(inp, cells)


def shifted_right(inp, out):
    cells = [(r, c + 1) for comp in components(inp) if len(comp) >= 4 for r, c in comp]
    return paint(inp, cells)


def only_four(inp, out):
    return paint(inp, [p for c in components(inp) if len(c) == 4 for p in c])


ALTERNATIVES = [
    ("recolor shapes of at least 3 cells (min size off by one, too low)", threshold(3)),
    ("recolor shapes of at least 5 cells (min size off by one, too high)", threshold(5)),
    ("shapes join at corners (8-connectivity) with min size 3", threshold(3, diag=True)),
    ("recolor large shapes to 8 instead of 6", wrong_color),
    ("recolor only the largest shape(s)", only_largest),
    ("recolor the small shapes (fewer than 4 cells) instead of the large ones", inverted),
    ("true output with the first large shape left unrecolored", first_left_unfilled),
    ("recolor only 2x2 square shapes", only_full_squares),
    ("recolor shapes whose bounding box has at least 6 cells", bbox_area_threshold),
    ("fill the whole bounding box of each large shape with 6", fill_bbox),
    ("recolor mask of large shapes placed one column to the right", shifted_right),
    ("recolor only shapes of exactly 4 cells", only_four),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/ae58858e.json"))
    train = task["train"]
    print("pairs", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
