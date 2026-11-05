import json
from collections import Counter
from pathlib import Path


def parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    frame = max((c for c in cnt if c != bg), key=lambda c: cnt[c])
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == frame]
    r0 = min(r for r, c in cells)
    r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells)
    c1 = max(c for r, c in cells)
    inside = lambda r, c: r0 <= r <= r1 and c0 <= c <= c1
    markers = [(r - r0, c - c0, inp[r][c]) for r in range(r0, r1 + 1)
               for c in range(c0, c1 + 1) if inp[r][c] != frame]
    pos = {}
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v != bg and not inside(r, c):
                pos.setdefault(v, []).append((r, c))
    shapes = {}
    tops = {}
    for col, ps in pos.items():
        a = min(p[0] for p in ps)
        b = max(p[0] for p in ps)
        x = min(p[1] for p in ps)
        y = max(p[1] for p in ps)
        g = [[bg] * (y - x + 1) for _ in range(b - a + 1)]
        for (r, c) in ps:
            g[r - a][c - x] = col
        shapes[col] = g
        tops[col] = (a, x)
    size = r1 - r0 + 1
    half = size // 2
    quad = {}
    for (r, c, col) in markers:
        quad[(1 if r >= half else 0, 1 if c >= half else 0)] = col
    return dict(bg=bg, frame=frame, shapes=shapes, tops=tops, quad=quad,
                legend=[row[c0:c1 + 1] for row in inp[r0:r1 + 1]])


def assemble(bg, tiles, t=3, gap=1, gapfill=None):
    # tiles: dict (qr,qc) -> t x t grid
    n = 2 * t + gap
    gf = bg if gapfill is None else gapfill
    g = [[gf] * n for _ in range(n)]
    for (qr, qc), tg in tiles.items():
        for i in range(t):
            for j in range(t):
                g[qr * (t + gap) + i][qc * (t + gap) + j] = tg[i][j] if i < len(tg) and j < len(tg[0]) else bg
    return g


def true_tiles(P):
    return {k: P['shapes'][v] for k, v in P['quad'].items()}


def flip_h(g):
    return [r[::-1] for r in g]


def flip_v(g):
    return g[::-1]


def rot90(g):
    return [list(r) for r in zip(*g[::-1])]


def transpose_t(g):
    return [list(r) for r in zip(*g)]


def tsize(out):
    return (len(out) - 1) // 2


def a_transpose_layout(inp, out):
    P = parse(inp)
    tl = {(c, r): s for (r, c), s in true_tiles(P).items()}
    return assemble(P['bg'], tl, tsize(out))


def a_mirror_layout_lr(inp, out):
    P = parse(inp)
    tl = {(r, 1 - c): s for (r, c), s in true_tiles(P).items()}
    return assemble(P['bg'], tl, tsize(out))


def a_rotate_layout_180(inp, out):
    P = parse(inp)
    tl = {(1 - r, 1 - c): s for (r, c), s in true_tiles(P).items()}
    return assemble(P['bg'], tl, tsize(out))


def a_shapes_flipped(inp, out):
    P = parse(inp)
    tl = {k: flip_h(s) for k, s in true_tiles(P).items()}
    return assemble(P['bg'], tl, tsize(out))


def a_shapes_rotated(inp, out):
    P = parse(inp)
    tl = {k: rot90(s) for k, s in true_tiles(P).items()}
    return assemble(P['bg'], tl, tsize(out))


def a_no_gap(inp, out):
    P = parse(inp)
    return assemble(P['bg'], true_tiles(P), tsize(out), gap=0)


def a_gap_frame_color(inp, out):
    P = parse(inp)
    return assemble(P['bg'], true_tiles(P), tsize(out), gapfill=P['frame'])


def a_reading_order_of_shapes(inp, out):
    P = parse(inp)
    cols = sorted(P['shapes'], key=lambda c: P['tops'][c])
    keys = [(0, 0), (0, 1), (1, 0), (1, 1)]
    tl = {k: P['shapes'][c] for k, c in zip(keys, cols)}
    return assemble(P['bg'], tl, tsize(out))


def a_bottom_row_missing(inp, out):
    t = tsize(out)
    bg = parse(inp)['bg']
    g = [r[:] for r in out]
    for i in range(t + 1, 2 * t + 1):
        g[i] = [bg] * len(g[i])
    return g


def a_shift_right(inp, out):
    P = parse(inp)
    t = tsize(out)
    bg = P['bg']
    tl = {}
    for k, s in true_tiles(P).items():
        tl[k] = [[bg] + r[:-1] for r in s]
    return assemble(bg, tl, t)


def a_padded_tiles(inp, out):
    # tile crop taken with a one-cell margin around each shape
    P = parse(inp)
    bg = P['bg']
    t = tsize(out) + 2
    tl = {}
    for k, s in true_tiles(P).items():
        pad = [[bg] * (len(s[0]) + 2)] + [[bg] + r + [bg] for r in s] + [[bg] * (len(s[0]) + 2)]
        tl[k] = pad
    return assemble(bg, tl, t)


def a_legend_crop(inp, out):
    return parse(inp)['legend']


def a_shape_color_from_marker_tile(inp, out):
    # shapes keep the right tile but are painted with the color of the diagonal marker
    P = parse(inp)
    bg = P['bg']
    tl = {}
    for (r, c), col in P['quad'].items():
        other = P['quad'][(1 - r, 1 - c)]
        s = P['shapes'][col]
        tl[(r, c)] = [[other if v != bg else bg for v in row] for row in s]
    return assemble(bg, tl, tsize(out))


ALTERNATIVES = [
    ("tile layout transposed: marker at (row, col) fills tile (col, row)", a_transpose_layout),
    ("tile layout mirrored left-right", a_mirror_layout_lr),
    ("tile layout rotated 180 degrees", a_rotate_layout_180),
    ("each shape flipped horizontally inside its tile", a_shapes_flipped),
    ("each shape rotated 90 degrees inside its tile", a_shapes_rotated),
    ("tiles abutted with no gap (6x6 output)", a_no_gap),
    ("gap row and column filled with the legend frame color", a_gap_frame_color),
    ("shapes assigned to tiles by their reading order in the input, not by legend marker", a_reading_order_of_shapes),
    ("bottom row of tiles left empty", a_bottom_row_missing),
    ("each shape shifted one cell right inside its tile", a_shift_right),
    ("shape crop taken with a one-cell margin, giving 5x5 tiles (11x11 output)", a_padded_tiles),
    ("output is the legend crop itself", a_legend_crop),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if any(len(r) != len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/7d18a6fb.json'))
    pairs = task['train']
    print('pairs', len(pairs), 'readings', len(ALTERNATIVES))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p['input'], p['output'])
            except Exception as e:
                print('  error', desc, repr(e))
                g = None
            if g is not None and valid(g, p['output']):
                n += 1
        print(n, desc)
