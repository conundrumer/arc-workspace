"""Near-miss readings for ARC task 78e78cff.

Rule: the most common color is the background. One color has a single cell
(the seed). The remaining color forms a frame. The seed color floods the
frame's bounding box (4-connected, around frame cells) and then leaks out of
the box along the rows and columns that are open.
"""
import json
from collections import Counter, deque
from pathlib import Path


def parts(inp):
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    seed_col = next(c for c, n in cnt.items() if n == 1)
    frame_col = next(c for c in cnt if c not in (bg, seed_col))
    seed = next((i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == seed_col)
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == frame_col]
    r0 = min(i for i, _ in cells)
    r1 = max(i for i, _ in cells)
    c0 = min(j for _, j in cells)
    c1 = max(j for _, j in cells)
    return bg, seed_col, frame_col, seed, (r0, c0, r1, c1)


def copy(g):
    return [list(r) for r in g]


def flood(inp, seed, box, conn8=False, clip=True):
    h, w = len(inp), len(inp[0])
    bg, sc, fc, _, _ = parts(inp)
    r0, c0, r1, c1 = box
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if conn8:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    seen = {seed}
    q = deque([seed])
    while q:
        i, j = q.popleft()
        for di, dj in steps:
            a, b = i + di, j + dj
            if not (0 <= a < h and 0 <= b < w) or (a, b) in seen:
                continue
            if clip and not (r0 <= a <= r1 and c0 <= b <= c1):
                continue
            if inp[a][b] == fc:
                continue
            seen.add((a, b))
            q.append((a, b))
    return seen


def paint(inp, cells, col):
    g = copy(inp)
    for i, j in cells:
        g[i][j] = col
    return g


def box_flood_only(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    return paint(inp, flood(inp, seed, box), sc)


def diag_flood_only(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    return paint(inp, flood(inp, seed, box, conn8=True), sc)


def wrong_fill_color(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    return [[fc if v == sc else v for v in r] for r in out]


def overwrite_frame(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    r0, c0, r1, c1 = box
    g = copy(out)
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            if inp[i][j] == fc:
                g[i][j] = sc
    return g


def no_vertical_leak(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    r0, c0, r1, c1 = box
    g = copy(out)
    for i in range(len(g)):
        for j in range(len(g[0])):
            if not (r0 <= i <= r1):
                g[i][j] = inp[i][j]
    return g


def no_horizontal_leak(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    r0, c0, r1, c1 = box
    g = copy(out)
    for i in range(len(g)):
        for j in range(len(g[0])):
            if not (c0 <= j <= c1):
                g[i][j] = inp[i][j]
    return g


def leak_one_side_only(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    r0, c0, r1, c1 = box
    g = copy(out)
    for i in range(len(g)):
        for j in range(len(g[0])):
            if i > r1 or j > c1:
                g[i][j] = inp[i][j]
    return g


def seed_cross_only(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    h, w = len(inp), len(inp[0])
    g = copy(inp)
    for j in range(w):
        if g[seed[0]][j] != fc:
            g[seed[0]][j] = sc
    for i in range(h):
        if g[i][seed[1]] != fc:
            g[i][seed[1]] = sc
    return g


def full_lines_of_flooded(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    h, w = len(inp), len(inp[0])
    reached = flood(inp, seed, box)
    rows = {i for i, _ in reached}
    cols = {j for _, j in reached}
    g = copy(inp)
    for i in range(h):
        for j in range(w):
            if (i in rows or j in cols) and inp[i][j] != fc:
                g[i][j] = sc
    return g


def unbounded_flood(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    return paint(inp, flood(inp, seed, box, clip=False), sc)


def whole_box_filled(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    r0, c0, r1, c1 = box
    g = copy(inp)
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            g[i][j] = sc
    return g


def crop_to_box(inp, out):
    bg, sc, fc, seed, box = parts(inp)
    r0, c0, r1, c1 = box
    return [list(r[c0:c1 + 1]) for r in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("fill only the flooded interior of the frame's bounding box; no leak out of the box", box_flood_only),
    ("flood treats diagonal frame gaps as open (8-connected) and does not leak", diag_flood_only),
    ("fill uses the frame color instead of the lone cell's color", wrong_fill_color),
    ("fill also overwrites frame cells inside the bounding box", overwrite_frame),
    ("fill leaks only horizontally, never above or below the box rows", no_vertical_leak),
    ("fill leaks only vertically, never left or right of the box columns", no_horizontal_leak),
    ("fill leaks only up and left, not down or right", leak_one_side_only),
    ("only the lone cell's own row and column are painted", seed_cross_only),
    ("every row and column through a flooded cell is painted in full", full_lines_of_flooded),
    ("flood is not clipped to the bounding box and spreads over the whole grid", unbounded_flood),
    ("whole bounding box rectangle is painted, frame included", whole_box_filled),
    ("output is cropped to the frame's bounding box", crop_to_box),
]


def valid(g, true):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != true


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/78e78cff.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
