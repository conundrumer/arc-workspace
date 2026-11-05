import json
from pathlib import Path

BG = 9
INK = 1
NEW = 8

N4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
N8 = N4 + [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def components(inp, steps):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == INK and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                comp = []
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy, dx in steps:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == INK and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                comps.append(comp)
    return comps


def holes(inp, shape, escape):
    """Cells outside `shape` that cannot reach the frame edge by `escape` steps."""
    h, w = len(inp), len(inp[0])
    wall = set(shape)
    reached = set()
    stack = []
    for r in range(h):
        for c in range(w):
            if (r in (0, h - 1) or c in (0, w - 1)) and (r, c) not in wall:
                reached.add((r, c))
                stack.append((r, c))
    while stack:
        y, x = stack.pop()
        for dy, dx in escape:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in wall and (ny, nx) not in reached:
                reached.add((ny, nx))
                stack.append((ny, nx))
    return [(r, c) for r in range(h) for c in range(w) if (r, c) not in wall and (r, c) not in reached]


def paint(inp, cells, color=NEW):
    g = [row[:] for row in inp]
    for r, c in cells:
        g[r][c] = color
    return g


def closed_shapes(inp, conn=N4, escape=N4):
    res = []
    for s in components(inp, conn):
        hs = holes(inp, s, escape)
        if hs:
            res.append((s, hs))
    return res


def other_color(inp, out):
    return [[2 if v == NEW else v for v in row] for row in out]


def fill_holes_only(inp, out):
    cells = [p for s, hs in closed_shapes(inp) for p in hs if inp[p[0]][p[1]] == BG]
    return paint(inp, cells)


def all_shapes(inp, out):
    return [[NEW if v == INK else v for v in row] for row in inp]


def largest_only(inp, out):
    cs = closed_shapes(inp)
    if not cs:
        return None
    s = max((s for s, _ in cs), key=len)
    return paint(inp, s)


def not_on_edge(inp, out):
    h, w = len(inp), len(inp[0])
    cells = [p for s, _ in closed_shapes(inp)
             if not any(r in (0, h - 1) or c in (0, w - 1) for r, c in s) for p in s]
    return paint(inp, cells)


def single_cell_hole(inp, out):
    cells = [p for s, hs in closed_shapes(inp) if len(hs) == 1 for p in s]
    return paint(inp, cells)


def ray_enclosed(inp, out):
    h, w = len(inp), len(inp[0])
    cells = []
    for s in components(inp, N4):
        ss = set(s)
        found = False
        for r in range(h):
            for c in range(w):
                if (r, c) in ss or inp[r][c] != BG:
                    continue
                ok = True
                for dy, dx in N4:
                    y, x = r + dy, c + dx
                    while 0 <= y < h and 0 <= x < w and (y, x) not in ss:
                        y += dy
                        x += dx
                    if not (0 <= y < h and 0 <= x < w):
                        ok = False
                        break
                if ok:
                    found = True
        if found:
            cells.extend(s)
    return paint(inp, cells)


def fill_shape_and_hole(inp, out):
    cells = [p for s, hs in closed_shapes(inp) for p in hs if inp[p[0]][p[1]] == BG]
    return paint(out, cells)


def big_holes_only(inp, out):
    cells = [p for s, hs in closed_shapes(inp) if len(hs) >= 3 for p in s]
    return paint(inp, cells)


def crop_to_recolored(inp, out):
    pts = [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v != inp[r][c]]
    if not pts:
        return None
    r0 = min(r for r, c in pts)
    r1 = max(r for r, c in pts)
    c0 = min(c for r, c in pts)
    c1 = max(c for r, c in pts)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def inverted(inp, out):
    return [[(NEW if (iv == INK and ov == INK) else (INK if ov == NEW else iv))
             for iv, ov in zip(ir, orow)] for ir, orow in zip(inp, out)]


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("closed shapes recolored to 2 instead of 8", other_color),
    ("only the enclosed background cells are filled with 8, shape cells stay 1", fill_holes_only),
    ("every shape is recolored, whether or not it closes off a region", all_shapes),
    ("only the largest closed shape is recolored", largest_only),
    ("a shape touching the frame edge is never recolored", not_on_edge),
    ("only shapes closing off a single-cell region are recolored", single_cell_hole),
    ("a shape counts as closed when some background cell has a shape cell in all four directions", ray_enclosed),
    ("closed shapes and the regions they enclose are both filled with 8", fill_shape_and_hole),
    ("only shapes closing off a region of at least 3 cells are recolored", big_holes_only),
    ("output is cropped to the bounding box of the recolored cells", crop_to_recolored),
    ("colors swapped: the open shapes are recolored to 8 and the closed shapes stay 1", inverted),
    ("input returned unchanged", unchanged),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b2862040.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
