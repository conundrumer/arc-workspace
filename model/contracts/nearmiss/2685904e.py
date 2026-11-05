import json
from collections import Counter
from pathlib import Path


def _parts(inp):
    h, w = len(inp), len(inp[0])
    sep = next(r for r in range(h) if all(v == 5 for v in inp[r]))
    prow = sep + 2
    n = sum(1 for v in inp[0] if v != 0)
    cnt = Counter(inp[prow])
    return h, w, sep, prow, n, cnt


def _paint(inp, cols_color, height, direction=-1, overwrite=False):
    """Paint columns (dict col->color) `height` cells from the separator."""
    h, w, sep, prow, n, cnt = _parts(inp)
    g = [r[:] for r in inp]
    for c, col in cols_color.items():
        for k in range(1, height + 1):
            r = sep + direction * k
            if 0 <= r < h and (overwrite or g[r][c] == 0):
                g[r][c] = col
    return g


def _cols_with(inp, pred):
    h, w, sep, prow, n, cnt = _parts(inp)
    return {c: inp[prow][c] for c in range(w) if pred(cnt[inp[prow][c]], n, cnt)}


def _freq_n_minus_1(inp, out):
    n = _parts(inp)[4]
    cols = _cols_with(inp, lambda f, n_, cnt: f == n_ - 1)
    return _paint(inp, cols, n) if cols else None


def _freq_n_plus_1(inp, out):
    n = _parts(inp)[4]
    cols = _cols_with(inp, lambda f, n_, cnt: f == n_ + 1)
    return _paint(inp, cols, n) if cols else None


def _most_frequent(inp, out):
    n = _parts(inp)[4]
    cols = _cols_with(inp, lambda f, n_, cnt: f == max(cnt.values()))
    return _paint(inp, cols, n)


def _least_frequent(inp, out):
    n = _parts(inp)[4]
    cols = _cols_with(inp, lambda f, n_, cnt: f == min(cnt.values()))
    return _paint(inp, cols, n)


def _correct_cols(inp):
    return _cols_with(inp, lambda f, n, cnt: f == n)


def _short_band(inp, out):
    n = _parts(inp)[4]
    return _paint(inp, _correct_cols(inp), n - 1)


def _long_band(inp, out):
    n = _parts(inp)[4]
    return _paint(inp, _correct_cols(inp), n + 1)


def _full_height(inp, out):
    sep = _parts(inp)[2]
    return _paint(inp, _correct_cols(inp), sep)


def _below_separator(inp, out):
    n = _parts(inp)[4]
    return _paint(inp, _correct_cols(inp), n, direction=1)


def _marker_color(inp, out):
    n = _parts(inp)[4]
    cols = {c: 8 for c in _correct_cols(inp)}
    return _paint(inp, cols, n)


def _one_cell(inp, out):
    return _paint(inp, _correct_cols(inp), 1)


def _pattern_row_cleared(inp, out):
    prow = _parts(inp)[3]
    g = [r[:] for r in out]
    keep = _correct_cols(inp)
    for c in range(len(g[0])):
        if c not in keep:
            g[prow][c] = 0
    return g


def _distinct_count(inp, out):
    h, w, sep, prow, n, cnt = _parts(inp)
    m = len(cnt)
    cols = _cols_with(inp, lambda f, n_, cnt_: f == m)
    return _paint(inp, cols, m) if cols else None


def _first_color(inp, out):
    h, w, sep, prow, n, cnt = _parts(inp)
    c0 = inp[prow][0]
    cols = {c: c0 for c in range(w) if inp[prow][c] == c0}
    return _paint(inp, cols, n)


ALTERNATIVES = [
    ("select colors with frequency N-1 instead of N", _freq_n_minus_1),
    ("select the most frequent pattern color", _most_frequent),
    ("select the least frequent pattern color", _least_frequent),
    ("band one cell too short (N-1 rows)", _short_band),
    ("band one cell too tall (N+1 rows)", _long_band),
    ("band fills the whole canvas above the separator", _full_height),
    ("band drawn below the separator instead of above", _below_separator),
    ("band painted in the length-marker color 8", _marker_color),
    ("band only one cell thick next to the separator", _one_cell),
    ("unselected pattern cells erased from the pattern row", _pattern_row_cleared),
    ("band follows the color of the first pattern cell", _first_color),
]


def _valid(g, truth):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != truth


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/2685904e.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        ok = sum(1 for p in pairs if _valid(fn(p["input"], p["output"]), p["output"]))
        print(f"{ok}/{len(pairs)}  {desc}")
