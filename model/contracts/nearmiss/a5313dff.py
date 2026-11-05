import json
from pathlib import Path


def _dims(g):
    return len(g), len(g[0])


def _reach(inp, nbrs, edge_ok=lambda r, c, h, w: True):
    """Background cells connected to an allowed edge cell through background cells."""
    h, w = _dims(inp)
    seen = set()
    stack = [(r, c) for r in range(h) for c in range(w)
             if inp[r][c] == 0 and (r in (0, h - 1) or c in (0, w - 1)) and edge_ok(r, c, h, w)]
    seen.update(stack)
    while stack:
        r, c = stack.pop()
        for dr, dc in nbrs:
            q = (r + dr, c + dc)
            if 0 <= q[0] < h and 0 <= q[1] < w and q not in seen and inp[q[0]][q[1]] == 0:
                seen.add(q)
                stack.append(q)
    return seen


N4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
N8 = N4 + [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def _filled(inp, out):
    h, w = _dims(inp)
    return {(r, c) for r in range(h) for c in range(w) if inp[r][c] != out[r][c]}


def _components(cells):
    cells = set(cells)
    comps = []
    while cells:
        s = cells.pop()
        comp = {s}
        stack = [s]
        while stack:
            r, c = stack.pop()
            for dr, dc in N4:
                q = (r + dr, c + dc)
                if q in cells:
                    cells.remove(q)
                    comp.add(q)
                    stack.append(q)
        comps.append(comp)
    return comps


def _paint(inp, cells, color=1):
    g = [row[:] for row in inp]
    for r, c in cells:
        g[r][c] = color
    return g


def four_ray_walls(inp, out):
    h, w = _dims(inp)
    cells = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0:
                continue
            col = [inp[i][c] for i in range(h)]
            if (2 in inp[r][:c] and 2 in inp[r][c + 1:]
                    and 2 in col[:r] and 2 in col[r + 1:]):
                cells.append((r, c))
    return _paint(inp, cells)


def wrong_color(inp, out):
    return _paint(inp, _filled(inp, out), 3)


def largest_only(inp, out):
    comps = _components(_filled(inp, out))
    if len(comps) < 2:
        return None
    return _paint(inp, max(comps, key=len))


def bbox_fill(inp, out):
    cells = set()
    for comp in _components(_filled(inp, out)):
        rs = [r for r, _ in comp]
        cs = [c for _, c in comp]
        for r in range(min(rs), max(rs) + 1):
            for c in range(min(cs), max(cs) + 1):
                cells.add((r, c))
    return _paint(inp, cells)


def bottom_edge_closes(inp, out):
    reached = _reach(inp, N4, lambda r, c, h, w: r != h - 1 and not (c in (0, w - 1) and r == h - 1))
    # Only seeds on the top, left and right edges count (bottom row seeds do not).
    h, w = _dims(inp)
    return _paint(inp, [(r, c) for r in range(h) for c in range(w)
                        if inp[r][c] == 0 and (r, c) not in reached])


def bbox_of_all_walls(inp, out):
    h, w = _dims(inp)
    pts = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == 2]
    r0, r1 = min(p[0] for p in pts), max(p[0] for p in pts)
    c0, c1 = min(p[1] for p in pts), max(p[1] for p in pts)
    return _paint(inp, [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
                        if inp[r][c] == 0])


def row_scan_only(inp, out):
    h, w = _dims(inp)
    cells = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 and 2 in inp[r][:c] and 2 in inp[r][c + 1:]:
                cells.append((r, c))
    return _paint(inp, cells)


def outline_instead(inp, out):
    h, w = _dims(inp)
    fill = _filled(inp, out)
    cells = set()
    for r, c in fill:
        for dr, dc in N8:
            q = (r + dr, c + dc)
            if 0 <= q[0] < h and 0 <= q[1] < w and inp[q[0]][q[1]] == 2:
                cells.add(q)
    return _paint(inp, cells)


def crop_to_fill(inp, out):
    fill = _filled(inp, out)
    rs = [r for r, _ in fill]
    cs = [c for _, c in fill]
    return [row[min(cs):max(cs) + 1] for row in out[min(rs):max(rs) + 1]]


def top_row_only(inp, out):
    cells = []
    for comp in _components(_filled(inp, out)):
        top = min(r for r, _ in comp)
        cells += [(r, c) for r, c in comp if r == top]
    return _paint(inp, cells)


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("a background cell is filled when a wall lies somewhere in each of the four directions from it", four_ray_walls),
    ("enclosed cells are filled with 3 instead of 1", wrong_color),
    ("only the largest enclosed region is filled", largest_only),
    ("each enclosed region is filled over its whole bounding box, covering wall cells inside it", bbox_fill),
    ("the bottom grid edge counts as a wall, so shapes cut off by the bottom edge are filled", bottom_edge_closes),
    ("every background cell inside the bounding box of all wall cells is filled", bbox_of_all_walls),
    ("a background cell is filled when walls lie to its left and right in its row", row_scan_only),
    ("the wall cells around each enclosed region are recolored instead of the interior", outline_instead),
    ("output is cropped to the bounding box of the filled region", crop_to_fill),
    ("only the top row of each enclosed region is filled", top_row_only),
    ("no cell is filled; the input is returned", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    path = Path(__file__).resolve().parents[3] / 'data/tasks/a5313dff.json'
    train = json.load(open(path))['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, len(train), desc)
