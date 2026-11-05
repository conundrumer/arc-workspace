import json
from collections import Counter
from pathlib import Path

FILL = 4


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for row in inp for v in row if v != 0)
    mark = min(cnt, key=lambda v: cnt[v])
    ink = max(cnt, key=lambda v: cnt[v])
    zc = [all(inp[r][c] == 0 for r in range(h)) for c in range(w)]
    zr = [all(inp[r][c] == 0 for c in range(w)) for r in range(h)]

    def interior(z):
        idx = [i for i, v in enumerate(z) if not v]
        return any(z[i] for i in range(idx[0], idx[-1] + 1))

    cols_are_bands = interior(zc)
    z = zc if cols_are_bands else zr
    band = []
    n = -1
    prev = True
    for v in z:
        if not v and prev:
            n += 1
        band.append(-1 if v else n)
        prev = v
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == mark]
    co = (lambda r, c: (c, r)) if cols_are_bands else (lambda r, c: (r, c))
    bs = [co(r, c) for r, c in cells]
    mb = band[bs[0][0]]
    p0 = min(p for _, p in bs)
    p1 = max(p for _, p in bs)
    q0 = min(b for b, _ in bs)
    q1 = max(b for b, _ in bs)
    return dict(h=h, w=w, mark=mark, ink=ink, band=band, mb=mb, p0=p0, p1=p1,
                q0=q0, q1=q1, co=co, nb=n + 1)


def _units(p, p0, p1, s, rnd=True):
    if p < p0:
        d = p0 - p
    elif p > p1:
        d = p - p1
    else:
        return 0
    return -(-d // s) if rnd else d // s


def _render(inp, cond, fill=FILL):
    P = _parse(inp)
    out = [row[:] for row in inp]
    for r in range(P['h']):
        for c in range(P['w']):
            if inp[r][c] != P['ink']:
                continue
            b, p = P['co'](r, c)
            if cond(P, b, p, r, c):
                out[r][c] = fill
    return out


def _d(P, b):
    return abs(P['band'][b] - P['mb'])


def _k(P, p, s=None, rnd=True):
    s = s or (P['p1'] - P['p0'] + 1)
    return _units(p, P['p0'], P['p1'], s, rnd)


# true cone: band distance d >= 1 and perpendicular unit distance k >= d
def true_cond(P, b, p, r, c):
    d = _d(P, b)
    return d >= 1 and _k(P, p) >= d


def strict(inp, out):
    return _render(inp, lambda P, b, p, r, c: _d(P, b) >= 1 and _k(P, p) > _d(P, b))


def wide(inp, out):
    return _render(inp, lambda P, b, p, r, c: _d(P, b) >= 1 and _k(P, p) + 1 >= _d(P, b))


def cell_step(inp, out):
    return _render(inp, lambda P, b, p, r, c: _d(P, b) >= 1 and _k(P, p, 1) >= _d(P, b))


def pitch_step(inp, out):
    return _render(inp, lambda P, b, p, r, c: _d(P, b) >= 1 and _k(P, p, 3) >= _d(P, b))


def floor_units(inp, out):
    return _render(inp, lambda P, b, p, r, c: _d(P, b) >= 1 and _k(P, p, rnd=False) >= _d(P, b))


def marker_band_too(inp, out):
    return _render(inp, lambda P, b, p, r, c: _k(P, p) >= _d(P, b))


def inside_cone(inp, out):
    return _render(inp, lambda P, b, p, r, c: _d(P, b) >= 1 and _k(P, p) < _d(P, b))


def swapped_axes(inp, out):
    return _render(inp, lambda P, b, p, r, c: _k(P, p) >= 1 and _d(P, b) >= _k(P, p))


def one_side(inp, out):
    def cond(P, b, p, r, c):
        return _d(P, b) >= 1 and p < P['p0'] and _k(P, p) >= _d(P, b)
    return _render(inp, cond)


def all_off_band(inp, out):
    return _render(inp, lambda P, b, p, r, c: _d(P, b) >= 1)


def wrong_color(inp, out):
    P = _parse(inp)
    return _render(inp, true_cond, fill=P['mark'])


def marker_lost(inp, out):
    P = _parse(inp)
    return [[P['ink'] if v == P['mark'] else v for v in row] for row in out]


ALTERNATIVES = [
    ("cone edge is exclusive: fill only where perpendicular units exceed band distance", strict),
    ("cone one unit too wide: fill where perpendicular units + 1 reach band distance", wide),
    ("perpendicular distance counted in single cells, not marker-size steps", cell_step),
    ("perpendicular distance counted in band pitch (band plus divider) steps", pitch_step),
    ("perpendicular distance rounded down instead of up, an offset of one", floor_units),
    ("marker's own band is also filled outside the marker", marker_band_too),
    ("fill is put inside the cone and the outside stays unchanged", inside_cone),
    ("band distance and perpendicular distance swap roles in the cone test", swapped_axes),
    ("only the side before the marker is filled", one_side),
    ("every ink cell outside the marker's band is filled, with no cone", all_off_band),
    ("cone is filled with the marker color", wrong_color),
    ("fill pattern is right but the marker block is overwritten with ink", marker_lost),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/7d419a02.json'))
    pairs = task['train']
    for p in pairs:
        assert _render(p['input'], true_cond) == p['output'], 'true rule mismatch'
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(f'{n}/{len(pairs)}  {desc}')
