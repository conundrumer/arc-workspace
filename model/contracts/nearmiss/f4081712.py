import json
from collections import Counter
from pathlib import Path


def _mask(inp):
    """Mask color: the color whose cells fill exactly their bounding box."""
    for c in sorted({v for row in inp for v in row}):
        cells = [(r, k) for r, row in enumerate(inp) for k, v in enumerate(row) if v == c]
        r0, r1 = min(r for r, _ in cells), max(r for r, _ in cells)
        c0, c1 = min(k for _, k in cells), max(k for _, k in cells)
        if len(cells) == (r1 - r0 + 1) * (c1 - c0 + 1) and len(cells) > 1:
            return c, r0, r1, c0, c1
    return None


def _window(inp, fn, rows, cols):
    """Build a grid of inp[fn(r, c)] over the hole; None if a source is out of range or masked."""
    m = _mask(inp)
    n, w = len(inp), len(inp[0])
    g = []
    for r in rows:
        line = []
        for c in cols:
            rr, cc = fn(r, c)
            if not (0 <= rr < n and 0 <= cc < w) or inp[rr][cc] == m[0]:
                return None
            line.append(inp[rr][cc])
        g.append(line)
    return g


def _hole(inp):
    m = _mask(inp)
    return range(m[1], m[2] + 1), range(m[3], m[4] + 1)


def solid_mask(inp, out):
    return [[_mask(inp)[0]] * len(out[0]) for _ in out]


def flip_h(inp, out):
    return [row[::-1] for row in out]


def flip_v(inp, out):
    return out[::-1]


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def rot180(inp, out):
    return [row[::-1] for row in out[::-1]]


def mirror_off_by_one(inp, out):
    n, w = len(inp), len(inp[0])
    rows, cols = _hole(inp)
    for fn in (lambda r, c: (r, w - c), lambda r, c: (n - r, c)):
        g = _window(inp, fn, rows, cols)
        if g is not None:
            return g
    return None


def shifted_copy(inp, out):
    n, w = len(inp), len(inp[0])
    rows, cols = _hole(inp)
    for fn in (lambda r, c: (r, w - 1 - c + 1), lambda r, c: (n - 1 - r + 1, c),
               lambda r, c: (r, w - 1 - c - 1), lambda r, c: (n - 1 - r - 1, c)):
        g = _window(inp, fn, rows, cols)
        if g is not None:
            return g
    return None


def one_row_too_tall(inp, out):
    n, w = len(inp), len(inp[0])
    rows, cols = _hole(inp)
    rows = range(rows.start, rows.stop + 1)
    return _window(inp, lambda r, c: (r, w - 1 - c), rows, cols) or \
        _window(inp, lambda r, c: (n - 1 - r, c), rows, cols)


def one_col_too_wide(inp, out):
    n, w = len(inp), len(inp[0])
    rows, cols = _hole(inp)
    cols = range(cols.start, cols.stop + 1)
    return _window(inp, lambda r, c: (r, w - 1 - c), rows, cols) or \
        _window(inp, lambda r, c: (n - 1 - r, c), rows, cols)


def most_common_color(inp, out):
    m = _mask(inp)[0]
    cnt = Counter(v for row in inp for v in row if v != m)
    col = cnt.most_common(1)[0][0]
    return [[col] * len(out[0]) for _ in out]


def full_width_rows(inp, out):
    n = len(inp)
    rows, _ = _hole(inp)
    m = _mask(inp)[0]
    g = [inp[n - 1 - r] for r in rows]
    if any(m in row for row in g):
        return None
    return [list(row) for row in g]


def neighbour_block(inp, out):
    n, w = len(inp), len(inp[0])
    rows, cols = _hole(inp)
    h, ww = len(rows), len(cols)
    for dr, dc in ((0, ww), (0, -ww), (h, 0), (-h, 0)):
        g = _window(inp, lambda r, c: (r + dr, c + dc), rows, cols)
        if g is not None:
            return g
    return None


def keep_mask_border(inp, out):
    """Fill only the interior of the hole; leave the outer ring as mask color."""
    m = _mask(inp)[0]
    h, w = len(out), len(out[0])
    if h < 3 or w < 3:
        return None
    return [[out[r][c] if 0 < r < h - 1 and 0 < c < w - 1 else m for c in range(w)] for r in range(h)]


ALTERNATIVES = [
    ("output is the hole itself, all mask color", solid_mask),
    ("correct content mirrored left-right", flip_h),
    ("correct content mirrored top-bottom", flip_v),
    ("correct content transposed", transpose),
    ("mirror axis off by one (reflect with n-c instead of n-1-c)", mirror_off_by_one),
    ("mirrored crop shifted by one cell", shifted_copy),
    ("crop one row too tall", one_row_too_tall),
    ("crop one column too wide", one_col_too_wide),
    ("fill with the most common non-mask color", most_common_color),
    ("output the full-width rows at the hole's rows, mirrored", full_width_rows),
    ("copy the neighbouring block of the same size", neighbour_block),
    ("only the hole interior is recovered, ring stays mask", keep_mask_border),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/f4081712.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                ok += 1
        print(ok, desc)
