"""Near-miss readings for ARC task f3e14006.

Rule model: two crossing lines (a bar line and a cross line), each with a base
color and two marks of its own color.  The output keeps a rectangle that
holds a woven lattice of holes and threads on the background.
"""
import json
from collections import Counter
from pathlib import Path


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _rect(out, bg):
    cells = [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v != bg]
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def _line_info(cells):
    """cells: list of (pos, color) off the crossing -> (base, mark, mark positions)."""
    cnt = Counter(v for _, v in cells)
    base = cnt.most_common(1)[0][0]
    mark = [v for v in cnt if v != base][0]
    return base, mark, sorted(p for p, v in cells if v == mark)


def _analyse(inp, out):
    """Return the parameters in an orientation where the bar line is a row."""
    h, w = len(inp), len(inp[0])
    bg = Counter(v for row in inp for v in row).most_common(1)[0][0]
    rcount = [sum(v != bg for v in row) for row in inp]
    ccount = [sum(inp[r][c] != bg for r in range(h)) for c in range(w)]
    R = rcount.index(max(rcount))
    C = ccount.index(max(ccount))
    X = inp[R][C]
    row_cells = [(c, inp[R][c]) for c in range(w) if inp[R][c] != bg and c != C]
    col_cells = [(r, inp[r][C]) for r in range(h) if inp[r][C] != bg and r != R]
    rbase, rmark, rpos = _line_info(row_cells)
    cbase, cmark, cpos = _line_info(col_cells)
    r0, r1, c0, c1 = _rect(out, bg)
    if (rpos[0], rpos[-1]) == (c0, c1):
        return dict(T=False, bg=bg, X=X, Rb=R, a=c0, b=c1, bbase=rbase, bmark=rmark,
                    cbase=cbase, cmark=cmark, p=cpos[0], q=cpos[-1], r0=r0, r1=r1,
                    h=h, w=w)
    return dict(T=True, bg=bg, X=X, Rb=C, a=r0, b=r1, bbase=cbase, bmark=cmark,
                cbase=rbase, cmark=rmark, p=rpos[0], q=rpos[-1], r0=c0, r1=c1,
                h=w, w=h)


def _build(inp, out, P=2, off_row=0, off_col=0, swap_marks=False, swap_bases=False,
           cross_other=False, hole_mode=None, span_adjust=None, rect_rows=None):
    """Forward model with switches for the wrong readings.  Works in the
    orientation where the bar line is a row, then maps back."""
    d = _analyse(inp, out)
    bg, X, Rb, a, b = d['bg'], d['X'], d['Rb'], d['a'], d['b']
    bbase, bmark, cbase, cmark = d['bbase'], d['bmark'], d['cbase'], d['cmark']
    p, q = d['p'], d['q']
    r0, r1 = d['r0'], d['r1']
    if rect_rows is not None:
        r0, r1 = rect_rows(d)
    if swap_marks:
        bmark, cmark = cmark, bmark
    if swap_bases:
        bbase, cbase = cbase, bbase
    cross_color = cbase if X == bbase else bbase
    hole_rows = [r for r in range(r0, r1 + 1) if (r - Rb - off_row) % P == 0]
    lo, hi = min(p, q), max(p, q)
    inspan = {r for r in hole_rows if lo <= r <= hi}
    if span_adjust == 'shrink' and inspan:
        inspan.discard(max(inspan, key=lambda r: abs(r - Rb)))
    elif span_adjust == 'extend':
        outside = [r for r in hole_rows if r not in inspan]
        if outside:
            inspan.add(min(outside, key=lambda r: max(lo - r, r - hi, 0)))
    g = [[bg] * d['w'] for _ in range(d['h'])]
    for r in range(r0, r1 + 1):
        for c in range(a, b + 1):
            hr = (r - Rb - off_row) % P == 0
            hc = (c - a - off_col) % P == 0
            if hr and hc:
                if hole_mode == 'bar':
                    v = bmark
                elif hole_mode == 'cross':
                    v = cmark
                else:
                    v = cmark if r in inspan else bmark
            elif hr:
                v = cbase
            elif hc:
                v = bbase
            else:
                v = cross_color if cross_other else X
            g[r][c] = v
    return _transpose(g) if d['T'] else g


def swap_hole_colors(inp, out):
    return _build(inp, out, swap_marks=True)


def swap_thread_colors(inp, out):
    return _build(inp, out, swap_bases=True)


def thread_crossing_other_base(inp, out):
    return _build(inp, out, cross_other=True)


def all_holes_bar_mark(inp, out):
    return _build(inp, out, hole_mode='bar')


def all_holes_cross_mark(inp, out):
    return _build(inp, out, hole_mode='cross')


def span_shrunk(inp, out):
    return _build(inp, out, span_adjust='shrink')


def span_extended(inp, out):
    return _build(inp, out, span_adjust='extend')


def period_three(inp, out):
    return _build(inp, out, P=3)


def hole_rows_offset(inp, out):
    return _build(inp, out, off_row=1)


def hole_cols_offset(inp, out):
    return _build(inp, out, off_col=1)


def rect_to_nearer_cross_mark(inp, out):
    def rows(d):
        near = min((d['p'], d['q']), key=lambda m: abs(m - d['Rb']))
        return min(near, d['Rb']), max(near, d['Rb'])
    return _build(inp, out, rect_rows=rows)


def rect_between_cross_marks(inp, out):
    def rows(d):
        return min(d['p'], d['q']), max(d['p'], d['q'])
    return _build(inp, out, rect_rows=rows)


ALTERNATIVES = [
    ("hole colors swapped: holes inside the cross span take the bar mark color, the others the cross mark color", swap_hole_colors),
    ("thread colors swapped: bar threads take the cross base color and cross threads the bar base color", swap_thread_colors),
    ("where two threads cross, the cell takes the other line's base color than the input crossing cell shows", thread_crossing_other_base),
    ("cross span ignored: every hole takes the bar line's mark color", all_holes_bar_mark),
    ("cross span ignored: every hole takes the cross line's mark color", all_holes_cross_mark),
    ("cross span too short: the hole line farthest from the bar line counts as outside the span", span_shrunk),
    ("cross span too long: the nearest hole line outside the span counts as inside it", span_extended),
    ("lattice period 3 in place of 2", period_three),
    ("hole lines along the bar axis start one line away from the bar line", hole_rows_offset),
    ("hole lines across the bar axis start one line in from the rectangle edge", hole_cols_offset),
    ("rectangle reaches only to the nearer mark of the cross line", rect_to_nearer_cross_mark),
    ("rectangle spans only between the two cross marks, leaving out the bar line", rect_between_cross_marks),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/f3e14006.json').read_text())
    train = task['train']
    # the forward model with no switches reproduces the true output
    for i, pair in enumerate(train):
        assert _build(pair['input'], pair['output']) == pair['output'], i
    print('task f3e14006:', len(ALTERNATIVES), 'readings,', len(train), 'train pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for pair in train:
            g = fn(pair['input'], pair['output'])
            if g is not None and _valid(g, pair['output']):
                n += 1
        print(f'{n}/{len(train)}  {desc}')
