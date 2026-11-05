import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _dividers(inp):
    bg = _bg(inp)
    rows = [i for i, r in enumerate(inp) if len(set(r)) == 1 and r[0] != bg]
    cols = [j for j in range(len(inp[0]))
            if len({r[j] for r in inp}) == 1 and inp[0][j] != bg]
    return rows[0], cols[0]


def _quads(inp):
    """Four quadrant regions (r0, r1, c0, c1), order TL, TR, BL, BR."""
    dr, dc = _dividers(inp)
    h, w = len(inp), len(inp[0])
    return [(0, dr, 0, dc), (0, dr, dc + 1, w), (dr + 1, h, 0, dc), (dr + 1, h, dc + 1, w)]


def _bbox(inp, q):
    bg = _bg(inp)
    r0, r1, c0, c1 = q
    cells = [(i, j) for i in range(r0, r1) for j in range(c0, c1) if inp[i][j] != bg]
    return (min(i for i, _ in cells), max(i for i, _ in cells) + 1,
            min(j for _, j in cells), max(j for _, j in cells) + 1)


def _crop(inp, b, pad_r=0, pad_c=0):
    r0, r1, c0, c1 = b
    h, w = len(inp), len(inp[0])
    r1 = min(h, r1 + pad_r)
    c1 = min(w, c1 + pad_c)
    return [row[c0:c1] for row in inp[r0:r1]]


def _tiles(inp):
    return [_crop(inp, _bbox(inp, q)) for q in _quads(inp)]


def _assemble(t):
    """2x2 composition of four equally sized tiles."""
    top = [a + b for a, b in zip(t[0], t[1])]
    bot = [a + b for a, b in zip(t[2], t[3])]
    return top + bot


def _out_tiles(out):
    h, w = len(out) // 2, len(out[0]) // 2
    return [[r[:w] for r in out[:h]], [r[w:] for r in out[:h]],
            [r[:w] for r in out[h:]], [r[w:] for r in out[h:]]]


def swap_lr(inp, out):
    t = _out_tiles(out)
    return _assemble([t[1], t[0], t[3], t[2]])


def swap_tb(inp, out):
    t = _out_tiles(out)
    return _assemble([t[2], t[3], t[0], t[1]])


def swap_diag(inp, out):
    t = _out_tiles(out)
    return _assemble([t[0], t[2], t[1], t[3]])


def clockwise_order(inp, out):
    t = _out_tiles(out)
    return _assemble([t[0], t[1], t[3], t[2]])


def mirror_each_tile(inp, out):
    t = _out_tiles(out)
    return _assemble([[r[::-1] for r in x] for x in t])


def flip_each_tile_vertically(inp, out):
    t = _out_tiles(out)
    return _assemble([x[::-1] for x in t])


def tile_is_quadrant_corner(inp, out):
    """Tile is a fixed-size window at each quadrant's top-left corner, not the shape's bbox."""
    s = len(out) // 2
    t = [_crop(inp, (q[0], q[0] + s, q[2], q[2] + s)) for q in _quads(inp)]
    return _assemble(t)


def whole_quadrants(inp, out):
    """Tile is the whole quadrant, no crop to the shape."""
    t = [_crop(inp, q) for q in _quads(inp)]
    rows = max(len(x) for x in t[:2])
    cols = max(len(x[0]) for x in (t[0], t[2]))
    def pad(x, hh, ww):
        return [r + [0] * (ww - len(r)) for r in x] + [[0] * ww for _ in range(hh - len(x))]
    h0 = max(len(t[0]), len(t[1])); h1 = max(len(t[2]), len(t[3]))
    w0 = max(len(t[0][0]), len(t[2][0])); w1 = max(len(t[1][0]), len(t[3][0]))
    tl, tr = pad(t[0], h0, w0), pad(t[1], h0, w1)
    bl, br = pad(t[2], h1, w0), pad(t[3], h1, w1)
    return [a + b for a, b in zip(tl, tr)] + [a + b for a, b in zip(bl, br)]


def bbox_one_extra(inp, out):
    """Crop is one row and one column too large."""
    t = [_crop(inp, _bbox(inp, q), 1, 1) for q in _quads(inp)]
    hs = [max(len(t[0]), len(t[1])), max(len(t[2]), len(t[3]))]
    ws = [max(len(t[0][0]), len(t[2][0])), max(len(t[1][0]), len(t[3][0]))]
    def pad(x, hh, ww):
        return [r + [0] * (ww - len(r)) for r in x] + [[0] * ww for _ in range(hh - len(x))]
    tl, tr = pad(t[0], hs[0], ws[0]), pad(t[1], hs[0], ws[1])
    bl, br = pad(t[2], hs[1], ws[0]), pad(t[3], hs[1], ws[1])
    return [a + b for a, b in zip(tl, tr)] + [a + b for a, b in zip(bl, br)]


def recolor_to_first(inp, out):
    c = next(v for r in out for v in r if v)
    return [[c if v else 0 for v in r] for r in out]


def recolor_to_divider(inp, out):
    dr, dc = _dividers(inp)
    c = inp[dr][dc] if inp[dr][0] != 0 else inp[dr][0]
    return [[c if v else 0 for v in r] for r in out]


def drop_bottom_right(inp, out):
    h, w = len(out) // 2, len(out[0]) // 2
    return [[0 if (i >= h and j >= w) else v for j, v in enumerate(r)] for i, r in enumerate(out)]


def stacked_column(inp, out):
    t = _tiles(inp)
    return [r for x in t for r in x]


def overlaid(inp, out):
    t = _out_tiles(out)
    h, w = len(t[0]), len(t[0][0])
    res = [[0] * w for _ in range(h)]
    for x in t:
        for i in range(h):
            for j in range(w):
                if x[i][j]:
                    res[i][j] = x[i][j]
    return res


ALTERNATIVES = [
    ("quadrant shapes placed with left and right columns swapped", swap_lr),
    ("quadrant shapes placed with top and bottom rows swapped", swap_tb),
    ("top-right and bottom-left shapes exchanged (transposed layout)", swap_diag),
    ("shapes placed in clockwise order TL, TR, BR, BL", clockwise_order),
    ("each shape mirrored left-right inside its tile", mirror_each_tile),
    ("each shape flipped top-bottom inside its tile", flip_each_tile_vertically),
    ("tile is a fixed window at each quadrant corner instead of the shape's bounding box", tile_is_quadrant_corner),
    ("tile is the whole quadrant, no crop to the shape", whole_quadrants),
    ("crop one row and one column larger than the bounding box", bbox_one_extra),
    ("all shapes recolored to the top-left shape's color", recolor_to_first),
    ("bottom-right shape left out", drop_bottom_right),
    ("four shapes stacked in a single column", stacked_column),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/0bb8deee.json'))
    pairs = task['train']
    print('pairs', len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p['input'], p['output'])
            except Exception as e:
                print('  error', f.__name__, repr(e))
                g = None
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
