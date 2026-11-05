"""Near-miss rules for 91714a58.

True rule: the output keeps only the largest solid single-color rectangle of
the input, on a background of 0.
"""
import json
from collections import Counter
from pathlib import Path


def _blank(inp):
    return [[0] * len(inp[0]) for _ in inp]


def _bbox(g):
    cells = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v]
    if not cells:
        return None
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def _color(g):
    cells = [v for row in g for v in row if v]
    return Counter(cells).most_common(1)[0][0] if cells else 0


def _fill(inp, r0, r1, c0, c1, col):
    g = _blank(inp)
    for r in range(max(r0, 0), min(r1, len(g) - 1) + 1):
        for c in range(max(c0, 0), min(c1, len(g[0]) - 1) + 1):
            g[r][c] = col
    return g


def _solid_rects(inp):
    """All solid single-color rectangles at least 2 cells on each axis."""
    h, w = len(inp), len(inp[0])
    found = []
    for r0 in range(h):
        for c0 in range(w):
            col = inp[r0][c0]
            if col == 0:
                continue
            for r1 in range(r0 + 1, h):
                for c1 in range(c0 + 1, w):
                    if all(inp[r][c] == col for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)):
                        found.append((r0, r1, c0, c1, col))
    return found


def _maximal(rects):
    return [a for a in rects
            if not any(b != a and b[4] == a[4] and b[0] <= a[0] and b[1] >= a[1]
                       and b[2] <= a[2] and b[3] >= a[3] for b in rects)]


def _area(t):
    return (t[1] - t[0] + 1) * (t[3] - t[2] + 1)


def recolored(inp, out):
    """Right place and size, but the most frequent other color of the input."""
    col = _color(out)
    counts = Counter(v for row in inp for v in row if v and v != col)
    other = counts.most_common(1)[0][0]
    return [[other if v else 0 for v in row] for row in out]


def shifted_right(inp, out):
    r0, r1, c0, c1 = _bbox(out)
    return _fill(inp, r0, r1, c0 + 1, c1 + 1, _color(out))


def first_col_dropped(inp, out):
    r0, r1, c0, c1 = _bbox(out)
    return _fill(inp, r0, r1, c0 + 1, c1, _color(out))


def shifted_down(inp, out):
    r0, r1, c0, c1 = _bbox(out)
    return _fill(inp, r0 + 1, r1 + 1, c0, c1, _color(out))


def grown_by_one(inp, out):
    r0, r1, c0, c1 = _bbox(out)
    return _fill(inp, r0 - 1, r1 + 1, c0 - 1, c1 + 1, _color(out))


def last_row_dropped(inp, out):
    r0, r1, c0, c1 = _bbox(out)
    return _fill(inp, r0, r1 - 1, c0, c1, _color(out))


def hollow_outline(inp, out):
    r0, r1, c0, c1 = _bbox(out)
    g = [row[:] for row in out]
    for r in range(r0 + 1, r1):
        for c in range(c0 + 1, c1):
            g[r][c] = 0
    return g


def transposed_position(inp, out):
    r0, r1, c0, c1 = _bbox(out)
    return _fill(inp, c0, c1, r0, r1, _color(out))


def mirrored_position(inp, out):
    r0, r1, c0, c1 = _bbox(out)
    w = len(inp[0])
    return _fill(inp, r0, r1, w - 1 - c1, w - 1 - c0, _color(out))


def color_bbox(inp, out):
    """Fill the bounding box of every cell of the rectangle's color."""
    col = _color(out)
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == col]
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return _fill(inp, min(rs), max(rs), min(cs), max(cs), col)


def most_frequent_color_cells(inp, out):
    """Keep every cell of the most frequent non-background color."""
    counts = Counter(v for row in inp for v in row if v)
    col = counts.most_common(1)[0][0]
    return [[v if v == col else 0 for v in row] for row in inp]


def input_unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("largest rectangle in the right size and place, but in the most frequent other color", recolored),
    ("largest rectangle placed one row too low", shifted_down),
    ("largest rectangle placed one column too far right", shifted_right),
    ("largest rectangle drawn one cell too large on every side", grown_by_one),
    ("largest rectangle with its last row cropped off", last_row_dropped),
    ("largest rectangle with its first column cropped off", first_col_dropped),
    ("only the outline of the largest rectangle is kept", hollow_outline),
    ("largest rectangle placed with rows and columns swapped", transposed_position),
    ("largest rectangle placed at its left-right mirrored position", mirrored_position),
    ("fill the bounding box of all cells of the rectangle's color", color_bbox),
    ("keep all cells of the most frequent color", most_frequent_color_cells),
    ("return the input unchanged", input_unchanged),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/91714a58.json').read_text())
    pairs = task["train"]
    print(f"pairs: {len(pairs)}")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
