import json
from pathlib import Path


def _cross(inp):
    h, w = len(inp), len(inp[0])
    rows = [r for r in range(h) if all(v != 0 for v in inp[r])]
    cols = [c for c in range(w) if all(inp[r][c] != 0 for r in range(h))]
    if len(rows) != 1 or len(cols) != 1:
        return None
    return rows[0], cols[0]


def _copy(g):
    return [list(r) for r in g]


def _ring(r, c, rad):
    return [(r + dr, c + dc) for dr in range(-rad, rad + 1) for dc in range(-rad, rad + 1)
            if max(abs(dr), abs(dc)) == rad]


def _paint(inp, cells, color, only_bg=False):
    g = _copy(inp)
    for (r, c) in cells:
        if 0 <= r < len(g) and 0 <= c < len(g[0]):
            if only_bg and g[r][c] != 0:
                continue
            g[r][c] = color
    return g


def orth_only(inp, out):
    r, c = _cross(inp)
    g = _copy(out)
    for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        g[r + dr][c + dc] = inp[r + dr][c + dc]
    return g


def bg_only(inp, out):
    r, c = _cross(inp)
    return _paint(inp, _ring(r, c, 1), 4, only_bg=True)


def radius2(inp, out):
    r, c = _cross(inp)
    return _paint(inp, _ring(r, c, 2), 4)


def filled(inp, out):
    r, c = _cross(inp)
    return _paint(inp, _ring(r, c, 1) + [(r, c)], 4)


def vert_color(inp, out):
    r, c = _cross(inp)
    return _paint(inp, _ring(r, c, 1), inp[0][c] if inp[r][c] != inp[0][c] else inp[r][0])


def around_all_line_cells(inp, out):
    h, w = len(inp), len(inp[0])
    r, c = _cross(inp)
    cells = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] != 0:
                cells += [(i + a, j + b) for a in (-1, 0, 1) for b in (-1, 0, 1)]
    return _paint(inp, cells, 4, only_bg=True)


def offset_center(inp, out):
    r, c = _cross(inp)
    return _paint(inp, _ring(r + 1, c, 1), 4)


def only_ring(inp, out):
    r, c = _cross(inp)
    ring = set(_ring(r, c, 1)) | {(r, c)}
    return [[out[i][j] if (i, j) in ring else 0 for j in range(len(out[0]))] for i in range(len(out))]


def upper_half(inp, out):
    r, c = _cross(inp)
    g = _copy(out)
    for (i, j) in _ring(r, c, 1):
        if i > r:
            g[i][j] = inp[i][j]
    return g


def unchanged(inp, out):
    return _copy(inp)


def swap_center(inp, out):
    r, c = _cross(inp)
    g = _copy(out)
    a, b = inp[r][0], inp[0][c]
    # the center shows one line color; swap to the other
    g[r][c] = b if out[r][c] == a else a
    return g


ALTERNATIVES = [
    ("ring covers only the 4 orthogonal neighbours of the crossing", lambda i, o: _rm(i, o, orth_only)),
    ("ring paints only background cells, so line cells next to the crossing keep their color", lambda i, o: _rm(i, o, bg_only)),
    ("ring has radius 2 (5x5 border) instead of 3x3", lambda i, o: _rm(i, o, radius2)),
    ("3x3 block including the crossing cell is filled with 4", lambda i, o: _rm(i, o, filled)),
    ("ring takes a line color instead of 4", lambda i, o: _rm(i, o, vert_color)),
    ("every background cell adjacent to any line cell gets 4", lambda i, o: _rm(i, o, around_all_line_cells)),
    ("ring is centered one row below the crossing", lambda i, o: _rm(i, o, offset_center)),
    ("output keeps only the ring and crossing; line remainder erased", lambda i, o: _rm(i, o, only_ring)),
    ("ring drawn only on the crossing row and the rows above", lambda i, o: _rm(i, o, upper_half)),
    ("crossing cell shows the other line's color", lambda i, o: _rm(i, o, swap_center)),
    ("grid returned unchanged", lambda i, o: _rm(i, o, unchanged)),
]


def _rm(inp, out, f):
    if _cross(inp) is None:
        return None
    return f(inp, out)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/67a423a3.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            ok = (g is not None and len(g) > 0 and all(len(r) == len(g[0]) for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != p['output'])
            n += ok
        print(n, desc)
