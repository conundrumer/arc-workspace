"""Near-miss readings for task 810b9b61.

Rule: each connected 1-component that fully encloses a hole (a closed
outline) is recolored to 3; open shapes stay 1.
"""
import json
from pathlib import Path


def _dims(g):
    return len(g), len(g[0])


def _components(g, diag=False):
    h, w = _dims(g)
    seen = set()
    comps = []
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diag:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for r in range(h):
        for c in range(w):
            if g[r][c] == 1 and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                comp = []
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy, dx in steps:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and g[ny][nx] == 1 and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                comps.append(comp)
    return comps


def _holes(g, comp):
    """Zero-or-other cells inside the bounding box of comp that cannot reach
    the box border without crossing comp (4-connected)."""
    cs = set(comp)
    r0 = min(y for y, _ in comp); r1 = max(y for y, _ in comp)
    c0 = min(x for _, x in comp); c1 = max(x for _, x in comp)
    reach = set()
    stack = []
    for y in range(r0 - 1, r1 + 2):
        for x in range(c0 - 1, c1 + 2):
            if (y in (r0 - 1, r1 + 1) or x in (c0 - 1, c1 + 1)):
                reach.add((y, x))
                stack.append((y, x))
    while stack:
        y, x = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if r0 - 1 <= ny <= r1 + 1 and c0 - 1 <= nx <= c1 + 1 and (ny, nx) not in reach and (ny, nx) not in cs:
                reach.add((ny, nx))
                stack.append((ny, nx))
    return [(y, x) for y in range(r0, r1 + 1) for x in range(c0, c1 + 1)
            if (y, x) not in cs and (y, x) not in reach]


def _closed(g):
    return [c for c in _components(g) if _holes(g, c)]


def _paint(g, cells, color):
    o = [row[:] for row in g]
    for y, x in cells:
        o[y][x] = color
    return o


def all_ink(inp, out):
    return _paint(inp, [p for c in _components(inp) for p in c], 3)


def fill_interior_only(inp, out):
    cells = [p for c in _closed(inp) for p in _holes(inp, c)]
    return _paint(inp, cells, 3)


def ring_and_fill(inp, out):
    cells = []
    for c in _closed(inp):
        cells += c + _holes(inp, c)
    return _paint(inp, cells, 3)


def wrong_color(inp, out):
    return [[8 if v == 3 else v for v in row] for row in out]


def largest_only(inp, out):
    comps = _components(inp)
    if not comps:
        return None
    return _paint(inp, max(comps, key=len), 3)


def open_only(inp, out):
    cells = [p for c in _components(inp) if not _holes(inp, c) for p in c]
    return _paint(inp, cells, 3)


def big_bbox(inp, out):
    cells = []
    for c in _components(inp):
        h = max(y for y, _ in c) - min(y for y, _ in c) + 1
        w = max(x for _, x in c) - min(x for _, x in c) + 1
        if h >= 3 and w >= 3:
            cells += c
    return _paint(inp, cells, 3)


def skip_corners(inp, out):
    h, w = _dims(out)
    o = [row[:] for row in out]
    for y in range(h):
        for x in range(w):
            if out[y][x] == 3:
                vert = any(0 <= y + d < h and out[y + d][x] == 3 for d in (-1, 1))
                horiz = any(0 <= x + d < w and out[y][x + d] == 3 for d in (-1, 1))
                if vert and horiz:
                    o[y][x] = 1
    return o


def hole_at_least_two(inp, out):
    cells = [p for c in _closed(inp) if len(_holes(inp, c)) >= 3 for p in c]
    return _paint(inp, cells, 3)


def skip_bottommost(inp, out):
    cl = _closed(inp)
    if not cl:
        return None
    last = max(cl, key=lambda c: max(y for y, _ in c))
    return _paint(inp, [p for c in cl if c is not last for p in c], 3)


def erase_open(inp, out):
    o = [row[:] for row in out]
    for c in _components(inp):
        if not _holes(inp, c):
            for y, x in c:
                o[y][x] = 0
    return o


ALTERNATIVES = [
    ("recolor every 1 cell to 3, closed or not", all_ink),
    ("fill the hole inside each closed outline with 3 and leave the outline 1", fill_interior_only),
    ("recolor closed outlines and also fill their holes with 3", ring_and_fill),
    ("recolor closed outlines to 8 instead of 3", wrong_color),
    ("recolor only the largest 1-component, closed or not", largest_only),
    ("recolor the open shapes instead of the closed ones", open_only),
    ("recolor every shape whose bounding box is at least 3x3, closed or not", big_bbox),
    ("recolor closed outlines but leave their corner cells as 1", skip_corners),
    ("recolor only closed outlines whose hole has at least 3 cells", hole_at_least_two),
    ("recolor every closed outline except the bottommost one", skip_bottommost),
    ("recolor closed outlines to 3 and erase the open shapes to 0", erase_open),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/810b9b61.json").read_text())
    pairs = task["train"]

    def valid(g, out):
        if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
            return False
        if len({len(r) for r in g}) != 1:
            return False
        if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
            return False
        return g != out

    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
