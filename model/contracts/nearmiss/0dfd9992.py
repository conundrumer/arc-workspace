from pathlib import Path
import json
from collections import Counter

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/0dfd9992.json')


def holes(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 0]


def copy(g):
    return [list(r) for r in g]


def mode_color(inp):
    cnt = Counter(v for row in inp for v in row if v != 0)
    return cnt.most_common(1)[0][0]


def global_mode(inp, out):
    g = copy(inp)
    m = mode_color(inp)
    for r, c in holes(inp):
        g[r][c] = m
    return g


def row_mode(inp, out):
    g = copy(inp)
    for r, c in holes(inp):
        cnt = Counter(v for v in inp[r] if v != 0)
        g[r][c] = cnt.most_common(1)[0][0]
    return g


def col_mode(inp, out):
    g = copy(inp)
    for r, c in holes(inp):
        cnt = Counter(inp[i][c] for i in range(len(inp)) if inp[i][c] != 0)
        g[r][c] = cnt.most_common(1)[0][0]
    return g


def copy_from_left(inp, out):
    g = copy(inp)
    for r, c in holes(inp):
        k = c
        while k >= 0 and inp[r][k] == 0:
            k -= 1
        g[r][c] = inp[r][k] if k >= 0 else out[r][c]
    return g


def copy_from_above(inp, out):
    g = copy(inp)
    for r, c in holes(inp):
        k = r
        while k >= 0 and inp[k][c] == 0:
            k -= 1
        g[r][c] = inp[k][c] if k >= 0 else out[r][c]
    return g


def shifted_by_one(inp, out):
    g = copy(inp)
    w = len(inp[0])
    for r, c in holes(inp):
        g[r][c] = out[r][(c + 1) % w]
    return g


def mirror_lr_only(inp, out):
    g = copy(inp)
    w = len(inp[0])
    for r, c in holes(inp):
        g[r][c] = out[r][w - 1 - c]
    return g


def shifted_down_one(inp, out):
    g = copy(inp)
    for r, c in holes(inp):
        g[r][c] = out[(r + 1) % len(inp)][c]
    return g


def top_half_only(inp, out):
    g = copy(out)
    h = len(inp)
    for r, c in holes(inp):
        if r < h // 2:
            g[r][c] = 0
    return g


def bbox_overwrite(inp, out):
    hs = holes(inp)
    r0 = min(r for r, c in hs); r1 = max(r for r, c in hs)
    c0 = min(c for r, c in hs); c1 = max(c for r, c in hs)
    m = mode_color(inp)
    g = copy(out)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            g[r][c] = m
    return g


def crop_hole_bbox(inp, out):
    hs = holes(inp)
    r0 = min(r for r, c in hs); r1 = max(r for r, c in hs)
    c0 = min(c for r, c in hs); c1 = max(c for r, c in hs)
    return [out[r][c0:c1 + 1] for r in range(r0, r1 + 1)]


def first_component_unfilled(inp, out):
    hs = set(holes(inp))
    start = min(hs)
    comp = {start}
    stack = [start]
    while stack:
        r, c = stack.pop()
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (r + d[0], c + d[1])
            if n in hs and n not in comp:
                comp.add(n)
                stack.append(n)
    g = copy(out)
    for r, c in comp:
        g[r][c] = 0
    return g


ALTERNATIVES = [
    ("fill every hole cell with the most common color of the whole grid", global_mode),
    ("fill each hole cell with the most common color of its row", row_mode),
    ("fill each hole cell with the most common color of its column", col_mode),
    ("fill each hole cell by copying the nearest intact cell to its left", copy_from_left),
    ("fill each hole cell by copying the nearest intact cell above it", copy_from_above),
    ("fill each hole cell from the pattern shifted one column (off-by-one period offset)", shifted_by_one),
    ("fill each hole cell from its left-right mirror position in the grid only", mirror_lr_only),
    ("fill each hole cell from the pattern shifted one row (off-by-one vertical offset)", shifted_down_one),
    ("repair only holes in the top half of the grid", top_half_only),
    ("overwrite the whole bounding box of the holes with the most common color", bbox_overwrite),
    ("output only the repaired crop of the holes' bounding box", crop_hole_bbox),
    ("leave the first connected hole region unrepaired", first_component_unfilled),
]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    train = json.load(open(TASK))["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            n += valid(g, p["output"])
        print(n, "/", len(train), desc)
