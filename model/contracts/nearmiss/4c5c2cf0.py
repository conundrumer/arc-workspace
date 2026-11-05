"""Near-miss readings for ARC task 4c5c2cf0.

True rule: one shape is a symmetric 3x3 pivot; the other shape is copied
by mirroring across the pivot's center column, center row, and both.
"""
import json
from pathlib import Path


def _cells(g):
    d = {}
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v:
                d.setdefault(v, []).append((r, c))
    return d


def _setup(inp, out):
    d = _cells(inp)
    do = _cells(out)
    pivot = [k for k in d if len(do.get(k, [])) == len(d[k])]
    if len(pivot) != 1 or len(d) != 2:
        return None
    pc = pivot[0]
    oc = [k for k in d if k != pc][0]
    pr = [r for r, _ in d[pc]]
    pcc = [c for _, c in d[pc]]
    return pc, oc, d[pc], d[oc], (min(pr), max(pr), min(pcc), max(pcc))


def _paint(inp, cells, color):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for r, c in cells:
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = color
    return g


def _finish(g, out):
    return g if g != out else None


def _mirror(inp, out, h=True, v=True, d=True, dr=0, dc=0, color=None):
    s = _setup(inp, out)
    if not s:
        return None
    pc, oc, pcells, ocells, (r0, r1, c0, c1) = s
    cells = []
    for r, c in ocells:
        rr = r0 + r1 - r + dr
        cc = c0 + c1 - c + dc
        if h:
            cells.append((r, cc))
        if v:
            cells.append((rr, c))
        if d:
            cells.append((rr, cc))
    return _finish(_paint(inp, cells, oc if color is None else color(pc, oc)), out)


def horiz_only(inp, out):
    return _mirror(inp, out, v=False, d=False)


def vert_only(inp, out):
    return _mirror(inp, out, h=False, d=False)


def point_only(inp, out):
    return _mirror(inp, out, h=False, v=False)


def missing_corner(inp, out):
    return _mirror(inp, out, d=False)


def axis_off_by_one(inp, out):
    return _mirror(inp, out, dr=1, dc=1)


def copies_in_pivot_color(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    pc, oc, pcells, ocells, (r0, r1, c0, c1) = s
    cells = []
    for r, c in ocells:
        rr, cc = r0 + r1 - r, c0 + c1 - c
        cells += [(r, cc), (rr, c), (rr, cc)]
    return _finish(_paint(inp, cells, pc), out)


def rotated_copies(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    pc, oc, pcells, ocells, (r0, r1, c0, c1) = s
    cr, cc = (r0 + r1) // 2, (c0 + c1) // 2
    cells = []
    for r, c in ocells:
        y, x = r - cr, c - cc
        cells += [(cr + x, cc - y), (cr - y, cc - x), (cr - x, cc + y)]
    return _finish(_paint(inp, cells, oc), out)


def translated_copies(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    pc, oc, pcells, ocells, (r0, r1, c0, c1) = s
    rs = [r for r, _ in ocells]
    cs = [c for _, c in ocells]
    dr = (r0 + r1) - (min(rs) + max(rs))
    dc = (c0 + c1) - (min(cs) + max(cs))
    cells = []
    for r, c in ocells:
        cells += [(r, c + dc), (r + dr, c), (r + dr, c + dc)]
    return _finish(_paint(inp, cells, oc), out)


def original_erased(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    oc, ocells = s[1], s[3]
    g = [row[:] for row in out]
    for r, c in ocells:
        g[r][c] = 0
    return _finish(g, out)


def swapped_pivot(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    pc, oc, pcells, ocells, _ = s
    rs = [r for r, _ in ocells]
    cs = [c for _, c in ocells]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    cells = []
    for r, c in pcells:
        rr, cc = r0 + r1 - r, c0 + c1 - c
        cells += [(r, cc), (rr, c), (rr, cc)]
    return _finish(_paint(inp, cells, pc), out)


def grid_center_axes(inp, out):
    s = _setup(inp, out)
    if not s:
        return None
    oc, ocells = s[1], s[3]
    h, w = len(inp), len(inp[0])
    cells = []
    for r, c in ocells:
        rr, cc = h - 1 - r, w - 1 - c
        cells += [(r, cc), (rr, c), (rr, cc)]
    return _finish(_paint(inp, cells, oc), out)


ALTERNATIVES = [
    ("mirror across the pivot's center column only (no vertical copy)", horiz_only),
    ("mirror across the pivot's center row only (no horizontal copy)", vert_only),
    ("only the 180-degree point reflection through the pivot center", point_only),
    ("horizontal and vertical copies but the diagonal corner copy is missing", missing_corner),
    ("mirror axes shifted one cell down and right of the pivot center", axis_off_by_one),
    ("mirrored copies painted in the pivot's color", copies_in_pivot_color),
    ("copies rotated 90, 180, 270 degrees about the pivot center instead of mirrored", rotated_copies),
    ("copies translated to the mirror positions without flipping", translated_copies),
    ("copies drawn but the original other shape erased", original_erased),
    ("roles swapped: the symmetric shape is mirrored around the other shape's box", swapped_pivot),
    ("mirror across the grid's center lines instead of the pivot's", grid_center_axes),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/4c5c2cf0.json'))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
