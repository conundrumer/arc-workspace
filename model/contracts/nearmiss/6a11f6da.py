import json
from pathlib import Path


def tiles(inp):
    h = len(inp) // 3
    return [inp[i * h:(i + 1) * h] for i in range(3)]


def tile_color(t):
    for row in t:
        for v in row:
            if v:
                return v
    return 0


def overlay(inp, order, skip=()):
    """order: tile indices, highest priority first."""
    ts = tiles(inp)
    h, w = len(ts[0]), len(ts[0][0])
    res = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            for k in order:
                if k in skip:
                    continue
                if ts[k][r][c]:
                    res[r][c] = ts[k][r][c]
                    break
    return res


def by_color(inp, colors, skip_colors=()):
    ts = tiles(inp)
    idx = {tile_color(t): i for i, t in enumerate(ts)}
    order = [idx[c] for c in colors if c in idx]
    skip = [idx[c] for c in skip_colors if c in idx]
    return overlay(inp, order, skip)


def prio(*colors):
    return lambda inp, out: by_color(inp, colors)


def top_first(inp, out):
    return overlay(inp, [0, 1, 2])


def bottom_first(inp, out):
    return overlay(inp, [2, 1, 0])


def ignore_8(inp, out):
    return by_color(inp, (6, 1), skip_colors=())


def ignore_6(inp, out):
    return by_color(inp, (1, 8))


def bg_fill_8(inp, out):
    return [[8 if v == 0 else v for v in row] for row in out]


def overlap_cancels(inp, out):
    ts = tiles(inp)
    h, w = len(ts[0]), len(ts[0][0])
    res = [row[:] for row in out]
    for r in range(h):
        for c in range(w):
            if sum(1 for t in ts if t[r][c]) > 1:
                res[r][c] = 0
    return res


def single_color(inp, out):
    return [[6 if v else 0 for v in row] for row in out]


def flip_h(inp, out):
    return [row[::-1] for row in out]


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def first_tile_only(inp, out):
    return [row[:] for row in tiles(inp)[0]]


def drop_last_row(inp, out):
    return [row[:] for row in out[:-1]]


ALTERNATIVES = [
    ("priority 1 over 6 over 8 instead of 6 over 1 over 8", prio(1, 6, 8)),
    ("priority 8 over 1 over 6", prio(8, 1, 6)),
    ("priority 6 over 8 over 1", prio(6, 8, 1)),
    ("priority by slab position, top slab wins", top_first),
    ("8 slab ignored, only 6 over 1 stacked", ignore_8),
    ("6 slab ignored, only 1 over 8 stacked", ignore_6),
    ("background filled with 8 instead of 0", bg_fill_8),
    ("cells where slabs overlap are left empty", overlap_cancels),
    ("every inked cell takes color 6", single_color),
    ("output mirrored left to right", flip_h),
    ("output is the first slab alone", first_tile_only),
    ("output loses its last row (off-by-one size)", drop_last_row),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/6a11f6da.json'))
    pairs = task['train']
    print('pairs', len(pairs), 'readings', len(ALTERNATIVES))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(n, desc)
