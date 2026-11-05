import json
from collections import Counter
from pathlib import Path

PW, STRIDE = 5, 6


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _sep(inp):
    return inp[0][PW]


def _panels(inp):
    n = (len(inp[0]) + 1) // STRIDE
    return [[r[STRIDE * k:STRIDE * k + PW] for r in inp] for k in range(n)]


def _comps(p, bg):
    h, w = len(p), len(p[0])
    seen, res = set(), []
    for r in range(h):
        for c in range(w):
            if (r, c) in seen or p[r][c] == bg:
                continue
            col = p[r][c]
            st = [(r, c)]
            seen.add((r, c))
            cells = []
            while st:
                a, b = st.pop()
                cells.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and (x, y) not in seen and p[x][y] == col:
                        seen.add((x, y))
                        st.append((x, y))
            res.append((col, cells))
    return res


def _by_col(shapes):
    return sorted(shapes, key=lambda s: min((c, r) for r, c in s[1]))


def _by_row(shapes):
    return sorted(shapes, key=lambda s: min(s[1]))


def _compose(inp, chooser, order=_by_col, fill=None, paint=None):
    """chooser(k, n, shapes) -> shape or None; paints picks onto a bg panel."""
    bg = fill if fill is not None else _bg(inp)
    ps = _panels(inp)
    out = [[bg] * PW for _ in range(PW)]
    for k, p in enumerate(ps):
        shapes = order(_comps(p, _bg(inp)))
        s = chooser(k, len(ps), shapes)
        if s is None:
            continue
        col, cells = s
        for r, c in cells:
            out[r][c] = col if paint is None else paint
    return out


def diag(k, n, shapes):
    return shapes[k % len(shapes)]


def anti_diagonal(inp, out):
    return _compose(inp, lambda k, n, s: s[(n - 1 - k) % len(s)])


def always_first(inp, out):
    return _compose(inp, lambda k, n, s: s[0])


def row_order(inp, out):
    return _compose(inp, diag, order=_by_row)


def shifted(inp, out):
    return _compose(inp, lambda k, n, s: s[(k + 1) % len(s)])


def drop_last_panel(inp, out):
    return _compose(inp, lambda k, n, s: None if k == n - 1 else diag(k, n, s))


def sep_background(inp, out):
    return _compose(inp, diag, fill=_sep(inp))


def sep_colored(inp, out):
    return _compose(inp, diag, paint=_sep(inp))


def keep_wide(inp, out):
    bg = _bg(inp)
    ps = _panels(inp)
    res = [list(r) for r in inp]
    keep = set()
    for k, p in enumerate(ps):
        s = _by_col(_comps(p, bg))[k]
        keep |= {(r, STRIDE * k + c) for r, c in s[1]}
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if c % STRIDE != PW and (r, c) not in keep:
                res[r][c] = bg
    return res


def mirror(inp, out):
    return [r[::-1] for r in out]


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def largest(inp, out):
    return _compose(inp, lambda k, n, s: max(s, key=lambda x: len(x[1])))


def all_shapes(inp, out):
    bg = _bg(inp)
    res = [[bg] * PW for _ in range(PW)]
    for p in _panels(inp):
        for col, cells in _comps(p, bg):
            for r, c in cells:
                res[r][c] = col
    return res


def bbox_filled(inp, out):
    bg = _bg(inp)
    res = [[bg] * PW for _ in range(PW)]
    for k, p in enumerate(_panels(inp)):
        col, cells = _by_col(_comps(p, bg))[k]
        r0, r1 = min(r for r, c in cells), max(r for r, c in cells)
        c0, c1 = min(c for r, c in cells), max(c for r, c in cells)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                res[r][c] = col
    return res


def _distinct(f):
    def g(inp, out):
        r = f(inp, out)
        return None if r == out else r
    return g


_RAW = [
    ("panel k contributes its (n-1-k)-th shape (anti-diagonal pick)", anti_diagonal),
    ("every panel contributes its leftmost shape", always_first),
    ("shapes ordered top-to-bottom instead of left-to-right", row_order),
    ("panel k contributes its (k+1)-th shape (off-by-one index)", shifted),
    ("last panel contributes nothing", drop_last_panel),
    ("background filled with the separator color", sep_background),
    ("picked shapes painted in the separator color", sep_colored),
    ("output keeps the full input width with only picked shapes left in place", keep_wide),
    ("true output mirrored left-to-right", mirror),
    ("true output transposed", transpose),
    ("each panel contributes its largest shape", largest),
    ("all shapes of all panels overlaid, no selection", all_shapes),
]
ALTERNATIVES = [(d, _distinct(f)) for d, f in _RAW]


def _valid(g, ref):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != ref)


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/5ecac7f7.json'))
    pairs = task['train']
    print('pairs', len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for ex in pairs:
            g = f(ex['input'], ex['output'])
            if g is not None and _valid(g, ex['output']):
                n += 1
        print(n, desc)
