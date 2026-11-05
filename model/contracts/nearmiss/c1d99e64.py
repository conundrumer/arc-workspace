import json
from collections import Counter
from pathlib import Path


def _rarest(inp):
    c = Counter(v for r in inp for v in r)
    return min(c, key=lambda k: (c[k], k))


def _commonest(inp):
    c = Counter(v for r in inp for v in r)
    return max(c, key=lambda k: (c[k], -k))


def _lines(inp, bg):
    h, w = len(inp), len(inp[0])
    rows = [r for r in range(h) if all(v == bg for v in inp[r])]
    cols = [c for c in range(w) if all(inp[r][c] == bg for r in range(h))]
    return rows, cols


def _line_color(inp, out):
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if inp[r][c] != out[r][c]:
                return out[r][c]
    return None


def _paint(inp, rows, cols, color):
    g = [list(r) for r in inp]
    h, w = len(g), len(g[0])
    for r in rows:
        if 0 <= r < h:
            for c in range(w):
                g[r][c] = color
    for c in cols:
        if 0 <= c < w:
            for r in range(h):
                g[r][c] = color
    return g


def _setup(inp, out):
    bg = _rarest(inp)
    rows, cols = _lines(inp, bg)
    return bg, rows, cols, _line_color(inp, out)


def only_rows(inp, out):
    bg, rows, cols, lc = _setup(inp, out)
    return _paint(inp, rows, [], lc)


def only_cols(inp, out):
    bg, rows, cols, lc = _setup(inp, out)
    return _paint(inp, [], cols, lc)


def wrong_color(inp, out):
    bg, rows, cols, lc = _setup(inp, out)
    fg = [k for k in set(v for r in inp for v in r) if k != bg][0]
    return _paint(inp, rows, cols, fg)


def all_bg_cells(inp, out):
    bg, rows, cols, lc = _setup(inp, out)
    return [[lc if v == bg else v for v in r] for r in inp]


def shifted_by_one(inp, out):
    bg, rows, cols, lc = _setup(inp, out)
    return _paint(inp, [r + 1 for r in rows], [c + 1 for c in cols], lc)


def first_line_only(inp, out):
    bg, rows, cols, lc = _setup(inp, out)
    if rows:
        return _paint(inp, rows[:1], [], lc)
    return _paint(inp, [], cols[:1], lc)


def crossing_kept_bg(inp, out):
    bg, rows, cols, lc = _setup(inp, out)
    if not rows or not cols:
        return None
    g = _paint(inp, rows, cols, lc)
    for r in rows:
        for c in cols:
            g[r][c] = bg
    return g


def commonest_as_bg(inp, out):
    cb = _commonest(inp)
    rows, cols = _lines(inp, cb)
    return _paint(inp, rows, cols, _line_color(inp, out))


def thick_lines(inp, out):
    bg, rows, cols, lc = _setup(inp, out)
    rr = sorted({r + d for r in rows for d in (-1, 0, 1)})
    cc = sorted({c + d for c in cols for d in (-1, 0, 1)})
    return _paint(inp, rr, cc, lc)


def mirrored_positions(inp, out):
    bg, rows, cols, lc = _setup(inp, out)
    h, w = len(inp), len(inp[0])
    return _paint(inp, [h - 1 - r for r in rows], [w - 1 - c for c in cols], lc)


def transposed_axes(inp, out):
    bg, rows, cols, lc = _setup(inp, out)
    return _paint(inp, cols, rows, lc)


ALTERNATIVES = [
    ("Only all-background rows are filled; columns are ignored", only_rows),
    ("Only all-background columns are filled; rows are ignored", only_cols),
    ("Lines are filled with the foreground color instead of the new color", wrong_color),
    ("Every background cell is filled, not only full lines", all_bg_cells),
    ("Lines are filled one row and one column too far (off by one)", shifted_by_one),
    ("Only the first line found is filled", first_line_only),
    ("Cells where a filled row meets a filled column stay background", crossing_kept_bg),
    ("Background is the most common color, so no line is found and input is kept", commonest_as_bg),
    ("Each line is filled three cells thick", thick_lines),
    ("Line positions are mirrored across the grid", mirrored_positions),
    ("Row indices and column indices are swapped when filling", transposed_axes),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/c1d99e64.json").read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in train)
        print(f"{n}/{len(train)}  {desc}")
