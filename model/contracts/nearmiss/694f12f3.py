import json
from pathlib import Path


def _rects(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    rects = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0 and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                ys = [p[0] for p in cells]
                xs = [p[1] for p in cells]
                rects.append((min(ys), min(xs), max(ys), max(xs), len(cells)))
    return rects


def _paint(inp, plan, margin=1, horizontal_only=False, whole=False):
    """plan: list of (rect, color or None)."""
    g = [row[:] for row in inp]
    for (r0, c0, r1, c1, _), col in plan:
        if col is None:
            continue
        for y in range(r0, r1 + 1):
            for x in range(c0, c1 + 1):
                if whole:
                    inside = True
                elif horizontal_only:
                    inside = c0 + margin <= x <= c1 - margin
                else:
                    inside = r0 + margin <= y <= r1 - margin and c0 + margin <= x <= c1 - margin
                if inside:
                    g[y][x] = col
    return g


def _by_size(inp):
    rs = sorted(_rects(inp), key=lambda r: r[4])
    return rs[0], rs[-1]


def swap_colors(inp, out):
    s, l = _by_size(inp)
    return _paint(inp, [(s, 2), (l, 1)])


def whole_rect(inp, out):
    s, l = _by_size(inp)
    return _paint(inp, [(s, 1), (l, 2)], whole=True)


def erode_twice(inp, out):
    s, l = _by_size(inp)
    return _paint(inp, [(s, 1), (l, 2)], margin=2)


def only_large(inp, out):
    s, l = _by_size(inp)
    return _paint(inp, [(s, None), (l, 2)])


def only_small(inp, out):
    s, l = _by_size(inp)
    return _paint(inp, [(s, 1), (l, None)])


def all_one(inp, out):
    s, l = _by_size(inp)
    return _paint(inp, [(s, 1), (l, 1)])


def all_two(inp, out):
    s, l = _by_size(inp)
    return _paint(inp, [(s, 2), (l, 2)])


def top_one_bottom_two(inp, out):
    rs = sorted(_rects(inp), key=lambda r: (r[0], r[1]))
    return _paint(inp, [(rs[0], 1), (rs[-1], 2)])


def horizontal_erode_only(inp, out):
    s, l = _by_size(inp)
    return _paint(inp, [(s, 1), (l, 2)], horizontal_only=True)


def hollow_zero(inp, out):
    s, l = _by_size(inp)
    return _paint(inp, [(s, 0), (l, 0)])


ALTERNATIVES = [
    ("fill colors swapped: smallest rectangle interior 2, largest 1", swap_colors),
    ("fill the whole rectangle including its border", whole_rect),
    ("interior shrunk by two cells from the rectangle edge", erode_twice),
    ("only the larger rectangle is filled", only_large),
    ("only the smaller rectangle is filled", only_small),
    ("every interior filled with 1", all_one),
    ("every interior filled with 2", all_two),
    ("color by position: top-left rectangle 1, other 2", top_one_bottom_two),
    ("interior erodes only left and right, so top and bottom rows are filled too", horizontal_erode_only),
    ("interiors cleared to 0 instead of filled", hollow_zero),
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
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/694f12f3.json').read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, desc)
