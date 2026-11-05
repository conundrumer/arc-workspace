import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for row in inp for v in row).most_common(1)[0][0]


def _boxes(inp):
    """Per non-background color: (r0, c0, r1, c1) bounding box, in reading order of first cell."""
    bg = _bg(inp)
    boxes = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == bg:
                continue
            if v not in boxes:
                boxes[v] = [r, c, r, c]
            else:
                b = boxes[v]
                b[0], b[1] = min(b[0], r), min(b[1], c)
                b[2], b[3] = max(b[2], r), max(b[3], c)
    return {k: tuple(v) for k, v in boxes.items()}


def _paint(grid, r0, c0, r1, c1, color):
    h, w = len(grid), len(grid[0])
    for r in range(max(r0, 0), min(r1, h - 1) + 1):
        for c in range(max(c0, 0), min(c1, w - 1) + 1):
            grid[r][c] = color


def _copy(g):
    return [list(r) for r in g]


def _with(inp, fn):
    g = _copy(inp)
    for col, b in _boxes(inp).items():
        fn(g, col, *b)
    return g


def unchanged(inp, out):
    return _copy(inp)


def outline_only(inp, out):
    def f(g, col, r0, c0, r1, c1):
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if r in (r0, r1) or c in (c0, c1):
                    g[r][c] = col
    return _with(inp, f)


def interior_only(inp, out):
    def f(g, col, r0, c0, r1, c1):
        _paint(g, r0 + 1, c0 + 1, r1 - 1, c1 - 1, col)
    return _with(inp, f)


def shrunk_off_by_one(inp, out):
    def f(g, col, r0, c0, r1, c1):
        _paint(g, r0, c0, r1 - 1, c1 - 1, col)
        g[r1][c1] = col
    g = _copy(inp)
    for col, (r0, c0, r1, c1) in _boxes(inp).items():
        _paint(g, r0, c0, r1 - 1, c1 - 1, col)
        g[r1][c1] = col
    return g


def grown_by_one(inp, out):
    def f(g, col, r0, c0, r1, c1):
        _paint(g, r0 - 1, c0 - 1, r1 + 1, c1 + 1, col)
    return _with(inp, f)


def full_width_bands(inp, out):
    w = len(inp[0])
    def f(g, col, r0, c0, r1, c1):
        _paint(g, r0, 0, r1, w - 1, col)
    return _with(inp, f)


def full_height_bands(inp, out):
    h = len(inp)
    def f(g, col, r0, c0, r1, c1):
        _paint(g, 0, c0, h - 1, c1, col)
    return _with(inp, f)


def first_seed_color_for_all(inp, out):
    boxes = _boxes(inp)
    first = next(v for row in inp for v in row if v != _bg(inp))
    g = _copy(inp)
    for col, (r0, c0, r1, c1) in boxes.items():
        _paint(g, r0, c0, r1, c1, first)
    return g


def only_first_color_box(inp, out):
    first = next(v for row in inp for v in row if v != _bg(inp))
    r0, c0, r1, c1 = _boxes(inp)[first]
    g = _copy(inp)
    _paint(g, r0, c0, r1, c1, first)
    return g


def transposed_spans(inp, out):
    def f(g, col, r0, c0, r1, c1):
        _paint(g, c0, r0, c1, r1, col)
    return _with(inp, f)


def shifted_down_right(inp, out):
    g = _copy(inp)
    bg = _bg(inp)
    for col, (r0, c0, r1, c1) in _boxes(inp).items():
        _paint(g, r0 + 1, c0 + 1, r1 + 1, c1 + 1, col)
    return g


def one_global_box(inp, out):
    bg = _bg(inp)
    cells = [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != bg]
    g = _copy(inp)
    _paint(g, min(r for r, _, _ in cells), min(c for _, c, _ in cells),
           max(r for r, _, _ in cells), max(c for _, c, _ in cells), cells[0][2])
    return g


ALTERNATIVES = [
    ("Output is the input unchanged (no fill)", unchanged),
    ("Only the border of each color's bounding box is drawn", outline_only),
    ("Only the interior of each bounding box is filled; the border keeps the input", interior_only),
    ("Bounding box is one row and one column too small at the bottom and right", shrunk_off_by_one),
    ("Bounding box is grown by one cell on every side", grown_by_one),
    ("Each color fills the full-width rows between its extreme rows", full_width_bands),
    ("Each color fills the full-height columns between its extreme columns", full_height_bands),
    ("Every box is filled with the color of the first seed in reading order", first_seed_color_for_all),
    ("Only the first-seen color's box is filled; other colors are left as in the input", only_first_color_box),
    ("Row span and column span of each bounding box are swapped", transposed_spans),
    ("Each filled box is shifted one cell down and right", shifted_down_right),
    ("One box spans all non-background cells regardless of color, in the first seed's color", one_global_box),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/56ff96f3.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
