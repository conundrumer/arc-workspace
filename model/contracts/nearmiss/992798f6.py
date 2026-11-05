"""Near-miss readings for ARC task 992798f6.

Rule: a mark of color 1 (D) and a mark of color 2 (S) sit on a background.
A path of color 3 leaves D diagonally toward S and stops on the last cell
that is not on S's row or column (the elbow E).  From E a straight leg runs
along the line it is on, to the cell that touches S diagonally (the tip T).
"""
import json
from pathlib import Path

PATH = 3


def _find(inp, color):
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == color:
                return (r, c)
    return None


def _sign(x):
    return (x > 0) - (x < 0)


def _geom(inp, d_color=1, s_color=2):
    """Return D, S, diagonal step, elbow E, tip T, diagonal cell count k."""
    D = _find(inp, d_color)
    S = _find(inp, s_color)
    if D is None or S is None:
        return None
    dy, dx = _sign(S[0] - D[0]), _sign(S[1] - D[1])
    if dy == 0 or dx == 0:
        return None
    k = 0
    r, c = D
    while True:
        nr, nc = r + dy, c + dx
        if nr == S[0] or nc == S[1]:
            break
        if not (0 <= nr < len(inp) and 0 <= nc < len(inp[0])):
            break
        r, c, k = nr, nc, k + 1
    E = (r, c)
    T = (S[0] - dy, S[1] - dx)
    return D, S, (dy, dx), E, T, k


def _line(a, b):
    """Cells from a (exclusive) to b (inclusive) along a shared row or column."""
    if a == b:
        return []
    if a[0] == b[0]:
        st = _sign(b[1] - a[1])
        return [(a[0], c) for c in range(a[1] + st, b[1] + st, st)]
    if a[1] == b[1]:
        st = _sign(b[0] - a[0])
        return [(r, a[1]) for r in range(a[0] + st, b[0] + st, st)]
    return None


def _diag(D, step, k):
    return [(D[0] + step[0] * i, D[1] + step[1] * i) for i in range(1, k + 1)]


def _paint(inp, cells, color=PATH):
    g = [row[:] for row in inp]
    for r, c in cells:
        if not (0 <= r < len(g) and 0 <= c < len(g[0])):
            return None
        if g[r][c] == 0:
            g[r][c] = color
    return g


def _erase(out, cells):
    g = [row[:] for row in out]
    for r, c in cells:
        if g[r][c] == PATH:
            g[r][c] = 0
    return g


def _ray_to_edge(inp, start, step):
    cells = []
    r, c = start[0] + step[0], start[1] + step[1]
    while 0 <= r < len(inp) and 0 <= c < len(inp[0]):
        cells.append((r, c))
        r, c = r + step[0], c + step[1]
    return cells


def path_color_is_diag_mark(inp, out):
    return [[1 if v == PATH else v for v in row] for row in out]


def diagonal_leg_only(inp, out):
    D, S, step, E, T, k = _geom(inp)
    return _erase(out, _line(E, T))


def straight_leg_only(inp, out):
    D, S, step, E, T, k = _geom(inp)
    return _erase(out, _diag(D, step, k - 1))


def diagonal_runs_to_edge(inp, out):
    D, S, step, E, T, k = _geom(inp)
    return _paint(inp, _ray_to_edge(inp, D, step))


def tip_one_short(inp, out):
    D, S, step, E, T, k = _geom(inp)
    return _erase(out, [T])


def tip_one_past(inp, out):
    D, S, step, E, T, k = _geom(inp)
    line = _line(E, T)
    if not line:
        return None
    a = E if len(line) == 1 else line[-2]
    v = (_sign(T[0] - a[0]), _sign(T[1] - a[1]))
    return _paint(out, [(T[0] + v[0], T[1] + v[1])])


def marks_swapped(inp, out):
    g = _geom(inp, d_color=2, s_color=1)
    if g is None:
        return None
    D, S, step, E, T, k = g
    return _paint(inp, _diag(D, step, k) + _line(E, T))


def straight_leg_first(inp, out):
    D, S, step, E, T, k = _geom(inp)
    v = (T[0] - E[0], T[1] - E[1])
    Dp = (D[0] + v[0], D[1] + v[1])
    return _paint(inp, _line(D, Dp) + _diag(Dp, step, k))


def diagonal_away_from_other_mark(inp, out):
    D, S, step, E, T, k = _geom(inp)
    return _paint(inp, _ray_to_edge(inp, D, (-step[0], -step[1])))


def diagonal_on_wrong_axis(inp, out):
    D, S, step, E, T, k = _geom(inp)
    return _paint(inp, _ray_to_edge(inp, D, (step[0], -step[1])))


def elbow_one_cell_late(inp, out):
    D, S, step, E, T, k = _geom(inp)
    E2 = (E[0] + step[0], E[1] + step[1])
    v = (_sign(S[0] - E2[0]), _sign(S[1] - E2[1]))
    stop = (S[0] - v[0], S[1] - v[1])
    return _paint(inp, _diag(D, step, k + 1) + _line(E2, stop))


def unchanged_input(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("path drawn in the color of the diagonal mark (1) instead of 3", path_color_is_diag_mark),
    ("only the diagonal leg is drawn; the straight leg is missing", diagonal_leg_only),
    ("only the straight leg is drawn; the diagonal leg is missing", straight_leg_only),
    ("diagonal ray is not halted at the other mark's line and runs to the grid edge", diagonal_runs_to_edge),
    ("straight leg stops one cell short of the tip", tip_one_short),
    ("straight leg runs one cell past the tip, to touch the other mark orthogonally", tip_one_past),
    ("mark roles swapped: diagonal leaves the 2 and the straight leg ends at the 1", marks_swapped),
    ("straight leg first from the 1, then the diagonal to the tip (corner on the wrong side)", straight_leg_first),
    ("diagonal leaves the 1 directly away from the 2", diagonal_away_from_other_mark),
    ("diagonal leaves the 1 along the other diagonal axis (mirrored sideways)", diagonal_on_wrong_axis),
    ("diagonal runs one cell too far, so the elbow sits on the other mark's line", elbow_one_cell_late),
    ("output equals the input (nothing drawn)", unchanged_input),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/992798f6.json").read_text())
    pairs = task["train"]
    # sanity: the reconstructed true path equals the true output
    for i, p in enumerate(pairs):
        D, S, step, E, T, k = _geom(p["input"])
        rebuilt = _paint(p["input"], _diag(D, step, k) + _line(E, T))
        print("pair", i, "geometry matches true output:", rebuilt == p["output"])
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error in", fn.__name__, repr(e))
                g = None
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
