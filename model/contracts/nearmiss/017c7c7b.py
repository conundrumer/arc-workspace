import json
from pathlib import Path


def _rc(g):
    return [[2 if v == 1 else v for v in r] for r in g]


def _period(g):
    n = len(g)
    for p in range(1, n + 1):
        if all(g[i] == g[i + p] for i in range(n - p)):
            return p
    return n


def _extend(g, n):
    p = _period(g)
    rows = [list(r) for r in g]
    while len(rows) < n:
        rows.append(list(rows[len(rows) - p]))
    return rows[:n]


def keep_color(inp, out):
    return [[1 if v == 2 else v for v in r] for r in out]


def same_height(inp, out):
    return [list(r) for r in out[:len(inp)]]


def one_row_short(inp, out):
    return [list(r) for r in out[:len(out) - 1]]


def one_row_long(inp, out):
    return _extend(out, len(out) + 1)


def double_height(inp, out):
    return _extend(out, 2 * len(inp))


def mirror_extension(inp, out):
    rc = _rc(inp)
    rows = [list(r) for r in rc]
    k = len(out) - len(inp)
    rows += [list(r) for r in rc[::-1][:k]]
    return rows


def grow_upward(inp, out):
    p = _period(out)
    k = len(out) - len(inp)
    rc = _rc(inp)
    top = [list(rc[(j - k) % p]) for j in range(k)]
    return top + [list(r) for r in rc]


def new_rows_uncolored(inp, out):
    rows = [list(r) for r in out]
    for i in range(len(inp), len(out)):
        rows[i] = [1 if v == 2 else v for v in rows[i]]
    return rows


def swap_colors(inp, out):
    return [[2 if v == 0 else (0 if v == 2 else v) for v in r] for r in out]


def repeat_last_row(inp, out):
    rc = _rc(inp)
    rows = [list(r) for r in rc]
    while len(rows) < len(out):
        rows.append(list(rc[-1]))
    return rows


def extend_sideways(inp, out):
    return [list(r) + list(r) for r in _rc(inp)]


def restart_from_top(inp, out):
    rc = _rc(inp)
    rows = [list(r) for r in rc]
    k = len(out) - len(inp)
    rows += [list(r) for r in rc[:k]]
    return rows


ALTERNATIVES = [
    ("keep ink color 1 instead of recoloring to 2", keep_color),
    ("recolor but do not grow: output keeps the input height", same_height),
    ("grow by one row too few", one_row_short),
    ("grow by one row too many", one_row_long),
    ("grow to twice the input height", double_height),
    ("extension is a mirror of the input instead of the periodic continuation", mirror_extension),
    ("grow upward instead of downward", grow_upward),
    ("recolor only the input rows; added rows keep color 1", new_rows_uncolored),
    ("swap background and ink colors in the output", swap_colors),
    ("added rows repeat the last input row", repeat_last_row),
    ("grow along columns instead of rows", extend_sideways),
    ("added rows restart from the top of the input, ignoring the period", restart_from_top),
]


def _valid(g):
    return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/017c7c7b.json'))
    pairs = task['train']
    print('pairs', len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
