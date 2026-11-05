import json
from collections import Counter
from pathlib import Path


def _sep(inp):
    for r, row in enumerate(inp):
        if all(v == 5 for v in row):
            return r
    return None


def _counts(inp, include=()):
    s = _sep(inp)
    c = Counter(v for row in inp[:s] for v in row)
    for v in include:
        c.update(v)
    return c


def _ranked(inp):
    c = _counts(inp)
    return sorted(c, key=lambda k: (-c[k], k))


def _put(out, r, col, color):
    g = [row[:] for row in out]
    g[r][col] = color
    return g


def _clear(out):
    s = _sep(out)
    g = [row[:] for row in out]
    for r in range(s + 1, len(g)):
        g[r] = [0] * len(g[r])
    return g


def least_common(inp, out):
    k = _ranked(inp)[-1]
    return _put(_clear(out), len(out) - 1, len(out[0]) // 2, k)


def second_common(inp, out):
    k = _ranked(inp)[1]
    return _put(_clear(out), len(out) - 1, len(out[0]) // 2, k)


def count_separator(inp, out):
    c = _counts(inp)
    c.update([5] * len(inp[0]))
    k = max(c, key=lambda k: (c[k], -k))
    return _put(_clear(out), len(out) - 1, len(out[0]) // 2, k)


def count_ground(inp, out):
    return [row[:] for row in inp]


def first_zero_row(inp, out):
    s = _sep(inp)
    k = _ranked(inp)[0]
    return _put(_clear(out), s + 1, len(out[0]) // 2, k)


def column_off_by_one(inp, out):
    k = _ranked(inp)[0]
    return _put(_clear(out), len(out) - 1, len(out[0]) // 2 + 1, k)


def corner(inp, out):
    k = _ranked(inp)[0]
    return _put(_clear(out), len(out) - 1, 0, k)


def whole_last_row(inp, out):
    k = _ranked(inp)[0]
    g = _clear(out)
    g[-1] = [k] * len(g[-1])
    return g


def center_band(inp, out):
    k = _ranked(inp)[0]
    g = _clear(out)
    m = len(g[0]) // 2
    for c in range(m - 1, m + 2):
        g[-1][c] = k
    return g


def vertical_line(inp, out):
    k = _ranked(inp)[0]
    g = _clear(out)
    m = len(g[0]) // 2
    for r in range(_sep(inp) + 1, len(g)):
        g[r][m] = k
    return g


def middle_zero_row(inp, out):
    s = _sep(inp)
    k = _ranked(inp)[0]
    rows = list(range(s + 1, len(out)))
    return _put(_clear(out), rows[(len(rows) - 1) // 2], len(out[0]) // 2, k)


def swap_top_bottom_row_colors(inp, out):
    # most common color of the last pattern row, instead of the whole pattern
    s = _sep(inp)
    c = Counter(inp[s - 1])
    k = sorted(c, key=lambda k: (-c[k], -k))[0]
    return _put(_clear(out), len(out) - 1, len(out[0]) // 2, k)


ALTERNATIVES = [
    ("stamp the least frequent pattern color instead of the most frequent", least_common),
    ("stamp the second most frequent pattern color", second_common),
    ("count colors including the 5 separator row, so the stamp is 5", count_separator),
    ("count the ground 0 as a color, so nothing is stamped (input unchanged)", count_ground),
    ("stamp in the first row below the separator instead of the last row", first_zero_row),
    ("stamp one column right of the center column", column_off_by_one),
    ("stamp in the bottom-left corner of the ground", corner),
    ("fill the whole last row with the stamp color", whole_last_row),
    ("stamp a three-cell band at the center of the last row", center_band),
    ("draw a vertical line down the center column of the ground", vertical_line),
    ("stamp in the vertical middle row of the ground", middle_zero_row),
    ("take the stamp color from the pattern row next to the separator only", swap_top_bottom_row_colors),
]


def _valid(g, out):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/27a77e38.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
