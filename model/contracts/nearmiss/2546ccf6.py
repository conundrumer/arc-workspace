import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _runs(flags):
    runs, start = [], None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        if not f and start is not None:
            runs.append((start, i))
            start = None
    return runs


def _layout(inp):
    """Return (bg, divider color, row runs, col runs) of the tile grid."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    div = None
    for r in range(h):
        if len(set(inp[r])) == 1 and inp[r][0] != bg:
            div = inp[r][0]
    if div is None:
        return None
    rdiv = [all(v == div for v in inp[r]) for r in range(h)]
    cdiv = [all(inp[r][c] == div for r in range(h)) for c in range(w)]
    rr = _runs([not x for x in rdiv])
    cr = _runs([not x for x in cdiv])
    return bg, div, rr, cr


def _tile(g, rr, cr, i, j):
    return [row[cr[j][0]:cr[j][1]] for row in g[rr[i][0]:rr[i][1]]]


def _put(g, rr, cr, i, j, t):
    g = [row[:] for row in g]
    for a, row in enumerate(t):
        for b, v in enumerate(row):
            g[rr[i][0] + a][cr[j][0] + b] = v
    return g


def _hflip(t):
    return [r[::-1] for r in t]


def _vflip(t):
    return t[::-1]


def _info(inp, out):
    """Find the missing tile and its diagonal, horizontal, vertical neighbors."""
    lay = _layout(inp)
    if lay is None:
        return None
    bg, div, rr, cr = lay
    filled = {}
    for i in range(len(rr)):
        for j in range(len(cr)):
            filled[(i, j)] = any(v != bg for row in _tile(inp, rr, cr, i, j) for v in row)
    miss = None
    for (i, j), f in filled.items():
        if not f and _tile(out, rr, cr, i, j) != _tile(inp, rr, cr, i, j):
            miss = (i, j)
    if miss is None:
        return None
    i, j = miss
    for di in (-1, 1):
        for dj in (-1, 1):
            if filled.get((i + di, j + dj)) and filled.get((i, j + dj)) and filled.get((i + di, j)):
                return dict(bg=bg, div=div, rr=rr, cr=cr, miss=miss, filled=filled,
                            D=(i + di, j + dj), H=(i, j + dj), V=(i + di, j))
    return None


def _fill_with(inp, out, pick):
    s = _info(inp, out)
    if s is None:
        return None
    t = pick(s, inp, out)
    if t is None:
        return None
    i, j = s['miss']
    return _put(inp, s['rr'], s['cr'], i, j, t)


def _src(s, inp, key):
    return _tile(inp, s['rr'], s['cr'], *s[key])


def unfilled(inp, out):
    return [r[:] for r in inp]


def copy_diag_plain(inp, out):
    return _fill_with(inp, out, lambda s, g, o: _src(s, g, 'D'))


def diag_hflip_only(inp, out):
    return _fill_with(inp, out, lambda s, g, o: _hflip(_src(s, g, 'D')))


def diag_vflip_only(inp, out):
    return _fill_with(inp, out, lambda s, g, o: _vflip(_src(s, g, 'D')))


def copy_h_neighbor_plain(inp, out):
    return _fill_with(inp, out, lambda s, g, o: _src(s, g, 'H'))


def copy_v_neighbor_plain(inp, out):
    return _fill_with(inp, out, lambda s, g, o: _src(s, g, 'V'))


def diag_transposed(inp, out):
    def pick(s, g, o):
        t = _src(s, g, 'D')
        if len(t) != len(t[0]):
            return None
        return [list(r) for r in zip(*t)]
    return _fill_with(inp, out, pick)


def paint_divider_color(inp, out):
    def pick(s, g, o):
        t = _tile(o, s['rr'], s['cr'], *s['miss'])
        return [[s['div'] if v != s['bg'] else v for v in r] for r in t]
    return _fill_with(inp, out, pick)


def fill_every_empty_tile(inp, out):
    s = _info(inp, out)
    if s is None:
        return None
    t = _tile(out, s['rr'], s['cr'], *s['miss'])
    g = [r[:] for r in inp]
    for (i, j), f in s['filled'].items():
        if not f:
            th = s['rr'][i][1] - s['rr'][i][0]
            tw = s['cr'][j][1] - s['cr'][j][0]
            if (th, tw) == (len(t), len(t[0])):
                g = _put(g, s['rr'], s['cr'], i, j, t)
    return g


def correct_patch_shifted_right(inp, out):
    def pick(s, g, o):
        t = _tile(o, s['rr'], s['cr'], *s['miss'])
        bg = s['bg']
        return [[bg] + r[:-1] for r in t]
    return _fill_with(inp, out, pick)


def move_not_copy(inp, out):
    s = _info(inp, out)
    if s is None:
        return None
    g = [r[:] for r in out]
    di, dj = s['D']
    blank = [[s['bg']] * (s['cr'][dj][1] - s['cr'][dj][0])
             for _ in range(s['rr'][di][1] - s['rr'][di][0])]
    return _put(g, s['rr'], s['cr'], di, dj, blank)


def solid_bounding_box(inp, out):
    def pick(s, g, o):
        t = _tile(o, s['rr'], s['cr'], *s['miss'])
        cells = [(a, b) for a, r in enumerate(t) for b, v in enumerate(r) if v != s['bg']]
        if not cells:
            return None
        col = t[cells[0][0]][cells[0][1]]
        a0, a1 = min(a for a, _ in cells), max(a for a, _ in cells)
        b0, b1 = min(b for _, b in cells), max(b for _, b in cells)
        return [[col if a0 <= a <= a1 and b0 <= b <= b1 else s['bg']
                 for b in range(len(t[0]))] for a in range(len(t))]
    return _fill_with(inp, out, pick)


ALTERNATIVES = [
    ("leave the missing tile empty (no completion)", unfilled),
    ("copy the diagonal tile into the missing tile without any flip", copy_diag_plain),
    ("copy the diagonal tile flipped left-right only", diag_hflip_only),
    ("copy the diagonal tile flipped up-down only", diag_vflip_only),
    ("copy the horizontally adjacent tile unchanged into the missing tile", copy_h_neighbor_plain),
    ("copy the vertically adjacent tile unchanged into the missing tile", copy_v_neighbor_plain),
    ("fill the missing tile with the diagonal tile transposed", diag_transposed),
    ("draw the correct shape in the divider color instead of the shape color", paint_divider_color),
    ("fill every empty tile with the completion, not only the one in the 2x2 block", fill_every_empty_tile),
    ("place the completion one cell too far right inside the tile", correct_patch_shifted_right),
    ("move the diagonal shape (erase it from its tile) instead of copying", move_not_copy),
    ("fill the bounding box of the completion solid", solid_bounding_box),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/2546ccf6.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(n, desc)
