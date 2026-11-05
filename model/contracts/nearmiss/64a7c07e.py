import json
from pathlib import Path


def _bg(g):
    from collections import Counter
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def _blobs(g, diag=True):
    bg = _bg(g)
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    steps = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diag:
        steps += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for r in range(h):
        for c in range(w):
            if g[r][c] != bg and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x, g[y][x]))
                    for dy, dx in steps:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != bg and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                res.append(cells)
    return res


def _extent(cells, axis):
    ys = [y for y, x, c in cells]
    xs = [x for y, x, c in cells]
    return (max(xs) - min(xs) + 1) if axis == 'x' else (max(ys) - min(ys) + 1)


def _render(inp, blobs, shift, keep_old=False):
    """shift(cells) -> (dy, dx)"""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    if keep_old:
        g = [r[:] for r in inp]
    for cells in blobs:
        dy, dx = shift(cells)
        for y, x, c in cells:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                g[ny][nx] = c
    return g


def row_wise(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    for b in _blobs(inp):
        rows = {}
        for y, x, c in b:
            rows.setdefault(y, []).append((x, c))
        for y, cells in rows.items():
            n = len(cells)
            for x, c in cells:
                if x + n < w:
                    g[y][x + n] = c
    return g


def fixed_one(inp, out):
    return _render(inp, _blobs(inp), lambda b: (0, 1))


def narrowest_row(inp, out):
    def n(b):
        rows = {}
        for y, x, c in b:
            rows[y] = rows.get(y, 0) + 1
        return min(rows.values())
    return _render(inp, _blobs(inp), lambda b: (0, n(b)))


def left_by_width(inp, out):
    return _render(inp, _blobs(inp), lambda b: (0, -_extent(b, 'x')))


def down_by_height(inp, out):
    return _render(inp, _blobs(inp), lambda b: (_extent(b, 'y'), 0))


def down_by_width(inp, out):
    return _render(inp, _blobs(inp), lambda b: (_extent(b, 'x'), 0))


def whole_ink_width(inp, out):
    allc = [c for b in _blobs(inp) for c in b]
    n = _extent(allc, 'x')
    return _render(inp, _blobs(inp), lambda b: (0, n))


def width_plus_one(inp, out):
    return _render(inp, _blobs(inp), lambda b: (0, _extent(b, 'x') + 1))


def width_minus_one(inp, out):
    return _render(inp, _blobs(inp), lambda b: (0, _extent(b, 'x') - 1))


def copy_not_move(inp, out):
    return _render(inp, _blobs(inp), lambda b: (0, _extent(b, 'x')), keep_old=True)


def only_largest_moves(inp, out):
    bl = _blobs(inp)
    big = max(bl, key=len)
    return _render(inp, bl, lambda b: (0, _extent(b, 'x') if b is big else 0))


def by_cell_count(inp, out):
    return _render(inp, _blobs(inp), lambda b: (0, len(b)))


def up_by_height(inp, out):
    return _render(inp, _blobs(inp), lambda b: (-_extent(b, 'y'), 0))


ALTERNATIVES = [
    ("each row of a blob moved right by its own cell count", row_wise),
    ("every blob moved right by 1 cell", fixed_one),
    ("blobs moved right by the cell count of their narrowest row", narrowest_row),
    ("blobs moved left by their width", left_by_width),
    ("blobs moved down by their height", down_by_height),
    ("blobs moved down by their width", down_by_width),
    ("all blobs moved right by the width of the whole ink bounding box", whole_ink_width),
    ("blobs moved right by width plus one", width_plus_one),
    ("blobs moved right by width minus one", width_minus_one),
    ("blobs copied right by width, originals left in place", copy_not_move),
    ("only the largest blob moves right by its width", only_largest_moves),
    ("blobs moved right by their cell count", by_cell_count),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/64a7c07e.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
