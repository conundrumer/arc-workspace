from pathlib import Path
import json
from collections import Counter


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _blocks(inp):
    """Number of 4-connected blocks per non-bg color."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    cnt = Counter()
    for i in range(h):
        for j in range(w):
            if inp[i][j] == bg or (i, j) in seen:
                continue
            col = inp[i][j]
            cnt[col] += 1
            st = [(i, j)]
            seen.add((i, j))
            while st:
                y, x = st.pop()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    a, b = y + dy, x + dx
                    if 0 <= a < h and 0 <= b < w and (a, b) not in seen and inp[a][b] == col:
                        seen.add((a, b))
                        st.append((a, b))
    return cnt


def _ranked(inp):
    """Minority colors, most blocks first (the true order)."""
    cnt = _blocks(inp)
    top = max(cnt.values())
    rest = [(c, n) for c, n in cnt.items() if n != top]
    rest.sort(key=lambda t: (-t[1], t[0]))
    return [c for c, _ in rest], cnt


def ascending(inp, out):
    cols, _ = _ranked(inp)
    return [[c] for c in reversed(cols)]


def keep_dominant(inp, out):
    cols, cnt = _ranked(inp)
    dom = max(cnt, key=lambda c: cnt[c])
    return [[dom]] + [[c] for c in cols]


def dominant_only(inp, out):
    _, cnt = _ranked(inp)
    return [[max(cnt, key=lambda c: cnt[c])]]


def horizontal(inp, out):
    cols, _ = _ranked(inp)
    return [list(cols)]


def drop_least(inp, out):
    cols, _ = _ranked(inp)
    return [[c] for c in cols[:-1]]


def drop_most(inp, out):
    cols, _ = _ranked(inp)
    return [[c] for c in cols[1:]]


def sort_by_color_value(inp, out):
    cols, _ = _ranked(inp)
    return [[c] for c in sorted(cols)]


def repeat_by_count(inp, out):
    cols, cnt = _ranked(inp)
    return [[c] for c in cols for _ in range(cnt[c])]


def rank_by_rows_touched(inp, out):
    bg = _bg(inp)
    cnt = _blocks(inp)
    dom = max(cnt, key=lambda c: cnt[c])
    rows = {c: sum(1 for r in inp if c in r) for c in cnt if c != dom}
    order = sorted(rows, key=lambda c: (-rows[c], c))
    return [[c] for c in order]


def rank_by_cell_count_with_dominant_by_blocks_only_two(inp, out):
    # Keep only the two most frequent minority colors.
    cols, _ = _ranked(inp)
    return [[c] for c in cols[:2]]


def background_column(inp, out):
    cols, _ = _ranked(inp)
    return [[_bg(inp)]] + [[c] for c in cols]


def minority_wide_pairs(inp, out):
    # Each color drawn as 2 cells wide (block width mistaken for output cell size).
    return [r * 2 for r in out]


ALTERNATIVES = [
    ("ranked fewest blocks first (ascending order)", ascending),
    ("dominant color kept as the top row", keep_dominant),
    ("output only the dominant color", dominant_only),
    ("colors laid out in a horizontal row", horizontal),
    ("least frequent minority color dropped", drop_least),
    ("most frequent minority color dropped", drop_most),
    ("minority colors ordered by color value", sort_by_color_value),
    ("each color repeated once per block", repeat_by_count),
    ("colors ranked by number of grid rows they touch", rank_by_rows_touched),
    ("only the top two minority colors kept", rank_by_cell_count_with_dominant_by_blocks_only_two),
    ("background color added as the top row", background_column),
    ("each output cell drawn two cells wide", minority_wide_pairs),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(type(c) is int and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/f8b3ba0a.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for p in pairs:
        assert _ranked(p["input"])[0] == [r[0] for r in p["output"]], "true rule mismatch"
    for name, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, name)
