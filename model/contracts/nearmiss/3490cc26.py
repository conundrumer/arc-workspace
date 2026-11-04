from pathlib import Path
import json, sys

def cp(g):
    return [r[:] for r in g]

def blocks(inp):
    """2x2 blocks as (r, c, color) with top-left corner."""
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] and (r, c) not in seen:
                col = inp[r][c]
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                res.append((min(y for y, _ in cells), min(x for _, x in cells), col))
    return res

def comps(out, color):
    """Connected components of cells with the given color."""
    h, w = len(out), len(out[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if out[r][c] == color and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and out[ny][nx] == color and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                res.append(cells)
    return res

def link_color(inp, out):
    h, w = len(inp), len(inp[0])
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 and out[r][c] != 0:
                return out[r][c]
    return 7

def seed_color(inp):
    cnt = {}
    for _, _, col in blocks(inp):
        cnt[col] = cnt.get(col, 0) + 1
    return min(cnt, key=lambda k: cnt[k])

def touches(cells, color, out):
    h, w = len(out), len(out[0])
    for y, x in cells:
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and out[ny][nx] == color:
                return True
    return False

def fill_gaps(inp, pairs, color):
    g = cp(inp)
    for (r1, c1), (r2, c2) in pairs:
        if r1 == r2:
            for r in (r1, r1 + 1):
                for c in range(c1 + 2, c2):
                    g[r][c] = color
        else:
            for c in (c1, c1 + 1):
                for r in range(r1 + 2, r2):
                    g[r][c] = color
    return g

# 1. links drawn in the block color instead of the link color
def a_block_color(inp, out):
    lc = link_color(inp, out)
    bc = max(set(v for r in inp for v in r if v), key=lambda v: sum(r.count(v) for r in inp))
    return [[bc if v == lc else v for v in r] for r in out]

# 2. links drawn in the seed color
def a_seed_color(inp, out):
    lc = link_color(inp, out)
    sc = seed_color(inp)
    return [[sc if v == lc else v for v in r] for r in out]

# 3. every pair of neighbouring aligned blocks is linked
def a_all_pairs(inp, out):
    bl = blocks(inp)
    lc = link_color(inp, out)
    pairs = []
    for a in bl:
        for b in bl:
            if a[0] == b[0] and a[1] < b[1]:
                if not any(c[0] == a[0] and a[1] < c[1] < b[1] for c in bl):
                    pairs.append(((a[0], a[1]), (b[0], b[1])))
            if a[1] == b[1] and a[0] < b[0]:
                if not any(c[1] == a[1] and a[0] < c[0] < b[0] for c in bl):
                    pairs.append(((a[0], a[1]), (b[0], b[1])))
    return fill_gaps(inp, pairs, lc)

# 4. the link next to the seed is left out
def a_skip_first(inp, out):
    lc = link_color(inp, out)
    sc = seed_color(inp)
    g = cp(out)
    seedcells = [(y, x) for y in range(len(inp)) for x in range(len(inp[0])) if inp[y][x] == sc]
    for cells in comps(out, lc):
        if any(touches([s], lc, out) for s in seedcells) and any(
                abs(y - sy) + abs(x - sx) == 1 for y, x in cells for sy, sx in seedcells):
            for y, x in cells:
                g[y][x] = 0
    return g

# 5. links are one cell wide
def a_thin(inp, out):
    lc = link_color(inp, out)
    g = cp(out)
    for cells in comps(out, lc):
        ys = [y for y, _ in cells]
        xs = [x for _, x in cells]
        horiz = (max(xs) - min(xs)) >= (max(ys) - min(ys))
        for y, x in cells:
            if horiz and y != min(ys):
                g[y][x] = 0
            if not horiz and x != min(xs):
                g[y][x] = 0
    return g

# 6. links paint over the blocks they join (two cells at each end)
def a_overwrite(inp, out):
    lc = link_color(inp, out)
    g = cp(out)
    h, w = len(out), len(out[0])
    for cells in comps(out, lc):
        ys = [y for y, _ in cells]
        xs = [x for _, x in cells]
        horiz = (max(xs) - min(xs)) >= (max(ys) - min(ys))
        for y, x in cells:
            for d in (-2, -1, 1, 2):
                ny, nx = (y, x + d) if horiz else (y + d, x)
                if 0 <= ny < h and 0 <= nx < w and inp[ny][nx]:
                    g[ny][nx] = lc
    return g

# 7. only the first link is drawn
def a_first_only(inp, out):
    lc = link_color(inp, out)
    sc = seed_color(inp)
    cs = comps(out, lc)
    if len(cs) < 2:
        return None
    seedcells = [(y, x) for y in range(len(inp)) for x in range(len(inp[0])) if inp[y][x] == sc]
    keep = [c for c in cs if any(abs(y - sy) + abs(x - sx) == 1 for y, x in c for sy, sx in seedcells)]
    g = cp(out)
    for cells in cs:
        if cells not in keep:
            for y, x in cells:
                g[y][x] = 0
    return g

# 8. output cropped to the bounding box of the non-zero cells
def a_crop(inp, out):
    pts = [(y, x) for y, r in enumerate(out) for x, v in enumerate(r) if v]
    y0 = min(y for y, _ in pts); y1 = max(y for y, _ in pts)
    x0 = min(x for _, x in pts); x1 = max(x for _, x in pts)
    return [r[x0:x1 + 1] for r in out[y0:y1 + 1]]

# 9. the seed block is recolored like the links
def a_seed_recolor(inp, out):
    lc = link_color(inp, out)
    sc = seed_color(inp)
    return [[lc if v == sc else v for v in r] for r in out]

# 10. seed links to its nearest block in every direction (a star, no chain)
def a_star(inp, out):
    bl = blocks(inp)
    lc = link_color(inp, out)
    sc = seed_color(inp)
    seed = [b for b in bl if b[2] == sc][0]
    pairs = []
    for b in bl:
        if b is seed:
            continue
        if b[0] == seed[0]:
            lo, hi = sorted((seed, b), key=lambda t: t[1])
            if not any(c[0] == seed[0] and lo[1] < c[1] < hi[1] for c in bl):
                pairs.append(((lo[0], lo[1]), (hi[0], hi[1])))
        if b[1] == seed[1]:
            lo, hi = sorted((seed, b), key=lambda t: t[0])
            if not any(c[1] == seed[1] and lo[0] < c[0] < hi[0] for c in bl):
                pairs.append(((lo[0], lo[1]), (hi[0], hi[1])))
    return fill_gaps(inp, pairs, lc)

# 11. only the longest link is drawn
def a_longest(inp, out):
    lc = link_color(inp, out)
    cs = comps(out, lc)
    if len(cs) < 2:
        return None
    best = max(cs, key=len)
    g = cp(out)
    for cells in cs:
        if cells is not best:
            for y, x in cells:
                g[y][x] = 0
    return g

# 12. links one cell too short at the far end
def a_short(inp, out):
    lc = link_color(inp, out)
    g = cp(out)
    for cells in comps(out, lc):
        ys = [y for y, _ in cells]
        xs = [x for _, x in cells]
        horiz = (max(xs) - min(xs)) >= (max(ys) - min(ys))
        for y, x in cells:
            if horiz and x == max(xs):
                g[y][x] = 0
            if not horiz and y == max(ys):
                g[y][x] = 0
    return g

ALTERNATIVES = [
    ("links drawn in the block color", a_block_color),
    ("links drawn in the seed color", a_seed_color),
    ("every pair of aligned neighbouring blocks is linked", a_all_pairs),
    ("the link touching the seed is left out", a_skip_first),
    ("links are one cell wide", a_thin),
    ("links paint over the blocks they join", a_overwrite),
    ("only the link touching the seed is drawn", a_first_only),
    ("output cropped to the non-zero bounding box", a_crop),
    ("seed block recolored to the link color", a_seed_recolor),
    ("seed links to its nearest blocks in each direction, no chain", a_star),
    ("only the longest link is drawn", a_longest),
    ("each link one cell short at its far end", a_short),
]

def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len(set(len(r) for r in g)) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out

if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/3490cc26.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(cp(p["input"]), cp(p["output"]))
            except Exception as e:
                print("  error", desc, repr(e))
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
