from pathlib import Path
import json
from collections import deque

N4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
N8 = N4 + [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def comps(inp, nb):
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0 and (r, c) not in seen:
                seen.add((r, c))
                q = deque([(r, c)])
                cells = []
                while q:
                    a, b = q.popleft()
                    cells.append((a, b))
                    for da, db in nb:
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and inp[x][y] != 0 and (x, y) not in seen:
                            seen.add((x, y))
                            q.append((x, y))
                res.append(cells)
    return res


def holes(inp, esc_nb, cells):
    """Count bg regions (4-connected) not escaping to the border when only `cells` is solid."""
    h, w = len(inp), len(inp[0])
    solid = set(cells)
    seen = set()
    out = []
    for r in range(h):
        for c in range(w):
            if (r, c) in solid or (r, c) in seen:
                continue
            seen.add((r, c))
            q = deque([(r, c)])
            reg = []
            border = False
            while q:
                a, b = q.popleft()
                reg.append((a, b))
                if a in (0, h - 1) or b in (0, w - 1):
                    border = True
                for da, db in esc_nb:
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and (x, y) not in solid and (x, y) not in seen:
                        seen.add((x, y))
                        q.append((x, y))
            if not border:
                out.append(reg)
    return out


def true_count(inp, out, cells):
    r, c = cells[0]
    return out[r][c]


def recolor(inp, out, f, only=None):
    g = [row[:] for row in inp]
    for cells in comps(inp, N8):
        col = f(cells)
        if col is None:
            continue
        for r, c in cells:
            g[r][c] = col
    return g


def off_by_one_plus(inp, out):
    return recolor(inp, out, lambda cs: min(9, true_count(inp, out, cs) + 1))


def off_by_one_minus(inp, out):
    return recolor(inp, out, lambda cs: true_count(inp, out, cs) - 1)


def fill_holes_too(inp, out):
    g = [row[:] for row in out]
    for cells in comps(inp, N8):
        col = true_count(inp, out, cells)
        for reg in holes(inp, N4, cells):
            for r, c in reg:
                g[r][c] = col
    return g


def only_largest(inp, out):
    cs = comps(inp, N8)
    big = max(cs, key=len)
    g = [row[:] for row in inp]
    for r, c in big:
        g[r][c] = out[r][c]
    return g


def skip_single_hole(inp, out):
    g = [row[:] for row in out]
    for cells in comps(inp, N8):
        if true_count(inp, out, cells) == 1:
            for r, c in cells:
                g[r][c] = inp[r][c]
    return g


def by_size_rank(inp, out):
    cs = sorted(comps(inp, N8), key=len)
    g = [row[:] for row in inp]
    for i, cells in enumerate(cs):
        for r, c in cells:
            g[r][c] = min(9, i + 1)
    return g


def reading_order_index(inp, out):
    cs = sorted(comps(inp, N8), key=lambda cs: min(cs))
    g = [row[:] for row in inp]
    for i, cells in enumerate(cs):
        for r, c in cells:
            g[r][c] = min(9, i + 1)
    return g


def reversed_mapping(inp, out):
    cs = comps(inp, N8)
    cnt = [true_count(inp, out, c) for c in cs]
    m = max(cnt) + 1
    g = [row[:] for row in inp]
    for cells, n in zip(cs, cnt):
        for r, c in cells:
            g[r][c] = m - n
    return g


def hole_area(inp, out):
    def f(cells):
        a = sum(len(reg) for reg in holes(inp, N4, cells))
        return min(9, a)
    return recolor(inp, out, f)


def total_holes(inp, out):
    t = sum(true_count(inp, out, c) for c in comps(inp, N8))
    return recolor(inp, out, lambda cs: min(9, t))


def top_row_only(inp, out):
    g = [row[:] for row in inp]
    for cells in comps(inp, N8):
        top = min(r for r, _ in cells)
        for r, c in cells:
            if r == top:
                g[r][c] = out[r][c]
    return g


def split_4conn_objects(inp, out):
    # objects taken as 4-connected, each counted by its own hole count under 8-connected escape
    g = [row[:] for row in inp]
    for cells in comps(inp, N4):
        n = len(holes(inp, N8, cells))
        for r, c in cells:
            g[r][c] = n if n else inp[r][c]
    return g


def bbox_fill(inp, out):
    g = [row[:] for row in out]
    for cells in comps(inp, N8):
        col = true_count(inp, out, cells)
        r0 = min(r for r, _ in cells); r1 = max(r for r, _ in cells)
        c0 = min(c for _, c in cells); c1 = max(c for _, c in cells)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if g[r][c] == 0:
                    g[r][c] = col
    return g


ALTERNATIVES = [
    ("hole count off by one high: each shape gets color count+1", off_by_one_plus),
    ("hole count off by one low: each shape gets color count-1", off_by_one_minus),
    ("holes also painted with the shape's color", fill_holes_too),
    ("only the largest shape is recolored", only_largest),
    ("shapes with a single hole are left unrecolored", skip_single_hole),
    ("color by size rank of the shape instead of hole count", by_size_rank),
    ("color by reading-order index of the shape", reading_order_index),
    ("color reversed: max count + 1 minus count", reversed_mapping),
    ("color is the total hole area, not the hole count", hole_area),
    ("every shape gets the grid-wide total hole count", total_holes),
    ("only the top row of each shape is recolored", top_row_only),
    ("whole bounding box of each shape is filled with its color", bbox_fill),
]


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/0a2355a6.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        ok = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  ERR", desc, e)
                g = None
            if g is None:
                continue
            if (g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                    and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                    and g != p["output"]):
                ok += 1
        print(ok, desc)
