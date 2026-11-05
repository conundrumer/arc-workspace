import json
from pathlib import Path


def vflip(g):
    return [list(r) for r in g[::-1]]


def hflip(g):
    return [list(r[::-1]) for r in g]


def rot180(g):
    return hflip(vflip(g))


def transpose(g):
    return [list(r) for r in zip(*g)]


def rot90cw(g):
    return [list(r) for r in zip(*g[::-1])]


def rot90ccw(g):
    return [list(r) for r in zip(*g)][::-1]


def quad(tl, tr, bl, br):
    top = [a + b for a, b in zip(tl, tr)]
    bot = [a + b for a, b in zip(bl, br)]
    return top + bot


def hcat(a, b):
    return [x + y for x, y in zip(a, b)]


def anchor_top_left(inp, out):
    return quad(inp, hflip(inp), vflip(inp), rot180(inp))


def anchor_top_right(inp, out):
    return quad(hflip(inp), inp, rot180(inp), vflip(inp))


def swapped_flips(inp, out):
    return quad(rot180(inp), hflip(inp), vflip(inp), inp)


def rotations_not_mirrors(inp, out):
    if len(inp) != len(inp[0]):
        return None
    return quad(rot180(inp), rot90cw(inp), rot90ccw(inp), inp)


def plain_copy(inp, out):
    return quad(inp, inp, inp, inp)


def horizontal_only(inp, out):
    return hcat(hflip(inp), inp)


def vertical_only(inp, out):
    return vflip(inp) + [list(r) for r in inp]


def missing_far_tile(inp, out):
    h, w = len(inp), len(inp[0])
    g = [list(r) for r in out]
    for r in range(h):
        for c in range(w):
            g[r][c] = 0
    return g


def shared_seam(inp, out):
    h, w = len(inp), len(inp[0])
    full = quad(rot180(inp), vflip(inp), hflip(inp), inp)
    rows = [r for i, r in enumerate(full) if i != h]
    return [[v for j, v in enumerate(r) if j != w] for r in rows]


def dominant_color_dropped(inp, out):
    counts = {}
    for r in inp:
        for v in r:
            if v:
                counts[v] = counts.get(v, 0) + 1
    if not counts:
        return None
    top = max(sorted(counts), key=lambda k: counts[k])
    return [[0 if v == top else v for v in r] for r in out]


def transposed_tiles(inp, out):
    if len(inp) != len(inp[0]):
        return None
    t = transpose(inp)
    return quad(rot180(inp), t, t, inp)


def kaleidoscope_3x3(inp, out):
    h = vflip(inp)
    rows = []
    for band in (h, inp, h):
        a = hflip(band)
        rows += [x + y + z for x, y, z in zip(a, band, a)]
    return rows


def last_row_cropped(inp, out):
    return [list(r) for r in out[:-1]]


ALTERNATIVES = [
    ("input placed at top-left tile instead of bottom-right", anchor_top_left),
    ("input placed at top-right tile instead of bottom-right", anchor_top_right),
    ("vertical-flip and horizontal-flip tiles swapped", swapped_flips),
    ("tiles are 90-degree rotations of the input rather than mirrors", rotations_not_mirrors),
    ("input copied unchanged into all four tiles", plain_copy),
    ("mirror on the horizontal axis only, giving a double-width output", horizontal_only),
    ("mirror on the vertical axis only, giving a double-height output", vertical_only),
    ("top-left tile (180-degree rotation) left blank", missing_far_tile),
    ("mirrored copies share one seam row and column, giving size 2n-1", shared_seam),
    ("most common non-zero color erased from the output", dominant_color_dropped),
    ("off-diagonal tiles are transposes of the input", transposed_tiles),
    ("3x3 mirrored tiling around the input", kaleidoscope_3x3),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/833dafe3.json').read_text())
    pairs = task['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g) and g != p['output']:
                n += 1
        print(f'{n}/{len(pairs)}  {desc}')
