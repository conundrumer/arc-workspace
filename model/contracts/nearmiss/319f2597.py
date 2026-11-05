"""Near-miss readings for 319f2597.

Rule: the rarest color is the mark (a 2x2 block). Every cell in a row or column
that holds a mark cell becomes the mark color, except cells of the spare color,
which stay as they are.
"""
import json
from collections import Counter
from pathlib import Path


def _mark(inp):
    cnt = Counter(c for r in inp for c in r)
    return min(cnt, key=lambda k: (cnt[k], k))


def _cells(inp):
    m = _mark(inp)
    return m, [(i, j) for i, r in enumerate(inp) for j, c in enumerate(r) if c == m]


def _spare(inp, out):
    m, cells = _cells(inp)
    rows = {i for i, _ in cells}
    cols = {j for _, j in cells}
    cnt = Counter()
    for i, r in enumerate(inp):
        for j, c in enumerate(r):
            if (i in rows or j in cols) and out[i][j] == c and c != m:
                cnt[c] += 1
    return cnt.most_common(1)[0][0] if cnt else None


def _paint(inp, out, pred, color=None, keep_spare=True):
    """Paint cells where pred(i, j) holds; spare-colored cells stay unless keep_spare is False."""
    m, _ = _cells(inp)
    sp = _spare(inp, out)
    col = m if color is None else color
    g = [r[:] for r in inp]
    for i in range(len(g)):
        for j in range(len(g[0])):
            if pred(i, j) and not (keep_spare and inp[i][j] == sp):
                g[i][j] = col
    return g


def _rc(inp):
    _, cells = _cells(inp)
    return {i for i, _ in cells}, {j for _, j in cells}


def paint_spare_too(inp, out):
    rows, cols = _rc(inp)
    return _paint(inp, out, lambda i, j: i in rows or j in cols, keep_spare=False)


def only_columns(inp, out):
    rows, cols = _rc(inp)
    return _paint(inp, out, lambda i, j: j in cols)


def only_rows(inp, out):
    rows, cols = _rc(inp)
    return _paint(inp, out, lambda i, j: i in rows)


def paint_with_spare_color(inp, out):
    rows, cols = _rc(inp)
    sp = _spare(inp, out)
    return _paint(inp, out, lambda i, j: i in rows or j in cols, color=sp)


def paint_with_common_color(inp, out):
    rows, cols = _rc(inp)
    cnt = Counter(c for r in inp for c in r)
    top = cnt.most_common(1)[0][0]
    return _paint(inp, out, lambda i, j: i in rows or j in cols, color=top)


def forward_only(inp, out):
    rows, cols = _rc(inp)
    r1, c1 = max(rows), max(cols)
    return _paint(inp, out, lambda i, j: (i in rows and j >= c1) or (j in cols and i >= r1))


def one_cell_cross(inp, out):
    _, cells = _cells(inp)
    r0, c0 = min(cells)
    return _paint(inp, out, lambda i, j: i == r0 or j == c0)


def wide_band(inp, out):
    rows, cols = _rc(inp)
    rr = {i + d for i in rows for d in (-1, 0, 1)}
    cc = {j + d for j in cols for d in (-1, 0, 1)}
    return _paint(inp, out, lambda i, j: i in rr or j in cc)


def blocked_rays(inp, out):
    """Rays leave the block and stop at the first spare-colored cell."""
    m, cells = _cells(inp)
    sp = _spare(inp, out)
    rows, cols = _rc(inp)
    h, w = len(inp), len(inp[0])
    g = [r[:] for r in inp]
    r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
    for i in rows:
        for rng in (range(c0 - 1, -1, -1), range(c1 + 1, w)):
            for j in rng:
                if inp[i][j] == sp:
                    break
                g[i][j] = m
    for j in cols:
        for rng in (range(r0 - 1, -1, -1), range(r1 + 1, h)):
            for i in rng:
                if inp[i][j] == sp:
                    break
                g[i][j] = m
    return g


def diagonals_too(inp, out):
    _, cells = _cells(inp)
    rows, cols = _rc(inp)
    return _paint(inp, out, lambda i, j: i in rows or j in cols
                  or any(abs(i - a) == abs(j - b) for a, b in cells))


def inverted_condition(inp, out):
    """Only spare-colored cells on the cross are painted."""
    rows, cols = _rc(inp)
    sp = _spare(inp, out)
    m, _ = _cells(inp)
    g = [r[:] for r in inp]
    for i in range(len(g)):
        for j in range(len(g[0])):
            if (i in rows or j in cols) and inp[i][j] == sp:
                g[i][j] = m
    return g


def output_without_mark_block(inp, out):
    """Correct painting, but the mark block itself is erased with the most common color."""
    _, cells = _cells(inp)
    cnt = Counter(c for r in inp for c in r)
    top = cnt.most_common(1)[0][0]
    g = [r[:] for r in out]
    for i, j in cells:
        g[i][j] = top
    return g


ALTERNATIVES = [
    ("paint the spare color too (no cell on the cross is spared)", paint_spare_too),
    ("paint only the columns of the mark block", only_columns),
    ("paint only the rows of the mark block", only_rows),
    ("paint the cross with the spare color instead of the mark color", paint_with_spare_color),
    ("paint the cross with the most common color", paint_with_common_color),
    ("paint only the part of the cross at or after the block (right and down)", forward_only),
    ("cross through one block cell only, not the whole block", one_cell_cross),
    ("cross band one cell wider on each side of the block", wide_band),
    ("rays stop at the first spare-colored cell", blocked_rays),
    ("diagonal lines through the block cells are painted as well", diagonals_too),
    ("only spare-colored cells on the cross are painted", inverted_condition),
    ("true painting, but the mark block itself is erased", output_without_mark_block),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/319f2597.json").read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
