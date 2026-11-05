import json
from collections import Counter
from pathlib import Path

FILL = 2


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _spans(row, bg):
    """Gaps between consecutive non-bg cells of a row: (left, right) column pairs."""
    cols = [i for i, c in enumerate(row) if c != bg]
    return list(zip(cols, cols[1:]))


def _copy(g):
    return [list(r) for r in g]


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _fill_rows(inp, color=FILL, margin=0, include_ends=False, row_ok=None, first_only=False):
    bg = _bg(inp)
    g = _copy(inp)
    for y, row in enumerate(inp):
        if row_ok is not None and not row_ok(y, len(inp)):
            continue
        sp = _spans(row, bg)
        if first_only:
            sp = sp[:1]
        for a, b in sp:
            lo, hi = a + 1 + margin, b - 1 - margin
            if include_ends:
                lo, hi = a, b
            for x in range(lo, hi + 1):
                g[y][x] = color
    return g


def vertical_axis(inp, out):
    return _transpose(_fill_rows(_transpose(inp)))


def shape_color(inp, out):
    bg = _bg(inp)
    col = next(c for r in inp for c in r if c != bg)
    return _fill_rows(inp, color=col)


def shrink_one(inp, out):
    return _fill_rows(inp, margin=1)


def overwrite_ends(inp, out):
    return _fill_rows(inp, include_ends=True)


def first_span_only(inp, out):
    return _fill_rows(inp, first_only=True)


def top_half_rows(inp, out):
    return _fill_rows(inp, row_ok=lambda y, h: 2 * y < h)


def bottom_row_only(inp, out):
    bg = _bg(inp)
    ys = [y for y, r in enumerate(inp) if _spans(r, bg)]
    last = ys[-1]
    return _fill_rows(inp, row_ok=lambda y, h: y == last)


def to_right_edge(inp, out):
    bg = _bg(inp)
    g = _copy(inp)
    for y, row in enumerate(inp):
        cols = [i for i, c in enumerate(row) if c != bg]
        if len(cols) >= 2:
            for x in range(cols[0] + 1, len(row)):
                if row[x] == bg:
                    g[y][x] = FILL
    return g


def whole_row(inp, out):
    bg = _bg(inp)
    g = _copy(inp)
    for y, row in enumerate(inp):
        if len(_spans(row, bg)) >= 1:
            for x in range(len(row)):
                if row[x] == bg:
                    g[y][x] = FILL
    return g


def bounding_box(inp, out):
    bg = _bg(inp)
    ys = [y for y, r in enumerate(inp) for c in r if c != bg]
    xs = [x for r in inp for x, c in enumerate(r) if c != bg]
    g = _copy(inp)
    for y in range(min(ys), max(ys) + 1):
        for x in range(min(xs), max(xs) + 1):
            if inp[y][x] == bg:
                g[y][x] = FILL
    return g


def wide_gaps_only(inp, out):
    bg = _bg(inp)
    g = _copy(inp)
    for y, row in enumerate(inp):
        for a, b in _spans(row, bg):
            if b - a - 1 >= 2:
                for x in range(a + 1, b):
                    g[y][x] = FILL
    return g


def drop_shape(inp, out):
    # fills the right gaps but erases the original shape cells
    bg = _bg(inp)
    g = _fill_rows(inp)
    return [[bg if inp[y][x] != bg else g[y][x] for x in range(len(inp[0]))]
            for y in range(len(inp))]


ALTERNATIVES = [
    ("fill vertical gaps between shape cells (columns) instead of horizontal gaps (rows)", vertical_axis),
    ("fill the gaps with the shape's own color instead of 2", shape_color),
    ("fill the gaps but leave the cell next to each endpoint unfilled", shrink_one),
    ("fill the gaps and also recolor the endpoint cells to 2", overwrite_ends),
    ("fill only the first gap in each row", first_span_only),
    ("fill only gaps in the top half of the grid", top_half_rows),
    ("fill only the gaps in the bottom-most row that has a gap", bottom_row_only),
    ("fill from the first shape cell in a row to the right grid edge", to_right_edge),
    ("fill every background cell of any row that has a gap, across the whole row", whole_row),
    ("fill the whole bounding box of the shape with 2", bounding_box),
    ("fill only gaps at least 2 cells wide", wide_gaps_only),
    ("fill the gaps but erase the original shape cells", drop_shape),
]


def _valid(g, out):
    if g is None:
        return False
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/aa18de87.json"))
    pairs = task["train"]
    print(f"{len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(_copy(p["input"]), _copy(p["output"]))
            except Exception as e:
                print("  error:", e)
                g = None
            n += _valid(g, p["output"])
        print(f"{n}/{len(pairs)}  {desc}")
