"""Near-miss readings for ARC task 896d5239.

Rule: the 3-cells form V or X shaped arms. Each wedge between two arms is
filled with 8, out to the margin of the farthest arm mark, over 0 and 1 cells.
"""
import json
from pathlib import Path

FILL = 8


def _copy(g):
    return [row[:] for row in g]


def _fill_cells(inp, out):
    return {(r, c) for r, row in enumerate(out) for c, v in enumerate(row)
            if v == FILL and inp[r][c] != FILL}


def _components(cells):
    cells = set(cells)
    comps = []
    while cells:
        stack = [cells.pop()]
        comp = set(stack)
        while stack:
            r, c = stack.pop()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    n = (r + dr, c + dc)
                    if n in cells:
                        cells.discard(n)
                        comp.add(n)
                        stack.append(n)
        comps.append(comp)
    return sorted(comps, key=lambda s: min(s))


def _revert(inp, out, cells):
    g = _copy(out)
    for r, c in cells:
        g[r][c] = inp[r][c]
    return g


def wrong_color(inp, out):
    return [[2 if v == FILL else v for v in row] for row in out]


def only_zero_cells(inp, out):
    cells = {(r, c) for r, c in _fill_cells(inp, out) if inp[r][c] == 1}
    return _revert(inp, out, cells)


def only_one_cells(inp, out):
    cells = {(r, c) for r, c in _fill_cells(inp, out) if inp[r][c] == 0}
    return _revert(inp, out, cells)


def first_wedge_only(inp, out):
    comps = _components(_fill_cells(inp, out))
    if len(comps) < 2:
        return None
    return _revert(inp, out, set().union(*comps[1:]))


def skip_smallest_wedge(inp, out):
    comps = _components(_fill_cells(inp, out))
    if len(comps) < 2:
        return None
    smallest = min(comps, key=len)
    return _revert(inp, out, smallest)


def only_smallest_wedge(inp, out):
    comps = _components(_fill_cells(inp, out))
    if len(comps) < 2:
        return None
    smallest = min(comps, key=len)
    return _revert(inp, out, set().union(*[c for c in comps if c is not smallest]))


def fill_shifted_down(inp, out):
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c in _fill_cells(inp, out):
        if r + 1 < h and inp[r + 1][c] != 3:
            g[r + 1][c] = FILL
    return g


def fill_mirrored(inp, out):
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c in _fill_cells(inp, out):
        if inp[r][w - 1 - c] != 3:
            g[r][w - 1 - c] = FILL
    return g


def fill_bounding_boxes(inp, out):
    g = _copy(inp)
    for comp in _components(_fill_cells(inp, out)):
        r0 = min(r for r, _ in comp)
        r1 = max(r for r, _ in comp)
        c0 = min(c for _, c in comp)
        c1 = max(c for _, c in comp)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if inp[r][c] != 3:
                    g[r][c] = FILL
    return g


def fill_between_marks_in_row(inp, out):
    g = _copy(inp)
    for r, row in enumerate(inp):
        cols = [c for c, v in enumerate(row) if v == 3]
        for a, b in zip(cols, cols[1:]):
            for c in range(a + 1, b):
                g[r][c] = FILL
    return g


def fill_bbox_of_all_marks(inp, out):
    pts = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 3]
    r0, r1 = min(r for r, _ in pts), max(r for r, _ in pts)
    c0, c1 = min(c for _, c in pts), max(c for _, c in pts)
    g = _copy(inp)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if inp[r][c] != 3:
                g[r][c] = FILL
    return g


def overwrite_marks(inp, out):
    g = _copy(out)
    for r, c in _fill_cells(inp, out):
        for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < len(inp) and 0 <= cc < len(inp[0]) and inp[rr][cc] == 3:
                g[rr][cc] = FILL
    return g


def drop_far_row(inp, out):
    """Fill stops one margin short of the farthest arm mark."""
    g = _copy(out)
    for comp in _components(_fill_cells(inp, out)):
        rows = {r for r, _ in comp}
        cols = {c for _, c in comp}
        if max(rows) - min(rows) >= max(cols) - min(cols):
            # wedge opens vertically; drop the extreme row farthest from the apex
            # (the apex end has the narrower row)
            width = lambda rr: sum(1 for r, _ in comp if r == rr)
            far = max(rows) if width(max(rows)) >= width(min(rows)) else min(rows)
            drop = {p for p in comp if p[0] == far}
        else:
            height = lambda cc: sum(1 for _, c in comp if c == cc)
            far = max(cols) if height(max(cols)) >= height(min(cols)) else min(cols)
            drop = {p for p in comp if p[1] == far}
        g = _revert(inp, g, drop)
    return g


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("Fill the wedges with 2 instead of 8", wrong_color),
    ("Fill only 0 cells and leave 1 cells inside the wedge as they are", only_zero_cells),
    ("Fill only 1 cells and leave 0 cells inside the wedge as they are", only_one_cells),
    ("Fill only the topmost-leftmost wedge", first_wedge_only),
    ("Fill every wedge except the smallest", skip_smallest_wedge),
    ("Fill only the smallest wedge", only_smallest_wedge),
    ("Fill is displaced one row down", fill_shifted_down),
    ("Fill is the left-right mirror of the correct fill", fill_mirrored),
    ("Fill the whole bounding box of each wedge instead of the wedge shape", fill_bounding_boxes),
    ("Fill only the cells between two 3s on the same row", fill_between_marks_in_row),
    ("Fill the bounding box of all 3s as one region", fill_bbox_of_all_marks),
    ("Fill also recolors the 3 cells diagonally touching the fill", overwrite_marks),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/896d5239.json').read_text())
    train = task['train']
    print(f'{len(ALTERNATIVES)} readings, {len(train)} train pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(f'{n}/{len(train)}  {desc}')
