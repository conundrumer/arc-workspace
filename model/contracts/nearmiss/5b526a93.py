"""Near-miss readings for ARC task 5b526a93.

Rule: the input holds same-shaped squares (rings of one color). Their row
starts and column starts form a lattice; every lattice position without a
square gets a copy of the square in color 8, with the hole kept.
"""
import json
from pathlib import Path

BG = 0
FILL = 8


def _squares(inp):
    """Bounding boxes (r, c, h, w) of 4-connected non-background components."""
    H, W = len(inp), len(inp[0])
    seen = set()
    boxes = []
    for i in range(H):
        for j in range(W):
            if inp[i][j] == BG or (i, j) in seen:
                continue
            stack = [(i, j)]
            seen.add((i, j))
            cells = []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = a + da, b + db
                    if 0 <= x < H and 0 <= y < W and inp[x][y] != BG and (x, y) not in seen:
                        seen.add((x, y))
                        stack.append((x, y))
            rs = [a for a, _ in cells]
            cs = [b for _, b in cells]
            boxes.append((min(rs), min(cs), max(rs) - min(rs) + 1, max(cs) - min(cs) + 1))
    return boxes


def _lattice(inp):
    boxes = _squares(inp)
    rows = sorted({b[0] for b in boxes})
    cols = sorted({b[1] for b in boxes})
    h, w = boxes[0][2], boxes[0][3]
    have = {(b[0], b[1]) for b in boxes}
    new = [(r, c) for r in rows for c in cols if (r, c) not in have]
    return boxes, rows, cols, h, w, have, new


def _color(inp):
    return next(v for r in inp for v in r if v != BG)


def _stamp(inp, positions, fn):
    """Copy of inp with a stamp painted at each position; fn(dr, dc, v) gives the cell value or None."""
    boxes, rows, cols, h, w, have, new = _lattice(inp)
    r0, c0 = boxes[0][0], boxes[0][1]
    g = [r[:] for r in inp]
    for (r, c) in positions:
        for dr in range(h):
            for dc in range(w):
                if 0 <= r + dr < len(g) and 0 <= c + dc < len(g[0]):
                    v = fn(dr, dc, inp[r0 + dr][c0 + dc])
                    if v is not None:
                        g[r + dr][c + dc] = v
    return g


def wrong_color(inp, out):
    c = _color(inp)
    return [[c if v == FILL else v for v in r] for r in out]


def solid_stamp(inp, out):
    _, _, _, _, _, _, new = _lattice(inp)
    return _stamp(inp, new, lambda dr, dc, v: FILL)


def inverted_stamp(inp, out):
    return _stamp(inp, _lattice(inp)[6], lambda dr, dc, v: BG if v != BG else FILL)


def last_column_only(inp, out):
    _, _, cols, _, _, _, new = _lattice(inp)
    keep = [p for p in new if p[1] == cols[-1]]
    return _stamp(inp, keep, lambda dr, dc, v: FILL if v != BG else None)


def last_row_only(inp, out):
    _, rows, _, _, _, _, new = _lattice(inp)
    keep = [p for p in new if p[0] == rows[-1]]
    return _stamp(inp, keep, lambda dr, dc, v: FILL if v != BG else None)


def first_stamp_missing(inp, out):
    new = sorted(_lattice(inp)[6])
    if len(new) < 2:
        return None
    return _stamp(inp, new[1:], lambda dr, dc, v: FILL if v != BG else None)


def rows_from_top_row_only(inp, out):
    """Columns taken from the top row of squares only; rows from all squares."""
    boxes, rows, cols, h, w, have, new = _lattice(inp)
    top = min(b[0] for b in boxes)
    cs = sorted({b[1] for b in boxes if b[0] == top})
    pos = [(r, c) for r in rows for c in cs if (r, c) not in have]
    return _stamp(inp, pos, lambda dr, dc, v: FILL if v != BG else None)


def stamp_shifted_right(inp, out):
    new = _lattice(inp)[6]
    pos = [(r, c + 1) for r, c in new]
    return _stamp(inp, pos, lambda dr, dc, v: FILL if v != BG else None)


def stamp_shifted_down(inp, out):
    new = _lattice(inp)[6]
    pos = [(r + 1, c) for r, c in new]
    return _stamp(inp, pos, lambda dr, dc, v: FILL if v != BG else None)


def transposed_stamp_layout(inp, out):
    """Stamps placed at (column start, row start) swapped: row/col roles exchanged."""
    boxes, rows, cols, h, w, have, new = _lattice(inp)
    pos = [(r, c) for r in cols for c in rows if (r, c) not in have]
    pos = [(r, c) for r, c in pos if r + h <= len(inp) and c + w <= len(inp[0])]
    return _stamp(inp, pos, lambda dr, dc, v: FILL if v != BG else None)


def filled_bounding_rectangle(inp, out):
    cells = [(i, j) for i, r in enumerate(out) for j, v in enumerate(r) if v == FILL]
    r0, r1 = min(i for i, _ in cells), max(i for i, _ in cells)
    c0, c1 = min(j for _, j in cells), max(j for _, j in cells)
    g = [r[:] for r in out]
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            if inp[i][j] == BG:
                g[i][j] = FILL
    return g


def stamp_one_wider(inp, out):
    g = [r[:] for r in out]
    for i, r in enumerate(out):
        for j, v in enumerate(r):
            if v == FILL and j + 1 < len(r) and g[i][j + 1] == BG:
                g[i][j + 1] = FILL
    return g


ALTERNATIVES = [
    ("new squares drawn in the existing square color instead of 8", wrong_color),
    ("new squares drawn solid in 8, hole filled", solid_stamp),
    ("new squares drawn with ring background and hole 8 (pattern inverted)", inverted_stamp),
    ("only the last column of lattice positions gets new squares", last_column_only),
    ("only the last row of lattice positions gets new squares", last_row_only),
    ("first new square (reading order) left out", first_stamp_missing),
    ("column positions taken from the top row of squares only", rows_from_top_row_only),
    ("new squares placed one column to the right of the lattice position", stamp_shifted_right),
    ("new squares placed one row below the lattice position", stamp_shifted_down),
    ("lattice built with row and column starts exchanged", transposed_stamp_layout),
    ("whole bounding rectangle of the new squares filled with 8", filled_bounding_rectangle),
    ("new squares one cell wider (extra 8 column on the right of each 8 cell)", stamp_one_wider),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/5b526a93.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {fn.__name__}: {desc}")
