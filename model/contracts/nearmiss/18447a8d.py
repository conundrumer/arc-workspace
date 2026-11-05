from pathlib import Path
import json
from collections import Counter

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/18447a8d.json')


def copy(g):
    return [r[:] for r in g]


def info(inp, out):
    """Return bg, base color, left width L, bands (row lists), fill cells."""
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    L = max(c for r in out for c, v in enumerate(r) if v != bg) + 1
    left = Counter(inp[r][c] for r in range(h) for c in range(L) if inp[r][c] != bg)
    base = left.most_common(1)[0][0]
    bands, cur = [], []
    for r in range(h):
        if any(v != bg for v in inp[r]):
            cur.append(r)
        elif cur:
            bands.append(cur)
            cur = []
    if cur:
        bands.append(cur)
    fill = {(r, c): out[r][c] for r in range(h) for c in range(L)
            if out[r][c] not in (bg, base)}
    return bg, base, L, bands, fill


def band_fill_color(band, fill):
    cols = {col for (r, c), col in fill.items() if r in band}
    return cols.pop() if cols else None


def own_piece_color(inp, band, L, bg):
    cols = {inp[r][c] for r in band for c in range(L, len(inp[0])) if inp[r][c] != bg}
    return cols.pop() if cols else None


def recolor(out, band_colors, bands, fill, bg):
    g = copy(out)
    for (r, c) in fill:
        for i, b in enumerate(bands):
            if r in b:
                g[r][c] = band_colors[i]
    return g


def no_swap(inp, out):
    bg, base, L, bands, fill = info(inp, out)
    cols = [own_piece_color(inp, b, L, bg) for b in bands]
    return recolor(out, cols, bands, fill, bg)


def rotate_colors(inp, out):
    bg, base, L, bands, fill = info(inp, out)
    cols = [band_fill_color(b, fill) for b in bands]
    cols = cols[1:] + cols[:1]
    return recolor(out, cols, bands, fill, bg)


def reverse_colors(inp, out):
    bg, base, L, bands, fill = info(inp, out)
    cols = [band_fill_color(b, fill) for b in bands][::-1]
    return recolor(out, cols, bands, fill, bg)


def unchanged(inp, out):
    return copy(inp)


def unfilled(inp, out):
    bg, base, L, bands, fill = info(inp, out)
    g = copy(out)
    for (r, c) in fill:
        g[r][c] = bg
    return g


def piece_copied(inp, out):
    bg, base, L, bands, fill = info(inp, out)
    g = copy(out)
    for r in range(len(inp)):
        for c in range(L, len(inp[0])):
            g[r][c] = inp[r][c]
    return g


def shift_right_one(inp, out):
    bg, base, L, bands, fill = info(inp, out)
    g = copy(out)
    for (r, c) in fill:
        g[r][c] = bg
    for (r, c), col in fill.items():
        g[r][c + 1] = col
    return g


def matched_but_on_right(inp, out):
    bg, base, L, bands, fill = info(inp, out)
    g = copy(out)
    for (r, c) in fill:
        g[r][c] = bg
    for (r, c), col in fill.items():
        g[r][c + 6] = col
    return g


def mirrored_piece(inp, out):
    bg, base, L, bands, fill = info(inp, out)
    g = copy(out)
    for (r, c) in fill:
        g[r][c] = bg
    for (r, c), col in fill.items():
        g[r][L - c] = col
    return g


def base_recolored(inp, out):
    bg, base, L, bands, fill = info(inp, out)
    cols = {i: band_fill_color(b, fill) for i, b in enumerate(bands)}
    g = copy(out)
    for i, b in enumerate(bands):
        for r in b:
            for c in range(L):
                if out[r][c] == base:
                    g[r][c] = cols[i]
    return g


def fill_in_base_color(inp, out):
    bg, base, L, bands, fill = info(inp, out)
    g = copy(out)
    for (r, c) in fill:
        g[r][c] = base
    return g


def first_band_only(inp, out):
    bg, base, L, bands, fill = info(inp, out)
    g = copy(out)
    for b in bands[1:]:
        for r in b:
            g[r] = inp[r][:]
    return g


ALTERNATIVES = [
    ("each piece fills the staircase in its own row band instead of the band whose hole it fits", no_swap),
    ("pieces matched to the next band's hole in cyclic order instead of by shape", rotate_colors),
    ("pieces matched to the bands in reverse top-to-bottom order", reverse_colors),
    ("nothing moves: output equals input", unchanged),
    ("pieces are removed but the staircases' holes are left unfilled", unfilled),
    ("pieces fill the holes but stay on the right as well (copied, not moved)", piece_copied),
    ("pieces land one column too far right, leaving a gap in the holes", shift_right_one),
    ("pieces are matched to the right bands but stay at the right side, holes unfilled", matched_but_on_right),
    ("pieces land mirrored left-right within the staircase area", mirrored_piece),
    ("the staircase takes the piece color as well as the holes", base_recolored),
    ("pieces fill the holes in the staircase color instead of their own color", fill_in_base_color),
    ("only the first band is solved; later bands are left as in the input", first_band_only),
]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    train = json.load(open(TASK))['train']
    print(len(ALTERNATIVES), 'readings,', len(train), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p['input'], p['output'])
            except Exception as e:
                print('  ERROR', fn.__name__, e)
                g = None
            n += valid(g, p['output'])
        print(n, fn.__name__, '-', desc)
