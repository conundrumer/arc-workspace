"""Near-miss readings for ARC task 9b4c17c4.

True rule: the grid has two background fields (colors 1 and 8) with ink (2)
rectangles on them. Shapes on field 8 slide left to the field edge, shapes on
field 1 slide right to the field edge. Vacated cells take the field color.
"""
import json
from pathlib import Path

INK = 2
TRUE_DIR = {8: (0, -1), 1: (0, 1)}  # (drow, dcol)


def _components(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == INK and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == INK and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                comps.append(cells)
    return comps


def _field_of(inp, cells):
    h, w = len(inp), len(inp[0])
    counts = {}
    for y, x in cells:
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != INK:
                counts[inp[ny][nx]] = counts.get(inp[ny][nx], 0) + 1
    return max(counts, key=counts.get)


def _analyse(inp):
    comps = _components(inp)
    fields = [_field_of(inp, c) for c in comps]
    base = [row[:] for row in inp]
    for cells, f in zip(comps, fields):
        for y, x in cells:
            base[y][x] = f
    boxes = {}
    for r, row in enumerate(base):
        for c, v in enumerate(row):
            b = boxes.setdefault(v, [r, r, c, c])
            b[0] = min(b[0], r); b[1] = max(b[1], r)
            b[2] = min(b[2], c); b[3] = max(b[3], c)
    return comps, fields, base, boxes


def _edge_dist(cells, box, d):
    r0, r1, c0, c1 = box
    if d == (0, -1):
        return min(x for _, x in cells) - c0
    if d == (0, 1):
        return c1 - max(x for _, x in cells)
    if d == (-1, 0):
        return min(y for y, _ in cells) - r0
    return r1 - max(y for y, _ in cells)


def _render(inp, dirfn, move=lambda f, cells: True, trim=0, keep_orig=False, erase=False):
    """dirfn(field, cells, box) -> direction or None."""
    comps, fields, base, boxes = _analyse(inp)
    g = [row[:] for row in base]
    for cells, f in zip(comps, fields):
        if keep_orig:
            for y, x in cells:
                g[y][x] = INK
        if erase:
            continue
        d = dirfn(f, cells, boxes[f])
        if d is None or not move(f, cells):
            for y, x in cells:
                g[y][x] = INK
            continue
        k = max(0, _edge_dist(cells, boxes[f], d) - trim)
        for y, x in cells:
            g[y + d[0] * k][x + d[1] * k] = INK
    return g


def swapped(inp, out):
    return _render(inp, lambda f, c, b: {8: (0, 1), 1: (0, -1)}[f])


def all_left(inp, out):
    return _render(inp, lambda f, c, b: (0, -1))


def all_right(inp, out):
    return _render(inp, lambda f, c, b: (0, 1))


def vertical(inp, out):
    return _render(inp, lambda f, c, b: {8: (-1, 0), 1: (1, 0)}[f])


def one_short(inp, out):
    return _render(inp, lambda f, c, b: TRUE_DIR[f], trim=1)


def only_field1_moves(inp, out):
    return _render(inp, lambda f, c, b: TRUE_DIR[f], move=lambda f, c: f == 1)


def only_field8_moves(inp, out):
    return _render(inp, lambda f, c, b: TRUE_DIR[f], move=lambda f, c: f == 8)


def shapes_erased(inp, out):
    return _render(inp, lambda f, c, b: TRUE_DIR[f], erase=True)


def copy_left_behind(inp, out):
    return _render(inp, lambda f, c, b: TRUE_DIR[f], keep_orig=True)


def nearer_edge(inp, out):
    def pick(f, cells, box):
        left = min(x for _, x in cells) - box[2]
        right = box[3] - max(x for _, x in cells)
        return (0, -1) if left <= right else (0, 1)
    return _render(inp, pick)


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("directions swapped: field 8 slides right, field 1 slides left", swapped),
    ("every shape slides left whatever its field", all_left),
    ("every shape slides right whatever its field", all_right),
    ("shapes slide vertically (field 8 up, field 1 down) instead of horizontally", vertical),
    ("shapes stop one cell short of the field edge", one_short),
    ("only shapes on field 1 slide; shapes on field 8 stay", only_field1_moves),
    ("only shapes on field 8 slide; shapes on field 1 stay", only_field8_moves),
    ("shapes are removed instead of moved", shapes_erased),
    ("shapes are copied to the edge but the originals stay", copy_left_behind),
    ("each shape slides to the nearer horizontal edge of its field", nearer_edge),
    ("input returned unchanged", unchanged),
]


def _valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/9b4c17c4.json').read_text())
    pairs = task["train"]
    print("pairs:", len(pairs))
    # sanity: the true rule reproduces the output
    truth = [_render(p["input"], lambda f, c, b: TRUE_DIR[f]) == p["output"] for p in pairs]
    print("true rule reproduces outputs:", truth)
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
