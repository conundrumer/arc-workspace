import json
from pathlib import Path


def _bg(inp):
    cnt = {}
    for r in inp:
        for v in r:
            cnt[v] = cnt.get(v, 0) + 1
    return max(cnt, key=cnt.get)


def _ink(inp):
    b = _bg(inp)
    return [(y, x, v) for y, r in enumerate(inp) for x, v in enumerate(r) if v != b]


def _blank(inp):
    b = _bg(inp)
    return [[b] * len(inp[0]) for _ in inp]


def _hline(inp, row, n, color, start=None):
    """Background grid with a horizontal run of n cells on `row`, centered unless start is given."""
    g = _blank(inp)
    w = len(g[0])
    n = max(0, min(n, w))
    if start is None:
        start = (w - n) // 2
    if 0 <= row < len(g):
        for x in range(start, min(w, start + n)):
            g[row][x] = color
    return g


def _color(inp):
    return _ink(inp)[0][2]


def vertical_line(inp, out):
    g = _blank(inp)
    h, w = len(g), len(g[0])
    n = min(len(_ink(inp)), h)
    x = w // 2
    s = (h - n) // 2
    for y in range(s, s + n):
        g[y][x] = _color(inp)
    return g


def full_width(inp, out):
    return _hline(inp, len(inp) // 2, len(inp[0]), _color(inp))


def left_anchored(inp, out):
    return _hline(inp, len(inp) // 2, len(_ink(inp)), _color(inp), start=0)


def short_by_one(inp, out):
    return _hline(inp, len(inp) // 2, len(_ink(inp)) - 1, _color(inp))


def long_by_two(inp, out):
    return _hline(inp, len(inp) // 2, len(_ink(inp)) + 2, _color(inp))


def row_of_centroid(inp, out):
    ink = _ink(inp)
    row = round(sum(y for y, _, _ in ink) / len(ink))
    return _hline(inp, row, len(ink), _color(inp))


def row_of_ink_top(inp, out):
    ink = _ink(inp)
    return _hline(inp, min(y for y, _, _ in ink), len(ink), _color(inp))


def length_is_ink_bbox_width(inp, out):
    ink = _ink(inp)
    xs = [x for _, x, _ in ink]
    return _hline(inp, len(inp) // 2, max(xs) - min(xs) + 1, _color(inp))


def line_at_ink_bbox_columns(inp, out):
    ink = _ink(inp)
    xs = [x for _, x, _ in ink]
    return _hline(inp, len(inp) // 2, max(xs) - min(xs) + 1, _color(inp), start=min(xs))


def ink_kept_under_line(inp, out):
    b = _bg(inp)
    g = [r[:] for r in inp]
    for y, r in enumerate(out):
        for x, v in enumerate(r):
            if v != b:
                g[y][x] = v
    return g


def line_in_wrong_color(inp, out):
    b = _bg(inp)
    c = _color(inp)
    other = next(k for k in (5, 1, 4, 6) if k not in (b, c))
    return [[other if v == c else v for v in r] for r in out]


def input_unchanged(inp, out):
    return [r[:] for r in inp]


def _differs(fn):
    def wrapped(inp, out):
        g = fn(inp, out)
        return None if g == out else g
    return wrapped


ALTERNATIVES = [
    ("line runs vertically along the central column instead of horizontally", _differs(vertical_line)),
    ("line spans the full width regardless of the ink cell count", _differs(full_width)),
    ("line has the right length but starts at the left edge", _differs(left_anchored)),
    ("line is one cell shorter than the ink cell count", _differs(short_by_one)),
    ("line is two cells longer than the ink cell count", _differs(long_by_two)),
    ("line is placed on the rounded centroid row of the ink instead of the grid center row", _differs(row_of_centroid)),
    ("line is placed on the top row of the ink", _differs(row_of_ink_top)),
    ("line length is the ink bounding-box width instead of the ink cell count", _differs(length_is_ink_bbox_width)),
    ("line has the ink bounding-box width and sits over the ink's columns", _differs(line_at_ink_bbox_columns)),
    ("line is drawn but the original ink is left in place", _differs(ink_kept_under_line)),
    ("line is drawn in a color other than the ink color", _differs(line_in_wrong_color)),
    ("input returned unchanged", _differs(input_unchanged)),
]


def _valid(g, out):
    if g is None or not g or not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/dce56571.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
