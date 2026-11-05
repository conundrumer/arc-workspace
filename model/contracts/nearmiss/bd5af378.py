"""Near-miss rules for ARC task bd5af378.

Rule: an L (one full row and column in one grid corner) sits in a field. The L
steps `shift` cells inward along the corner's diagonal. Cells nearer than
`shift` to either L edge take the field color; the L reappears at distance
`shift`; everything farther in takes a fill color. On the corner's diagonal,
cells up to distance `shift` take the fill color and cells beyond take the
field color.
"""
import json
from pathlib import Path


def parse(inp, out):
    H, W = len(inp), len(inp[0])
    for cr in (0, H - 1):
        for cc in (0, W - 1):
            L = inp[cr][cc]
            if (all(inp[cr][c] == L for c in range(W))
                    and all(inp[r][cc] == L for r in range(H))):
                ir = cr + (1 if cr == 0 else -1)
                ic = cc + (1 if cc == 0 else -1)
                if inp[ir][ic] != L:
                    field = inp[ir][ic]
                    fill = out[cr][cc]
                    s = 0
                    while True:
                        r = cr + (s + 1) * (1 if cr == 0 else -1)
                        c = cc + (s + 1) * (1 if cc == 0 else -1)
                        if 0 <= r < H and 0 <= c < W and out[r][c] == fill:
                            s += 1
                        else:
                            break
                    return H, W, cr, cc, L, field, fill, s
    raise ValueError("no corner")


def render(H, W, cr, cc, L, F, Fill, band, lpos, diagext, diagfar=None,
           drop_arm=None, band_color=None, inner=None):
    """band: cells with min distance < band take F (off the diagonal).
    lpos: min distance at which the L is drawn. diagext: diagonal cells up to
    this distance take Fill. diagfar: color of farther diagonal cells."""
    if diagfar is None:
        diagfar = F
    if band_color is None:
        band_color = F
    g = []
    for r in range(H):
        row = []
        for c in range(W):
            dr, dc = abs(r - cr), abs(c - cc)
            a, b = min(dr, dc), max(dr, dc)
            if dr == dc:
                v = Fill if a <= diagext else diagfar
            elif a < band:
                v = band_color
            elif a == lpos:
                v = L
                if drop_arm == 'row' and dr == lpos:
                    v = Fill
                if drop_arm == 'col' and dc == lpos:
                    v = Fill
            elif a > lpos:
                v = Fill if inner is None else inner
            else:
                v = F
            row.append(v)
        g.append(row)
    return g


def _p(f):
    def w(inp, out):
        H, W, cr, cc, L, F, Fill, S = parse(inp, out)
        return f(inp, out, H, W, cr, cc, L, F, Fill, S)
    return w


@_p
def no_shift(inp, out, H, W, cr, cc, L, F, Fill, S):
    return render(H, W, cr, cc, L, F, Fill, 0, 0, 0)


@_p
def shift_plus1(inp, out, H, W, cr, cc, L, F, Fill, S):
    s = S + 1
    return render(H, W, cr, cc, L, F, Fill, s, s, s)


@_p
def swap_l_fill(inp, out, H, W, cr, cc, L, F, Fill, S):
    m = {L: Fill, Fill: L}
    return [[m.get(v, v) for v in row] for row in out]


@_p
def fill_is_field(inp, out, H, W, cr, cc, L, F, Fill, S):
    return [[F if v == Fill else v for v in row] for row in out]


@_p
def diag_all_fill(inp, out, H, W, cr, cc, L, F, Fill, S):
    return render(H, W, cr, cc, L, F, Fill, S, S, 99, diagfar=Fill)


@_p
def diag_short(inp, out, H, W, cr, cc, L, F, Fill, S):
    return render(H, W, cr, cc, L, F, Fill, S, S, S - 1)


@_p
def one_arm_only(inp, out, H, W, cr, cc, L, F, Fill, S):
    return render(H, W, cr, cc, L, F, Fill, S, S, S, drop_arm='row')


@_p
def band_keeps_l(inp, out, H, W, cr, cc, L, F, Fill, S):
    return render(H, W, cr, cc, L, F, Fill, S, S, S, band_color=L)


@_p
def l_gap(inp, out, H, W, cr, cc, L, F, Fill, S):
    return render(H, W, cr, cc, L, F, Fill, S, S + 1, S)


@_p
def interior_unfilled(inp, out, H, W, cr, cc, L, F, Fill, S):
    return render(H, W, cr, cc, L, F, Fill, S, S, S, inner=F)


@_p
def wrong_corner(inp, out, H, W, cr, cc, L, F, Fill, S):
    g = render(H, W, cr, cc, L, F, Fill, S, S, S)
    return g[::-1] if H > 1 and cr == 0 or cr == H - 1 else g


@_p
def diag_far_is_l(inp, out, H, W, cr, cc, L, F, Fill, S):
    return render(H, W, cr, cc, L, F, Fill, S, S, S, diagfar=L)


ALTERNATIVES = [
    ("L does not step in (shift 0): L stays on the edge, rest is fill", no_shift),
    ("shift one too large (S+1) for band, L and diagonal", shift_plus1),
    ("L color and fill color exchanged in the output", swap_l_fill),
    ("fill region left as field color (fill never applied)", fill_is_field),
    ("whole corner diagonal takes fill color, not only up to shift", diag_all_fill),
    ("diagonal fill stops one cell short of shift", diag_short),
    ("only one arm of the L steps in; the other arm becomes fill", one_arm_only),
    ("edge band keeps the L color instead of the field color", band_keeps_l),
    ("L steps in one further than the field band, leaving a field gap", l_gap),
    ("cells inside the L fill region stay field color but L steps in", interior_unfilled),
    ("render mirrored vertically, as if the L were at the opposite edge", wrong_corner),
    ("far diagonal cells take the L color instead of the field color", diag_far_is_l),
]


def _valid(g, out):
    if g is None:
        return False
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/bd5af378.json').read_text())
    pairs = task['train']
    # sanity: the true rule reproduces every output
    for p in pairs:
        H, W, cr, cc, L, F, Fill, S = parse(p['input'], p['output'])
        assert render(H, W, cr, cc, L, F, Fill, S, S, S) == p['output']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, f in ALTERNATIVES:
        n = sum(_valid(f(p['input'], p['output']), p['output']) for p in pairs)
        print(n, desc)
