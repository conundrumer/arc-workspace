from pathlib import Path
import json
from collections import Counter

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/00d62c1b.json')
N4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
N8 = N4 + [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def copy(g):
    return [r[:] for r in g]


def bg_of(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def reached(inp, nbrs=N4, edges=("t", "b", "l", "r")):
    """Background cells reached from the chosen grid edges."""
    h, w = len(inp), len(inp[0])
    bg = bg_of(inp)
    seen = set()
    stack = []
    for r in range(h):
        for c in range(w):
            on = (("t" in edges and r == 0) or ("b" in edges and r == h - 1)
                  or ("l" in edges and c == 0) or ("r" in edges and c == w - 1))
            if on and inp[r][c] == bg:
                seen.add((r, c))
                stack.append((r, c))
    while stack:
        r, c = stack.pop()
        for dr, dc in nbrs:
            q = (r + dr, c + dc)
            if 0 <= q[0] < h and 0 <= q[1] < w and q not in seen and inp[q[0]][q[1]] == bg:
                seen.add(q)
                stack.append(q)
    return seen


def enclosed(inp, **kw):
    bg = bg_of(inp)
    rs = reached(inp, **kw)
    return {(r, c) for r in range(len(inp)) for c in range(len(inp[0]))
            if inp[r][c] == bg and (r, c) not in rs}


def fill_color(inp, out):
    bg = bg_of(inp)
    cols = {out[r][c] for r in range(len(out)) for c in range(len(out[0])) if out[r][c] != inp[r][c]}
    return cols.pop() if cols else 4


def regions(cells):
    cells = set(cells)
    res = []
    while cells:
        s = cells.pop()
        comp = {s}
        st = [s]
        while st:
            r, c = st.pop()
            for dr, dc in N4:
                q = (r + dr, c + dc)
                if q in cells:
                    cells.remove(q)
                    comp.add(q)
                    st.append(q)
        res.append(comp)
    return res


def paint(inp, cells, color):
    g = copy(inp)
    for r, c in cells:
        g[r][c] = color
    return g


def diag_leak(inp, out):
    return paint(inp, enclosed(inp, nbrs=N8), fill_color(inp, out))


def wrong_color(inp, out):
    f = fill_color(inp, out)
    g = copy(out)
    for r in range(len(g)):
        for c in range(len(g[0])):
            if out[r][c] == f and inp[r][c] != f:
                g[r][c] = 8 if f != 8 else 2
    return g


def fill_all_bg(inp, out):
    bg = bg_of(inp)
    f = fill_color(inp, out)
    return [[f if v == bg else v for v in r] for r in inp]


def largest_only(inp, out):
    regs = regions(enclosed(inp))
    if not regs:
        return None
    big = max(regs, key=len)
    return paint(inp, big, fill_color(inp, out))


def smallest_only(inp, out):
    regs = regions(enclosed(inp))
    if not regs:
        return None
    small = min(regs, key=len)
    return paint(inp, small, fill_color(inp, out))


def recolor_wall(inp, out):
    bg = bg_of(inp)
    f = fill_color(inp, out)
    return [[f if v != bg else v for v in r] for r in inp]


def multi_cell_only(inp, out):
    cells = set()
    for reg in regions(enclosed(inp)):
        if len(reg) > 1:
            cells |= reg
    return paint(inp, cells, fill_color(inp, out))


def bbox_fill(inp, out):
    bg = bg_of(inp)
    pts = [(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] != bg]
    r0, r1 = min(p[0] for p in pts), max(p[0] for p in pts)
    c0, c1 = min(p[1] for p in pts), max(p[1] for p in pts)
    cells = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if inp[r][c] == bg}
    return paint(inp, cells, fill_color(inp, out))


def top_left_sources(inp, out):
    bg = bg_of(inp)
    rs = reached(inp, edges=("t", "l"))
    cells = {(r, c) for r in range(len(inp)) for c in range(len(inp[0]))
             if inp[r][c] == bg and (r, c) not in rs}
    return paint(inp, cells, fill_color(inp, out))


def drop_last_region(inp, out):
    regs = regions(enclosed(inp))
    if len(regs) < 2:
        return None
    last = max(regs, key=lambda s: max(s))
    g = copy(out)
    for r, c in last:
        g[r][c] = bg_of(inp)
    return g


def row_gaps_only(inp, out):
    bg = bg_of(inp)
    cells = set()
    for r, c in enclosed(inp):
        left = any(inp[r][k] != bg for k in range(c))
        right = any(inp[r][k] != bg for k in range(c + 1, len(inp[0])))
        if left and right:
            cells.add((r, c))
    # wrong: fill only cells whose row has a wall on both sides and exactly one bg run inside
    cells = {(r, c) for r, c in cells
             if inp[r][c - 1] != bg and inp[r][c + 1] != bg} if cells else cells
    return paint(inp, cells, fill_color(inp, out))


def shift_fill_down(inp, out):
    f = fill_color(inp, out)
    cells = {(r + 1, c) for r, c in enclosed(inp) if r + 1 < len(inp)}
    bg = bg_of(inp)
    cells = {(r, c) for r, c in cells if inp[r][c] == bg}
    return paint(inp, cells, f)


ALTERNATIVES = [
    ("flood from the border through diagonal steps, so diagonal gaps leak and fewer cells fill", diag_leak),
    ("fill enclosed cells with the wrong color (8 instead of the true fill)", wrong_color),
    ("fill every background cell, including those outside the shapes", fill_all_bg),
    ("fill only the largest enclosed region", largest_only),
    ("fill only the smallest enclosed region", smallest_only),
    ("recolor the wall cells with the fill color and leave the interior unfilled", recolor_wall),
    ("fill only enclosed regions of more than one cell", multi_cell_only),
    ("fill every background cell inside the bounding box of the shapes", bbox_fill),
    ("seed the outside flood only from the top and left edges", top_left_sources),
    ("fill all enclosed regions except the lowest-rightmost one", drop_last_region),
    ("fill only enclosed cells with a wall directly left and right on the same row", row_gaps_only),
    ("fill is shifted one row down from the true enclosed cells", shift_fill_down),
]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    train = json.load(open(TASK))["train"]
    print("pairs:", len(train))
    for name, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error:", name, repr(e))
                g = None
            n += valid(g, p["output"])
        print(n, "-", name)
