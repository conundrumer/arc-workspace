from pathlib import Path
import json


def _color(inp):
    for row in inp:
        for v in row:
            if v:
                return v
    return 0


def _count(inp):
    return sum(1 for row in inp for v in row if v)


def vertical_bar(inp, out):
    n = _count(inp)
    return [[_color(inp)] for _ in range(n)]


def length_plus_one(inp, out):
    return [[_color(inp)] * (_count(inp) + 1)]


def length_minus_one(inp, out):
    n = _count(inp) - 1
    if n < 1:
        return None
    return [[_color(inp)] * n]


def count_background(inp, out):
    n = sum(1 for row in inp for v in row if not v)
    return [[_color(inp)] * n]


def wrong_color(inp, out):
    c = _color(inp)
    return [[c % 9 + 1] * _count(inp)]


def background_color_bar(inp, out):
    return [[0] * _count(inp)]


def input_unchanged(inp, out):
    return [list(r) for r in inp]


def fill_square_row_major(inp, out):
    n = _count(inp)
    h, w = len(inp), len(inp[0])
    cells = [_color(inp) if i < n else 0 for i in range(h * w)]
    return [cells[r * w:(r + 1) * w] for r in range(h)]


def longest_row_count(inp, out):
    n = max(sum(1 for v in row if v) for row in inp)
    return [[_color(inp)] * n]


def bounding_box_crop(inp, out):
    pts = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v]
    r0 = min(p[0] for p in pts)
    r1 = max(p[0] for p in pts)
    c0 = min(p[1] for p in pts)
    c1 = max(p[1] for p in pts)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def two_row_bar(inp, out):
    n = _count(inp)
    return [[_color(inp)] * n for _ in range(2)]


ALTERNATIVES = [
    ("bar laid out as a vertical column instead of a horizontal row", vertical_bar),
    ("bar one cell too long", length_plus_one),
    ("bar one cell too short", length_minus_one),
    ("bar length counts background cells instead of colored cells", count_background),
    ("bar uses the wrong color (next color up)", wrong_color),
    ("bar of the right length drawn in background color 0", background_color_bar),
    ("input returned unchanged", input_unchanged),
    ("bar filled row-major into a grid of the input size", fill_square_row_major),
    ("bar length is the largest colored count in a single row", longest_row_count),
    ("output is the bounding box crop of the colored cells", bounding_box_crop),
    ("bar is two rows thick instead of one", two_row_bar),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/d631b094.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(ok, "/", len(pairs), desc)
