import json
from pathlib import Path


def _zeros(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 0]


def _paint(inp, color_of):
    g = [row[:] for row in inp]
    for r, c in _zeros(inp):
        g[r][c] = color_of(r, c)
    return g


def _ranks(keys, reverse=False):
    ks = sorted(set(keys), reverse=reverse)
    return {k: i + 1 for i, k in enumerate(ks)}


def right_to_left(inp, out):
    rk = _ranks([c for _, c in _zeros(inp)], reverse=True)
    return _paint(inp, lambda r, c: min(rk[c], 9))


def by_row(inp, out):
    rk = _ranks([r for r, _ in _zeros(inp)])
    return _paint(inp, lambda r, c: min(rk[r], 9))


def shifted_colors(inp, out):
    rk = _ranks([c for _, c in _zeros(inp)])
    return _paint(inp, lambda r, c: rk[c] + 1)


def by_zero_count(inp, out):
    cols = {}
    for r, c in _zeros(inp):
        cols[c] = cols.get(c, 0) + 1
    order = sorted(cols, key=lambda c: (-cols[c], -c))
    rk = {c: i + 1 for i, c in enumerate(order)}
    return _paint(inp, lambda r, c: rk[c])


def per_cell_reading_order(inp, out):
    order = {p: i + 1 for i, p in enumerate(_zeros(inp))}
    return _paint(inp, lambda r, c: min(order[(r, c)], 9))


def first_cell_per_column(inp, out):
    rk = _ranks([c for _, c in _zeros(inp)])
    seen = set()
    g = [row[:] for row in inp]
    for r, c in sorted(_zeros(inp)):
        if c not in seen:
            seen.add(c)
            g[r][c] = rk[c]
        else:
            g[r][c] = 5
    return g


def by_column_index(inp, out):
    return _paint(inp, lambda r, c: c // 2 + 1)


def lowest_zero_first(inp, out):
    low = {}
    for r, c in _zeros(inp):
        low[c] = max(low.get(c, -1), r)
    order = sorted(low, key=lambda c: (-low[c], c))
    rk = {c: i + 1 for i, c in enumerate(order)}
    return _paint(inp, lambda r, c: rk[c])


def top_rank_unfilled(inp, out):
    top = max(v for row in out for v in row if v != 5)
    return [[5 if (v == top and inp[r][c] == 0) else v for c, v in enumerate(row)]
            for r, row in enumerate(out)]


def marks_erased(inp, out):
    return [[5 if v == 0 else v for v in row] for row in inp]


def rank_from_zero_index(inp, out):
    rk = _ranks([c for _, c in _zeros(inp)])
    return _paint(inp, lambda r, c: rk[c] - 1 if rk[c] > 1 else 0)


ALTERNATIVES = [
    ("rank marked columns right to left instead of left to right", right_to_left),
    ("rank marked rows top to bottom and color by row rank", by_row),
    ("colors start at 2 instead of 1 (rank plus one)", shifted_colors),
    ("rank marked columns by number of marks, most first", by_zero_count),
    ("give every marked cell its own color in reading order", per_cell_reading_order),
    ("color only the topmost mark of each column, erase the rest", first_cell_per_column),
    ("color by absolute column index (half of it) instead of rank among marked columns", by_column_index),
    ("rank marked columns by lowest mark, lowest first", lowest_zero_first),
    ("leave the last-ranked column's marks unfilled", top_rank_unfilled),
    ("erase all marks to background", marks_erased),
    ("colors are rank minus one, first column stays 0", rank_from_zero_index),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/575b1a71.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(1 for p in pairs if (g := fn(p['input'], p['output'])) is not None and _valid(g, p['output']))
        print(n, desc)
