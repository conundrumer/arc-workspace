import json
from pathlib import Path


def _copy(g):
    return [r[:] for r in g]


def _rows(inp):
    """Rows whose left and right end cells are non-zero: (row, left, right)."""
    w = len(inp[0])
    return [(r, row[0], row[w - 1]) for r, row in enumerate(inp)
            if row[0] != 0 and row[w - 1] != 0]


def _matches(inp):
    return [(r, a) for r, a, b in _rows(inp) if a == b]


def _guard(out, g):
    return None if g == out else g


def identity(inp, out):
    return _copy(inp)


def left_half(inp, out):
    g = _copy(inp)
    w = len(g[0])
    for r, c in _matches(inp):
        for x in range(w // 2):
            g[r][x] = c
    return _guard(out, g)


def any_both_nonzero(inp, out):
    g = _copy(inp)
    w = len(g[0])
    for r, a, b in _rows(inp):
        g[r] = [a] * w
    return g


def wrong_color(inp, out):
    g = _copy(inp)
    w = len(g[0])
    for r, c in _matches(inp):
        g[r] = [c % 9 + 1] * w
    return _guard(out, g)


def column_instead_of_row(inp, out):
    g = _copy(inp)
    h = len(g)
    for r, c in _matches(inp):
        for y in range(h):
            g[y][r] = c
    return _guard(out, g)


def off_by_one_short(inp, out):
    g = _copy(inp)
    w = len(g[0])
    for r, c in _matches(inp):
        for x in range(w - 2):
            g[r][x] = c
    return _guard(out, g)


def two_rows_thick(inp, out):
    g = _copy(inp)
    w = len(g[0])
    for r, c in _matches(inp):
        for rr in (r, r + 1):
            if rr < len(g):
                for x in range(w):
                    if g[rr][x] == 0:
                        g[rr][x] = c
    return _guard(out, g)


def first_match_only(inp, out):
    m = _matches(inp)
    if not m:
        return None
    g = _copy(inp)
    r, c = m[0]
    g[r] = [c] * len(g[0])
    return _guard(out, g)


def match_any_row_on_right(inp, out):
    rows = _rows(inp)
    rights = {b for _, _, b in rows}
    g = _copy(inp)
    w = len(g[0])
    for r, a, b in rows:
        if a in rights:
            g[r] = [a] * w
    return _guard(out, g)


def match_next_row(inp, out):
    rows = _rows(inp)
    g = _copy(inp)
    w = len(g[0])
    for i, (r, a, b) in enumerate(rows):
        if i + 1 < len(rows) and rows[i + 1][2] == a:
            g[r] = [a] * w
    return _guard(out, g)


def erase_matched_ends(inp, out):
    g = _copy(out)
    w = len(g[0])
    for r, c in _matches(inp):
        g[r] = [0] * w
    return _guard(out, g)


def fill_unmatched_with_left(inp, out):
    g = _copy(out)
    w = len(g[0])
    ms = {r for r, _ in _matches(inp)}
    for r, a, b in _rows(inp):
        if r not in ms:
            g[r] = [a] * w
    return _guard(out, g)


ALTERNATIVES = [
    ("no row is filled; input returned unchanged", identity),
    ("a matching row is filled only across its left half", left_half),
    ("every row with non-zero cells at both ends is filled with its left color, matched or not", any_both_nonzero),
    ("matching rows are filled with the wrong color (matched color plus one)", wrong_color),
    ("the matched color is drawn down the column with the row's index, not along the row", column_instead_of_row),
    ("fill stops one cell short of the right end", off_by_one_short),
    ("fill is two rows thick (the row below is also filled)", two_rows_thick),
    ("only the first matching row is filled", first_match_only),
    ("a left cell counts as matched if its color appears at the right end of any row", match_any_row_on_right),
    ("a left cell is matched against the right end of the next row with end cells", match_next_row),
    ("matching rows are cleared to background instead of filled", erase_matched_ends),
    ("non-matching rows with two end cells are filled with the left color, matching rows left alone", fill_unmatched_with_left),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/22eb0ac0.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
