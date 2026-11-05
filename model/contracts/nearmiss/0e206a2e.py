import json
from collections import Counter
from pathlib import Path

D4 = [
    lambda r, c: (r, c),
    lambda r, c: (c, -r),
    lambda r, c: (-r, -c),
    lambda r, c: (-c, r),
    lambda r, c: (r, -c),
    lambda r, c: (-r, c),
    lambda r, c: (c, r),
    lambda r, c: (-c, -r),
]
ROT_ONLY = D4[:4]
FLIP_ONLY = [D4[0], D4[4], D4[5], D4[2]]


def bg_of(g):
    return Counter(v for row in g for v in row).most_common(1)[0][0]


def parts(g):
    bg = bg_of(g)
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != bg and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append(cells)
    objs = [c for c in comps if len(c) > 1]
    marks = [c[0] for c in comps if len(c) == 1]
    return bg, objs, marks


def body_colors(g, cells):
    cnt = Counter(g[y][x] for y, x in cells)
    top = max(cnt.values())
    return {k for k, v in cnt.items() if v == top}


def solve(g, dihedral=D4, body=None, color_match=True, need_all=True,
          keep_orig=False, drop_unmatched=False, only_first=False, bodyless=False):
    bg, objs, marks = parts(g)
    h, w = len(g), len(g[0])
    mcol = {p: g[p[0]][p[1]] for p in marks}
    placed = {}
    for cells in objs[:1] if only_first else objs:
        bc = body(g, cells) if body else body_colors(g, cells)
        anchors = [(y, x) for y, x in cells if g[y][x] not in bc]
        if not anchors:
            continue
        for f in dihedral:
            tr = [(f(y, x), g[y][x]) for y, x in cells]
            tanch = [(f(y, x), g[y][x]) for y, x in anchors]
            (a0, c0) = tanch[0]
            for m, mc in mcol.items():
                if color_match and mc != c0:
                    continue
                oy, ox = m[0] - a0[0], m[1] - a0[1]
                hits = [
                    mcol.get((p[0] + oy, p[1] + ox)) == (c if color_match else mcol.get((p[0] + oy, p[1] + ox)))
                    and (p[0] + oy, p[1] + ox) in mcol
                    for p, c in tanch
                ]
                ok = all(hits) if need_all else hits[0]
                if not ok:
                    continue
                for p, c in tr:
                    y, x = p[0] + oy, p[1] + ox
                    if 0 <= y < h and 0 <= x < w and not (bodyless and c in bc):
                        placed[(y, x)] = c
    res = [[bg] * w for _ in range(h)]
    if keep_orig:
        for cells in objs:
            for y, x in cells:
                res[y][x] = g[y][x]
    for p, c in mcol.items():
        if not drop_unmatched or p in placed:
            res[p[0]][p[1]] = c
    for (y, x), c in placed.items():
        res[y][x] = c
    return res


def shift(g, dy, dx, bg):
    h, w = len(g), len(g[0])
    res = [[bg] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            if 0 <= r + dy < h and 0 <= c + dx < w:
                res[r + dy][c + dx] = g[r][c]
    return res


def a_no_flip(inp, out):
    return solve(inp, dihedral=ROT_ONLY)


def a_no_rot(inp, out):
    return solve(inp, dihedral=[D4[0]])


def a_flip_only(inp, out):
    return solve(inp, dihedral=FLIP_ONLY)


def a_keep_orig(inp, out):
    return solve(inp, keep_orig=True)


def a_color_free(inp, out):
    return solve(inp, color_match=False)


def a_one_anchor(inp, out):
    return solve(inp, need_all=False)


def a_transpose(inp, out):
    return [list(r) for r in zip(*out)]


def a_first_only(inp, out):
    return solve(inp, only_first=True)


def a_bodyless(inp, out):
    return solve(inp, bodyless=True)


def a_first_cell_body(inp, out):
    # body color taken as the color of the object's first cell in reading order
    return solve(inp, body=lambda g, cells: {g[min(cells)[0]][min(cells)[1]]})


def a_shift_right(inp, out):
    return shift(out, 0, 1, bg_of(inp))


def a_recolor_body(inp, out):
    bg, objs, marks = parts(inp)
    body = set()
    for cells in objs:
        body |= body_colors(inp, cells)
    other = next(c for c in range(1, 10) if c not in body and all(c not in row for row in inp))
    return [[other if v in body else v for v in row] for row in out]


ALTERNATIVES = [
    ("place objects by rotation only, no mirror poses", a_no_flip),
    ("place objects without turning, translation only", a_no_rot),
    ("place objects by mirror poses only, no quarter turns", a_flip_only),
    ("original objects stay in place beside the placed copies", a_keep_orig),
    ("anchor cells match any marker regardless of color", a_color_free),
    ("a pose needs only the first anchor to land on a marker", a_one_anchor),
    ("output is the transpose of the true output", a_transpose),
    ("only the first object is placed", a_first_only),
    ("placed objects keep only anchor cells, body cells omitted", a_bodyless),
    ("body color taken from the object's first cell in reading order", a_first_cell_body),
    ("whole output shifted one column right", a_shift_right),
    ("body cells of placed objects recolored to an unused color", a_recolor_body),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/0e206a2e.json'))
    train = task["train"]
    print("base solver reproduces:", [solve(p["input"]) == p["output"] for p in train])
    for desc, fn in ALTERNATIVES:
        n = 0
        per = []
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                g = None
                print("  error", desc, e)
            ok = g is not None and valid(g) and g != p["output"]
            per.append(int(ok))
            n += ok
        print(n, per, desc)
