import json
from pathlib import Path

BAR = 5


def _box(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == BAR]
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def _crop(inp, r0, r1, c0, c1):
    h, w = len(inp), len(inp[0])
    r0, c0 = max(r0, 0), max(c0, 0)
    r1, c1 = min(r1, h - 1), min(c1, w - 1)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def bars_only(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0, r1, c0, c1)


def top_cap_only(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0 - 1, r1, c0, c1)


def bottom_cap_only(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0, r1 + 1, c0, c1)


def wrong_axis(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0, r1, c0 - 1, c1 + 1)


def both_axes(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0 - 1, r1 + 1, c0 - 1, c1 + 1)


def two_cells_cap(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0 - 2, r1 + 2, c0, c1)


def all_nonzero_box(inp, out):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v]
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return _crop(inp, min(rs), max(rs), min(cs), max(cs))


def drop_inner_caps(inp, out):
    g = [row[:] for row in out]
    for r in range(1, len(g) - 1):
        for c in range(len(g[0])):
            if g[r][c] != BAR:
                g[r][c] = 0
    return g


def drop_cap_rows(inp, out):
    g = [row[:] for row in out]
    for r in (0, len(g) - 1):
        g[r] = [0] * len(g[r])
    return g


def drop_bars(inp, out):
    return [[0 if v == BAR else v for v in row] for row in out]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def shifted_left(inp, out):
    r0, r1, c0, c1 = _box(inp)
    return _crop(inp, r0 - 1, r1 + 1, c0 - 1, c1 - 1)


ALTERNATIVES = [
    ("crop only the bounding box of the 5 bars, no cap row at either end", bars_only),
    ("extend the box by one row only above the bars", top_cap_only),
    ("extend the box by one row only below the bars", bottom_cap_only),
    ("extend the box one column left and right (wrong axis) instead of one row up and down", wrong_axis),
    ("extend the box by one cell on all four sides", both_axes),
    ("extend the box by two rows above and below", two_cells_cap),
    ("crop the bounding box of all non-zero cells", all_nonzero_box),
    ("keep the bars and cap rows but erase the 8 cells between the bars", drop_inner_caps),
    ("keep the box but erase the 8 cells of the cap rows", drop_cap_rows),
    ("keep the box but erase the 5 bars", drop_bars),
    ("correct crop but transposed", transposed),
    ("correct-size crop offset one column to the left", shifted_left),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/3f7978a0.json').read_text())
    pairs = task['train']
    print('pairs', len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
