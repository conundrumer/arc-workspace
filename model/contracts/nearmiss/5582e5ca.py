import json
from collections import Counter
from pathlib import Path


def _flat(g):
    return [c for r in g for c in r]


def _ranked(inp):
    """Colors ordered by count; ties by first row-major occurrence."""
    flat = _flat(inp)
    cnt = Counter(flat)
    first = {}
    for i, c in enumerate(flat):
        first.setdefault(c, i)
    return sorted(cnt, key=lambda c: (-cnt[c], first[c])), cnt


def _fill(inp, c):
    return [[c] * len(r) for r in inp]


def least_frequent(inp, out):
    ranked, cnt = _ranked(inp)
    low = min(cnt.values())
    flat = _flat(inp)
    c = next(x for x in flat if cnt[x] == low)
    return _fill(inp, c)


def second_most_frequent(inp, out):
    ranked, _ = _ranked(inp)
    return _fill(inp, ranked[1])


def top_row_only(inp, out):
    ranked, _ = _ranked(inp)
    g = [r[:] for r in inp]
    g[0] = [ranked[0]] * len(g[0])
    return g


def diagonal_only(inp, out):
    ranked, _ = _ranked(inp)
    g = [r[:] for r in inp]
    for i in range(min(len(g), len(g[0]))):
        g[i][i] = ranked[0]
    return g


def one_smaller(inp, out):
    h, w = len(out) - 1, len(out[0]) - 1
    return [[out[0][0]] * w for _ in range(h)]


def column_majority(inp, out):
    cols = []
    for j in range(len(inp[0])):
        col = [r[j] for r in inp]
        cnt = Counter(col)
        cols.append(max(col, key=lambda c: (cnt[c], -col.index(c))))
    return [cols[:] for _ in inp]


def smallest_color(inp, out):
    return _fill(inp, min(_flat(inp)))


def one_cell_unfilled(inp, out):
    ranked, _ = _ranked(inp)
    g = _fill(inp, ranked[0])
    for i, r in enumerate(inp):
        for j, c in enumerate(r):
            if c != ranked[0]:
                g[i][j] = c
                return g
    return None


def keep_winner_blank_rest(inp, out):
    ranked, _ = _ranked(inp)
    return [[c if c == ranked[0] else 0 for c in r] for r in inp]


def unchanged(inp, out):
    return [r[:] for r in inp]


def single_cell(inp, out):
    return [[out[0][0]]]


ALTERNATIVES = [
    ("fill with the least frequent color instead of the most frequent", least_frequent),
    ("fill with the second most frequent color", second_most_frequent),
    ("fill only the top row with the winning color, keep the rest of the input", top_row_only),
    ("write the winning color only on the main diagonal, keep the rest of the input", diagonal_only),
    ("fill with the winning color but one row and one column too small", one_smaller),
    ("fill each column with that column's own most common color", column_majority),
    ("fill with the numerically smallest color present", smallest_color),
    ("fill with the winning color but leave the first non-winning cell unfilled", one_cell_unfilled),
    ("keep the winning color cells and blank all other cells to 0", keep_winner_blank_rest),
    ("return the input grid unchanged", unchanged),
    ("reduce the answer to a single cell of the winning color", single_cell),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/5582e5ca.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
