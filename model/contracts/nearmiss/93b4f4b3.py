from pathlib import Path
import json
from collections import Counter

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/93b4f4b3.json')


def panel_color(out):
    return Counter(c for r in out for c in r).most_common(1)[0][0]


def holes(out):
    """4-connected components of non-panel cells in out, as lists of (r, c)."""
    pc = panel_color(out)
    h, w = len(out), len(out[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if out[r][c] != pc and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                comp = []
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and out[ny][nx] != pc \
                                and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                comps.append(sorted(comp))
    comps.sort(key=lambda cp: cp[0])
    return comps


def copy(g):
    return [row[:] for row in g]


def cyclic_swap(inp, out):
    g = copy(out)
    hs = holes(out)
    cols = [out[c[0][0]][c[0][1]] for c in hs]
    if len(set(cols)) < 2:
        return None
    for i, comp in enumerate(hs):
        for y, x in comp:
            g[y][x] = cols[(i + 1) % len(cols)]
    return g


def unfilled(inp, out):
    pc = panel_color(out)
    bg = Counter(c for r in inp for c in r).most_common(1)[0][0] if False else 0
    return [[c if c == pc else bg for c in row] for row in out]


def single_color(inp, out):
    g = copy(out)
    hs = holes(out)
    cnt = Counter(out[y][x] for comp in hs for y, x in comp)
    col = cnt.most_common(1)[0][0]
    for comp in hs:
        for y, x in comp:
            g[y][x] = col
    return g


def only_first_hole(inp, out):
    g = copy(out)
    hs = holes(out)
    for comp in hs[1:]:
        for y, x in comp:
            g[y][x] = panel_color(out)
    return g


def vflip_shapes(inp, out):
    g = copy(out)
    for comp in holes(out):
        r0 = min(y for y, _ in comp)
        r1 = max(y for y, _ in comp)
        cells = {(y, x): out[y][x] for y, x in comp}
        pc = panel_color(out)
        # blank hole bbox rows, then redraw flipped
        for y, x in comp:
            g[y][x] = pc
        for (y, x), v in cells.items():
            g[r0 + r1 - y][x] = v
    return g if g != out else None


def interior_only(inp, out):
    if len(out) < 3 or len(out[0]) < 3:
        return None
    return [row[1:-1] for row in out[1:-1]]


def right_side_crop(inp, out):
    w = len(out[0])
    return [row[w:] for row in inp]


def order_assign(inp, out):
    w = len(out[0])
    right = [row[w:] for row in inp]
    first = {}
    for r, row in enumerate(right):
        for c in row:
            if c != 0 and c not in first:
                first[c] = r
    order = sorted(first, key=lambda c: first[c])
    hs = holes(out)
    if len(order) != len(hs):
        return None
    g = copy(out)
    for col, comp in zip(order, hs):
        for y, x in comp:
            g[y][x] = col
    return g


def panel_to_zero(inp, out):
    pc = panel_color(out)
    return [[0 if c == pc else c for c in row] for row in out]


def pad_extra_column(inp, out):
    return [row + [0] for row in out]


def hfill_rows(inp, out):
    """Fill each hole's whole bounding box, not just the shape cells."""
    g = copy(out)
    for comp in holes(out):
        col = out[comp[0][0]][comp[0][1]]
        r0, r1 = min(y for y, _ in comp), max(y for y, _ in comp)
        c0, c1 = min(x for _, x in comp), max(x for _, x in comp)
        for y in range(r0, r1 + 1):
            for x in range(c0, c1 + 1):
                g[y][x] = col
    return g


def unchanged(inp, out):
    return copy(inp)


ALTERNATIVES = [
    ("fill each hole with the color of the next hole's shape (cyclic mismatch)", cyclic_swap),
    ("leave all holes unfilled (background)", unfilled),
    ("fill every hole with the single most common shape color", single_color),
    ("fill only the topmost hole, leave the rest panel color", only_first_hole),
    ("fill holes with vertically flipped shapes", vflip_shapes),
    ("crop only the panel interior, dropping the border", interior_only),
    ("output the shapes region instead of the panel region", right_side_crop),
    ("assign shape colors to holes by top-to-bottom order of shapes", order_assign),
    ("panel color replaced by background", panel_to_zero),
    ("crop one column too wide", pad_extra_column),
    ("fill the whole bounding box of each hole", hfill_rows),
    ("return the input unchanged", unchanged),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not isinstance(g[0], list):
        return False
    w = len(g[0])
    if w == 0:
        return False
    for row in g:
        if not isinstance(row, list) or len(row) != w:
            return False
        for v in row:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == "__main__":
    train = json.load(open(TASK))["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error:", desc, repr(e))
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
