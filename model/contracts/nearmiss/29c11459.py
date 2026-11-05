import json
from pathlib import Path


def _info(out):
    for r, row in enumerate(out):
        if 5 in row:
            return r, row.index(5), row[0], row[-1]
    return None


def _copy(g):
    return [list(r) for r in g]


def clash_as_left(inp, out):
    r, m, a, b = _info(out)
    g = _copy(out)
    g[r][m] = a
    return g


def clash_as_right(inp, out):
    r, m, a, b = _info(out)
    g = _copy(out)
    g[r][m] = b
    return g


def clash_background(inp, out):
    r, m, a, b = _info(out)
    g = _copy(out)
    g[r][m] = 0
    return g


def left_wins_all(inp, out):
    r, m, a, b = _info(out)
    return [[a if i == r else 0 for _ in row] for i, row in enumerate(out)]


def right_wins_all(inp, out):
    r, m, a, b = _info(out)
    return [[(b if i == r else 0) for j in range(len(row))] for i, row in enumerate(out)]


def clash_shifted_left(inp, out):
    r, m, a, b = _info(out)
    g = _copy(out)
    g[r][m] = a
    g[r][m - 1] = 5
    return g


def clash_two_wide(inp, out):
    r, m, a, b = _info(out)
    g = _copy(out)
    g[r][m + 1] = 5
    return g


def colors_swapped(inp, out):
    r, m, a, b = _info(out)
    g = _copy(out)
    for j in range(len(g[r])):
        if j < m:
            g[r][j] = b
        elif j > m:
            g[r][j] = a
    return g


def fill_every_row(inp, out):
    r, m, a, b = _info(out)
    return [[(a if j < m else 5 if j == m else b) for j in range(len(row))] for row in out]


def clash_column_all_rows(inp, out):
    r, m, a, b = _info(out)
    g = _copy(out)
    for i in range(len(g)):
        g[i][m] = 5
    return g


def interior_only(inp, out):
    r, m, a, b = _info(out)
    g = _copy(out)
    g[r][0] = 0
    g[r][-1] = 0
    return g


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("clash cell takes the left mark color instead of 5", clash_as_left),
    ("clash cell takes the right mark color instead of 5", clash_as_right),
    ("clash cell left as background (no clash color)", clash_background),
    ("only the left mark spreads, over the whole row, no clash cell", left_wins_all),
    ("only the right mark spreads, over the whole row, no clash cell", right_wins_all),
    ("clash cell placed one cell left of the midpoint", clash_shifted_left),
    ("clash band two cells wide", clash_two_wide),
    ("each half gets the far mark's color", colors_swapped),
    ("halves and clash applied to every row, not only the mark row", fill_every_row),
    ("clash color 5 drawn down the whole middle column", clash_column_all_rows),
    ("fill only strictly between marks; the mark cells are cleared", interior_only),
    ("input returned unchanged", unchanged),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/29c11459.json'))
    pairs = task['train']
    print('pairs', len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(n, fn.__name__, '-', desc)
