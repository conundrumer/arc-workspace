import json
from collections import Counter
from pathlib import Path

T = 2  # tile side
G = 1  # gap between tiles


def parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for row in inp for v in row if v)
    tc = cnt.most_common(1)[0][0]
    rows = [r for r in range(h) for c in range(w) if inp[r][c] == tc]
    cols = [c for r in range(h) for c in range(w) if inp[r][c] == tc]
    r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
    nr = (r1 - r0 + 1 + G) // (T + G)
    nc = (c1 - c0 + 1 + G) // (T + G)
    codes = {}
    for ti in range(nr):
        for tj in range(nc):
            r, c = r0 + ti * (T + G), c0 + tj * (T + G)
            for dr in range(T):
                for dc in range(T):
                    v = inp[r + dr][c + dc]
                    if v not in (0, tc):
                        codes[(ti, tj)] = v
    legend = []  # (color, shape, marker row, marker col), left to right
    ink = 1
    for r in range(r0):
        for c in range(w):
            v = inp[r][c]
            if v not in (0, ink):
                legend.append((v, r, c))
    legend.sort(key=lambda x: x[2])
    return dict(h=h, w=w, tc=tc, r0=r0, c0=c0, r1=r1, c1=c1, nr=nr, nc=nc,
                codes=codes, legend=legend, ink=ink)


def box_shape(inp, r, c, dc=1):
    return [[1 if inp[r + 1 + i][c + dc + j] == 1 else 0 for j in range(T)]
            for i in range(T)]


def shape_map(inp, P, dc=1):
    return {col: box_shape(inp, r, c, dc) for col, r, c in P['legend']}


def render(P, tile_fn, gap_fill=0):
    H = P['nr'] * T + (P['nr'] - 1) * G
    W = P['nc'] * T + (P['nc'] - 1) * G
    g = [[gap_fill] * W for _ in range(H)]
    for ti in range(P['nr']):
        for tj in range(P['nc']):
            cells = tile_fn(ti, tj)
            for i in range(T):
                for j in range(T):
                    g[ti * (T + G) + i][tj * (T + G) + j] = cells[i][j]
    return g


def paint(shape, color, off=0):
    return [[color if shape[i][j] else off for j in range(T)] for i in range(T)]


def blank(v=0):
    return [[v] * T for _ in range(T)]


def raw_tile(inp, P, ti, tj):
    r, c = P['r0'] + ti * (T + G), P['c0'] + tj * (T + G)
    return [[inp[r + i][c + j] for j in range(T)] for i in range(T)]


def out_tiles(out, P):
    def f(ti, tj):
        r, c = ti * (T + G), tj * (T + G)
        return [[out[r + i][c + j] for j in range(T)] for i in range(T)]
    return f


def alt_crop_only(inp, out):
    P = parse(inp)
    return render(P, lambda ti, tj: raw_tile(inp, P, ti, tj))


def alt_tile_color_ink(inp, out):
    P = parse(inp)
    sm = shape_map(inp, P)
    return render(P, lambda ti, tj: paint(sm[P['codes'][(ti, tj)]], P['tc'])
                  if (ti, tj) in P['codes'] else blank())


def alt_blank_keeps_tile(inp, out):
    P = parse(inp)
    sm = shape_map(inp, P)
    return render(P, lambda ti, tj: paint(sm[P['codes'][(ti, tj)]], P['codes'][(ti, tj)])
                  if (ti, tj) in P['codes'] else blank(P['tc']))


def alt_gap_filled(inp, out):
    P = parse(inp)
    f = out_tiles(out, P)
    return render(P, f, gap_fill=P['tc'])


def alt_margin(inp, out):
    w = len(out[0])
    return [[0] * (w + 2)] + [[0] + list(r) + [0] for r in out] + [[0] * (w + 2)]


def alt_flip_h(inp, out):
    P = parse(inp)
    f = out_tiles(out, P)
    return render(P, lambda ti, tj: [row[::-1] for row in f(ti, tj)])


def alt_transpose(inp, out):
    P = parse(inp)
    f = out_tiles(out, P)
    return render(P, lambda ti, tj: [list(r) for r in zip(*f(ti, tj))])


def alt_next_marker(inp, out):
    P = parse(inp)
    sm = shape_map(inp, P)
    order = [col for col, _, _ in P['legend']]
    nxt = {order[i]: order[(i + 1) % len(order)] for i in range(len(order))}
    return render(P, lambda ti, tj: paint(sm[nxt[P['codes'][(ti, tj)]]], P['codes'][(ti, tj)])
                  if (ti, tj) in P['codes'] else blank())


def alt_box_shifted(inp, out):
    P = parse(inp)
    sm = shape_map(inp, P, dc=0)
    return render(P, lambda ti, tj: paint(sm[P['codes'][(ti, tj)]], P['codes'][(ti, tj)])
                  if (ti, tj) in P['codes'] else blank())


def alt_first_only(inp, out):
    P = parse(inp)
    f = out_tiles(out, P)
    first = min(P['codes'])
    return render(P, lambda ti, tj: f(ti, tj) if (ti, tj) == first else blank())


def alt_all_common(inp, out):
    P = parse(inp)
    sm = shape_map(inp, P)
    col = Counter(P['codes'].values()).most_common(1)[0][0]
    return render(P, lambda ti, tj: paint(sm[col], col))


def alt_inverted(inp, out):
    P = parse(inp)
    sm = shape_map(inp, P)

    def f(ti, tj):
        if (ti, tj) not in P['codes']:
            return blank()
        col = P['codes'][(ti, tj)]
        return [[0 if sm[col][i][j] else col for j in range(T)] for i in range(T)]
    return render(P, f)


ALTERNATIVES = [
    ("crop to the tile region but leave tiles and codes as in the input, no shape stamped", alt_crop_only),
    ("stamp each shape in the tile color instead of the code color", alt_tile_color_ink),
    ("stamp shapes but leave code-less tiles filled with the tile color", alt_blank_keeps_tile),
    ("stamp shapes correctly but fill the gaps between tiles with the tile color", alt_gap_filled),
    ("output has an extra background margin of one cell around the tile region", alt_margin),
    ("each stamped shape is mirrored left to right inside its tile", alt_flip_h),
    ("each stamped shape is transposed inside its tile", alt_transpose),
    ("a code names the shape of the next marker to the right (cyclic) instead of its own", alt_next_marker),
    ("legend box read one column too far left, so shapes are shifted right", alt_box_shifted),
    ("only the first code tile in reading order is stamped, the rest blanked", alt_first_only),
    ("every tile gets the shape of the commonest code color", alt_all_common),
    ("shape inverted: its holes are inked and its cells left background", alt_inverted),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/c64f1187.json'))
    train = task['train']
    print(len(ALTERNATIVES), 'readings,', len(train), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(n, desc)
