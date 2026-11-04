from pathlib import Path
import json
from collections import Counter


def _find(inp, out, dr=0, dc=0):
    """Locate the uniform-ish block window of the output's size.
    Returns (r, c, h, w, color)."""
    h, w = len(out), len(out[0])
    H, W = len(inp), len(inp[0])
    best = None
    for r in range(H - h + 1):
        for c in range(W - w + 1):
            cnt = Counter(inp[r + i][c + j] for i in range(h) for j in range(w))
            col, n = cnt.most_common(1)[0]
            if best is None or n > best[0]:
                best = (n, r, c, col)
    _, r, c, col = best
    return r, c, h, w, col


def _flaws(inp, r, c, h, w, col):
    return [(i, j, inp[r + i][c + j]) for i in range(h) for j in range(w)
            if inp[r + i][c + j] != col]


def _paint(h, w, col, flaws, rows=True, cols=True, fcol=None, lines=True,
           swap=False):
    g = [[col] * w for _ in range(h)]
    for (i, j, f) in flaws:
        f = f if fcol is None else fcol
        if lines:
            if rows:
                for x in range(w):
                    g[i][x] = f
            if cols:
                for y in range(h):
                    g[y][j] = f
        else:
            g[i][j] = f
    return g


def _ctx(inp, out):
    r, c, h, w, col = _find(inp, out)
    return r, c, h, w, col, _flaws(inp, r, c, h, w, col)


def rows_only(inp, out):
    r, c, h, w, col, fl = _ctx(inp, out)
    return _paint(h, w, col, fl, cols=False)


def cols_only(inp, out):
    r, c, h, w, col, fl = _ctx(inp, out)
    return _paint(h, w, col, fl, rows=False)


def cells_only(inp, out):
    r, c, h, w, col, fl = _ctx(inp, out)
    return _paint(h, w, col, fl, lines=False)


def swapped_colors(inp, out):
    r, c, h, w, col, fl = _ctx(inp, out)
    if not fl:
        return None
    f = fl[0][2]
    g = _paint(h, w, col, fl)
    return [[f if v == col else col for v in row] for row in g]


def shrunk_crop(inp, out):
    if len(out) < 3 or len(out[0]) < 3:
        return None
    return [row[1:-1] for row in out[1:-1]]


def extra_row_col(inp, out):
    g = [row + [row[-1]] for row in out]
    g.append(list(g[-1]))
    return g


def pasted_into_input(inp, out):
    r, c, h, w, col, fl = _ctx(inp, out)
    g = [list(row) for row in inp]
    for i in range(h):
        for j in range(w):
            g[r + i][c + j] = out[i][j]
    return g


def wrong_line_color(inp, out):
    # lines take the least common color of the whole input instead of the flaw color
    cnt = Counter(v for row in inp for v in row)
    r, c, h, w, col, fl = _ctx(inp, out)
    cand = [k for k, _ in sorted(cnt.items(), key=lambda kv: kv[1]) if k != col]
    return _paint(h, w, col, fl, fcol=cand[0])


def mirrored_flaw_columns(inp, out):
    r, c, h, w, col, fl = _ctx(inp, out)
    fl2 = [(i, w - 1 - j, f) for (i, j, f) in fl]
    return _paint(h, w, col, fl2)


def first_flaw_only(inp, out):
    r, c, h, w, col, fl = _ctx(inp, out)
    return _paint(h, w, col, fl[:1])


def shifted_window(inp, out):
    h, w = len(out), len(out[0])
    r, c, _, _, col = _find(inp, out)
    c2 = c + 1 if c + w < len(inp[0]) else c - 1
    col2 = Counter(inp[r + i][c2 + j] for i in range(h) for j in range(w)).most_common(1)[0][0]
    fl = _flaws(inp, r, c2, h, w, col2)
    return _paint(h, w, col2, fl)


def inverted_lines(inp, out):
    # lines drawn through the cells that are NOT on a flaw row or column
    r, c, h, w, col, fl = _ctx(inp, out)
    if not fl:
        return None
    f = fl[0][2]
    fr = {i for i, _, _ in fl}
    fc = {j for _, j, _ in fl}
    return [[col if (i in fr or j in fc) else f for j in range(w)] for i in range(h)]


ALTERNATIVES = [
    ("flaw rows are painted but flaw columns are not", rows_only),
    ("flaw columns are painted but flaw rows are not", cols_only),
    ("only the flaw cells are painted, no lines through them", cells_only),
    ("block color and flaw color are swapped in the output", swapped_colors),
    ("crop leaves out the block's outer border", shrunk_crop),
    ("crop is one row and one column too large", extra_row_col),
    ("output is the whole input with the block region replaced", pasted_into_input),
    ("lines use the rarest color of the input instead of the flaw color", wrong_line_color),
    ("flaw columns counted from the right edge", mirrored_flaw_columns),
    ("only the first flaw (reading order) makes lines", first_flaw_only),
    ("block window found one column off", shifted_window),
    ("lines drawn on every row and column without a flaw instead", inverted_lines),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/8731374e.json')))
    pairs = t["train"]
    # sanity: the true rule reproduces the output
    for p in pairs:
        r, c, h, w, col, fl = _ctx(p["input"], p["output"])
        assert _paint(h, w, col, fl) == p["output"], "rule check failed"
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
