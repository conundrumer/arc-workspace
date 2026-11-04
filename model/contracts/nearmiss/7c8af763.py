from pathlib import Path
import json
from collections import Counter

N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
N8 = N4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def regions(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 and (r, c) not in seen:
                comp, st = [], [(r, c)]
                seen.add((r, c))
                while st:
                    y, x = st.pop()
                    comp.append((y, x))
                    for dy, dx in N4:
                        a, b = y + dy, x + dx
                        if 0 <= a < h and 0 <= b < w and inp[a][b] == 0 and (a, b) not in seen:
                            seen.add((a, b))
                            st.append((a, b))
                res.append(sorted(comp))
    return res


def touching(inp, comp, nbrs=N4, cell_ok=None):
    h, w = len(inp), len(inp[0])
    cs = set(comp)
    q = {}
    for y, x in comp:
        for dy, dx in nbrs:
            a, b = y + dy, x + dx
            if 0 <= a < h and 0 <= b < w and (a, b) not in cs and inp[a][b] not in (0, 5):
                if cell_ok is None or cell_ok(a, b, h, w):
                    q[(a, b)] = inp[a][b]
    return q


def render(inp, choose, nbrs=N4, cell_ok=None, only=None):
    g = [row[:] for row in inp]
    regs = regions(inp)
    for i, comp in enumerate(regs):
        if only is not None and i not in only(regs):
            continue
        q = touching(inp, comp, nbrs, cell_ok)
        col = choose(q, inp, comp)
        if col is None:
            continue
        for y, x in comp:
            g[y][x] = col
    return g


def most(q, inp, comp):
    cnt = Counter(q.values())
    return max(cnt, key=lambda k: (cnt[k], -k)) if cnt else None


def least(q, inp, comp):
    cnt = Counter(q.values())
    return min(cnt, key=lambda k: (cnt[k], k)) if cnt else None


def alt_least(inp, out):
    return render(inp, least)


def alt_row_band_global(inp, out):
    # a region votes with every marker in the rows it spans, across the whole grid width
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for comp in regions(inp):
        y0 = min(y for y, _ in comp); y1 = max(y for y, _ in comp)
        cnt = Counter(inp[y][x] for y in range(max(0, y0 - 1), min(h, y1 + 2)) for x in range(w) if inp[y][x] in (1, 2))
        if cnt:
            col = max(cnt, key=lambda k: (cnt[k], -k))
            for y, x in comp:
                g[y][x] = col
    return g


def alt_two_cell_reach(inp, out):
    # a marker counts for a region if it lies within the region's bounding box grown by one cell, diagonals included
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for comp in regions(inp):
        y0 = min(y for y, _ in comp); y1 = max(y for y, _ in comp)
        x0 = min(x for _, x in comp); x1 = max(x for _, x in comp)
        cnt = Counter()
        for y in range(max(0, y0 - 1), min(h, y1 + 2)):
            for x in range(max(0, x0 - 1), min(w, x1 + 2)):
                if inp[y][x] in (1, 2):
                    cnt[inp[y][x]] += 1
        if cnt:
            col = max(cnt, key=lambda k: (cnt[k], -k))
            for y, x in comp:
                g[y][x] = col
    return g


def alt_presence(inp, out):
    def ch(q, inp, comp):
        s = sorted(set(q.values()))
        return s[-1] if s else None
    return render(inp, ch)


def alt_interior(inp, out):
    ok = lambda a, b, h, w: 0 < a < h - 1 and 0 < b < w - 1
    return render(inp, most, cell_ok=ok)


def alt_global(inp, out):
    cnt = Counter(v for row in inp for v in row if v not in (0, 5))
    col = max(cnt, key=lambda k: (cnt[k], -k))
    return render(inp, lambda q, i, c: col)


def alt_first_scan(inp, out):
    def ch(q, inp, comp):
        return inp_first(q)
    def inp_first(q):
        return q[min(q)] if q else None
    return render(inp, ch)


def alt_swap(inp, out):
    g = [row[:] for row in out]
    for comp in regions(inp):
        y, x = comp[0]
        v = out[y][x]
        if v in (1, 2):
            for y, x in comp:
                g[y][x] = 3 - v
    return g


def alt_largest_only(inp, out):
    regs = regions(inp)
    big = max(regs, key=len)
    g = [row[:] for row in out]
    for comp in regs:
        if comp is not big:
            for y, x in comp:
                g[y][x] = 0
    return g


def alt_skip_smallest(inp, out):
    regs = regions(inp)
    small = min(regs, key=len)
    g = [row[:] for row in out]
    for y, x in small:
        g[y][x] = 0
    return g


def alt_crop(inp, out):
    return [row[1:-1] for row in out[1:-1]]


def alt_markers_cleared(inp, out):
    g = [row[:] for row in out]
    for y, row in enumerate(inp):
        for x, v in enumerate(row):
            if v in (1, 2):
                g[y][x] = 5
    return g


def alt_row_band(inp, out):
    # region takes the color of the markers on its own top border row only
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for comp in regions(inp):
        top = min(y for y, _ in comp)
        cols = sorted(set(x for _, x in comp))
        vals = [inp[top - 1][x] for x in cols if top > 0 and inp[top - 1][x] in (1, 2)]
        if not vals:
            continue
        cnt = Counter(vals)
        col = max(cnt, key=lambda k: (cnt[k], -k))
        for y, x in comp:
            g[y][x] = col
    return g


ALTERNATIVES = [
    ("fill each region with its least common touching marker color", alt_least),
    ("a region votes with every marker in the grid rows it spans, not only the touching ones", alt_row_band_global),
    ("pick the highest marker color present at a region instead of the majority", alt_presence),
    ("ignore markers on the outer border rows and columns when voting", alt_interior),
    ("fill every region with the grid-wide most common marker color", alt_global),
    ("fill each region with the first touching marker in scan order", alt_first_scan),
    ("swap colors 1 and 2 in every filled region", alt_swap),
    ("fill only the largest region", alt_largest_only),
    ("leave the smallest region unfilled", alt_skip_smallest),
    ("crop the one-cell outer border off the output", alt_crop),
    ("fill regions correctly but turn marker cells in the lines into 5", alt_markers_cleared),
    ("vote only from markers on the row above each region", alt_row_band),
]


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/7c8af763.json')))
    train = t["train"]
    print("pairs", len(train))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", e)
                g = None
            ok = (g is not None and len(g) > 0 and all(len(r) == len(g[0]) for r in g)
                  and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
                  and g != p["output"])
            n += ok
        print(n, desc)
