import json
from collections import Counter
from pathlib import Path

DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1)]


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(c for r in inp for c in r)
    bg = cnt.most_common(1)[0][0]
    eye_col = min(cnt, key=lambda c: (cnt[c], c))
    eye = next((i, j) for i in range(h) for j in range(w) if inp[i][j] == eye_col)
    d = None
    for dd in DIRS:
        i, j = eye[0] + dd[0], eye[1] + dd[1]
        if 0 <= i < h and 0 <= j < w and inp[i][j] != bg and inp[i][j] != eye_col:
            d = dd
    lens = inp[eye[0] + d[0]][eye[1] + d[1]]
    speck = next(c for c in cnt if c not in (bg, eye_col, lens))
    return h, w, bg, eye_col, eye, d, lens, speck


def _ray(h, w, eye, d):
    cells = []
    i, j = eye[0] + d[0], eye[1] + d[1]
    while 0 <= i < h and 0 <= j < w:
        cells.append((i, j))
        i, j = i + d[0], j + d[1]
    return cells


def _flood(inp, seeds, speck, diag=False):
    h, w = len(inp), len(inp[0])
    nb = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diag:
        nb += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    seen = set()
    stack = [s for s in seeds if inp[s[0]][s[1]] == speck]
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        for a, b in nb:
            q = (p[0] + a, p[1] + b)
            if 0 <= q[0] < h and 0 <= q[1] < w and inp[q[0]][q[1]] == speck and q not in seen:
                stack.append(q)
    return seen


def _erase(inp, cells, bg):
    g = [r[:] for r in inp]
    for i, j in cells:
        g[i][j] = bg
    return g


def only_ray_cells(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    return _erase(inp, [p for p in _ray(h, w, eye, d) if inp[p[0]][p[1]] == sp], bg)


def diag_connect(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    g = _erase(inp, _flood(inp, _ray(h, w, eye, d), sp, True), bg)
    return g if g != out else None


def opposite_dir(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    od = (-d[0], -d[1])
    return _erase(inp, _flood(inp, _ray(h, w, eye, od), sp), bg)


def all_specks(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    return _erase(inp, [(i, j) for i in range(h) for j in range(w) if inp[i][j] == sp], bg)


def both_directions(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    od = (-d[0], -d[1])
    cells = _ray(h, w, eye, d) + _ray(h, w, eye, od)
    g = _erase(inp, _flood(inp, cells, sp), bg)
    return g if g != out else None


def first_hit_only(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    for p in _ray(h, w, eye, d):
        if inp[p[0]][p[1]] == sp:
            return _erase(inp, _flood(inp, [p], sp), bg)
    return None


def lens_erased(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    return _erase(out, [(i, j) for i in range(h) for j in range(w) if inp[i][j] == lens], bg)


def eye_erased(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    return _erase(out, [eye], bg)


def perpendicular_dir(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    pd = (d[1], -d[0])
    return _erase(inp, _flood(inp, _ray(h, w, eye, pd), sp), bg)


def fill_with_lens(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    g = [r[:] for r in out]
    for i in range(h):
        for j in range(w):
            if inp[i][j] != out[i][j]:
                g[i][j] = lens
    return g


def thick_beam(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    cells = []
    for k in (-1, 0, 1):
        o = (eye[0] + k * d[1], eye[1] + k * d[0])
        if 0 <= o[0] < h and 0 <= o[1] < w:
            cells += _ray(h, w, o, d)
    return _erase(inp, _flood(inp, cells, sp), bg)


def half_ray(inp, out):
    h, w, bg, e, eye, d, lens, sp = _parse(inp)
    cells = _ray(h, w, eye, d)
    return _erase(inp, _flood(inp, cells[:len(cells) // 2], sp), bg)


ALTERNATIVES = [
    ("erase only the specks on the ray line, not their whole components", only_ray_cells),
    ("erase components touched by the ray using 8-connectivity", diag_connect),
    ("ray points away from the lens cell instead of through it", opposite_dir),
    ("erase every speck in the grid", all_specks),
    ("ray runs both ways from the eye, erasing touched components on both sides", both_directions),
    ("erase only the first component the ray touches", first_hit_only),
    ("correct erasure but the lens cells are also erased", lens_erased),
    ("correct erasure but the eye cell is also erased", eye_erased),
    ("ray goes perpendicular to the lens direction", perpendicular_dir),
    ("erased cells are painted with the lens color instead of background", fill_with_lens),
    ("beam is three cells wide, centered on the eye", thick_beam),
    ("ray reaches only half of its length to the grid edge", half_ray),
]


def _valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r) and g != out
    )


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/2f767503.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(n, desc)
