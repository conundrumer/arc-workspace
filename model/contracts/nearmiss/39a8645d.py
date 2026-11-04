from pathlib import Path
import json
from collections import Counter

def bgcolor(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]

def components(g, conn=8, by_color=True):
    bg = bgcolor(g)
    H, W = len(g), len(g[0])
    if conn == 8:
        nb = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
    else:
        nb = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    seen = set()
    comps = []
    for r in range(H):
        for c in range(W):
            if g[r][c] == bg or (r, c) in seen:
                continue
            col = g[r][c]
            st = [(r, c)]
            seen.add((r, c))
            cells = []
            while st:
                y, x = st.pop()
                cells.append((y, x))
                for dy, dx in nb:
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < H and 0 <= xx < W and (yy, xx) not in seen and g[yy][xx] != bg \
                            and (not by_color or g[yy][xx] == col):
                        seen.add((yy, xx))
                        st.append((yy, xx))
            comps.append((col, sorted(cells)))
    return comps

def bbox(cells):
    ys = [y for y, _ in cells]; xs = [x for _, x in cells]
    return min(ys), min(xs), max(ys), max(xs)

def shape_of(cells):
    r0, c0, _, _ = bbox(cells)
    return frozenset((y - r0, x - c0) for y, x in cells)

def crop(g, box, pad=0):
    r0, c0, r1, c1 = box
    bg = bgcolor(g)
    H, W = len(g), len(g[0])
    return [[g[y][x] if 0 <= y < H and 0 <= x < W else bg
             for x in range(c0 - pad, c1 + pad + 1)] for y in range(r0 - pad, r1 + pad + 1)]

def pick(g, conn=8, by_color=True, mode='most', same_color_copies=False):
    comps = components(g, conn, by_color)
    shapes = [shape_of(c) for _, c in comps]
    def copies(i):
        n = 0
        for j in range(len(comps)):
            if shapes[j] == shapes[i] and (not same_color_copies or comps[j][0] == comps[i][0]):
                n += 1
        return n
    cnt = [copies(i) for i in range(len(comps))]
    if mode == 'most':
        k = max(cnt)
        return next(i for i in range(len(comps)) if cnt[i] == k), comps
    if mode == 'least':
        k = min(cnt)
        return next(i for i in range(len(comps)) if cnt[i] == k), comps
    if mode == 'first':
        return 0, comps
    if mode == 'last':
        return len(comps) - 1, comps
    if mode == 'largest':
        return max(range(len(comps)), key=lambda i: len(comps[i][1])), comps
    if mode == 'smallest':
        return min(range(len(comps)), key=lambda i: len(comps[i][1])), comps

def solve(inp, **kw):
    i, comps = pick(inp, **kw)
    return crop(inp, bbox(comps[i][1]))

def correct(inp, out):
    return solve(inp)

def least_copies(inp, out):
    return solve(inp, mode='least')

def first_piece(inp, out):
    return solve(inp, mode='first')

def largest_piece(inp, out):
    return solve(inp, mode='largest')

def four_conn(inp, out):
    return solve(inp, conn=4)

def four_conn_largest(inp, out):
    return solve(inp, conn=4, mode='largest')

def margin(inp, out):
    i, comps = pick(inp)
    return crop(inp, bbox(comps[i][1]), pad=1)

def solid_fill(inp, out):
    i, comps = pick(inp)
    col = comps[i][0]
    return [[col] * len(out[0]) for _ in out]

def inverted(inp, out):
    bg = bgcolor(inp)
    col = next(v for r in out for v in r if v != bg)
    return [[col if v == bg else bg for v in r] for r in out]

def recolor_other(inp, out):
    bg = bgcolor(inp)
    col = next(v for r in out for v in r if v != bg)
    others = sorted({v for r in inp for v in r if v not in (bg, col)})
    if not others:
        return None
    o = others[0]
    return [[o if v == col else v for v in r] for r in out]

def flip_h(inp, out):
    return [r[::-1] for r in out]

def same_color_copies(inp, out):
    # copies must match in color as well as shape; pick the color-group with most copies
    comps = components(inp)
    key = [(c, shape_of(cells)) for c, cells in comps]
    cnt = Counter(key)
    k = max(cnt.values())
    i = next(i for i in range(len(comps)) if cnt[key[i]] == k)
    return crop(inp, bbox(comps[i][1]))

def merge_colors(inp, out):
    # ignore color when forming pieces: any non-background neighbors join
    return solve(inp, by_color=False, mode='most')

def second_most(inp, out):
    comps = components(inp)
    shapes = [shape_of(c) for _, c in comps]
    cnt = Counter(shapes)
    ranked = sorted(cnt, key=lambda s: -cnt[s])
    if len(ranked) < 2:
        return None
    s = ranked[1]
    i = next(i for i in range(len(comps)) if shapes[i] == s)
    return crop(inp, bbox(comps[i][1]))

ALTERNATIVES = [
    ("pick the piece with the fewest copies instead of the most", least_copies),
    ("pick the first piece in reading order", first_piece),
    ("pick the piece with the most cells", largest_piece),
    ("pieces use 4-connectivity, then pick the piece with the most copies", four_conn),
    ("pieces use 4-connectivity, then pick the largest piece", four_conn_largest),
    ("crop one cell wider than the bounding box on every side", margin),
    ("fill the whole bounding box with the piece color", solid_fill),
    ("swap the piece cells and the background cells inside the crop", inverted),
    ("recolor the output piece with a different piece color from the input", recolor_other),
    ("mirror the crop left to right", flip_h),
    ("copies must match in color as well as shape", same_color_copies),
    ("pieces join across colors when touching, then most copies", merge_colors),
    ("pick the second most common shape", second_most),
]

def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))

if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/39a8645d.json')))
    train = t["train"]
    assert all(correct(p["input"], p["output"]) == p["output"] for p in train), "solver mismatch"
    print("task 39a8645d, readings", len(ALTERNATIVES), "pairs", len(train))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                g = None
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, "|", desc)
