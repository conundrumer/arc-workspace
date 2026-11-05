import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _objects(inp, same_color=True):
    """4-connected components of non-background cells above the floor row."""
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    seen = set()
    objs = []
    for r in range(h - 1):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            col = inp[r][c]
            stack, cells = [(r, c)], []
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h - 1 and 0 <= nx < w and (ny, nx) not in seen:
                        v = inp[ny][nx]
                        if v != bg and (v == col or not same_color):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            objs.append(cells)
    return objs


def _render(inp, moves, keep_original=False, floor_cleared=False):
    """moves: list of (cells, dy, dx). Cells moved off-grid are lost."""
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    g = [row[:] for row in inp]
    if not keep_original:
        for cells, _, _ in moves:
            for y, x in cells:
                g[y][x] = bg
    for cells, dy, dx in moves:
        for y, x in cells:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h - 1 and 0 <= nx < w:
                g[ny][nx] = inp[y][x]
    if floor_cleared:
        g[h - 1] = [bg] * w
    return g


def _by(inp, fn):
    return _render(inp, [(c, -fn(c, inp), 0) for c in _objects(inp)])


def one_row(inp, out):
    return _by(inp, lambda c, i: 1)


def count_minus_one(inp, out):
    return _by(inp, lambda c, i: len(c) - 1)


def count_plus_one(inp, out):
    return _by(inp, lambda c, i: len(c) + 1)


def by_height(inp, out):
    return _by(inp, lambda c, i: max(y for y, _ in c) - min(y for y, _ in c) + 1)


def by_width(inp, out):
    return _by(inp, lambda c, i: max(x for _, x in c) - min(x for _, x in c) + 1)


def largest_count_for_all(inp, out):
    m = max(len(c) for c in _objects(inp))
    return _by(inp, lambda c, i: m)


def to_far_edge(inp, out):
    return _by(inp, lambda c, i: min(y for y, _ in c))


def sideways(inp, out):
    return _render(inp, [(c, 0, len(c)) for c in _objects(inp)])


def toward_floor(inp, out):
    return _render(inp, [(c, len(c), 0) for c in _objects(inp)])


def no_clear(inp, out):
    return _render(inp, [(c, -len(c), 0) for c in _objects(inp)], keep_original=True)


def floor_erased(inp, out):
    g = [row[:] for row in out]
    bg = _bg(inp)
    g[-1] = [bg] * len(g[-1])
    return g


def one_object_all_colors(inp, out):
    cells = [cell for c in _objects(inp) for cell in c]
    return _render(inp, [(cells, -len(cells), 0)])


ALTERNATIVES = [
    ("every object moves up one row", one_row),
    ("object moves up by its cell count minus one", count_minus_one),
    ("object moves up by its cell count plus one", count_plus_one),
    ("object moves up by the height of its bounding box", by_height),
    ("object moves up by the width of its bounding box", by_width),
    ("every object moves up by the cell count of the largest object", largest_count_for_all),
    ("every object moves up until it touches the far edge", to_far_edge),
    ("object moves right by its cell count instead of away from the floor", sideways),
    ("object moves toward the floor by its cell count", toward_floor),
    ("object is copied up by its cell count and the original stays in place", no_clear),
    ("objects move correctly but the floor row is erased to background", floor_erased),
    ("all non-background cells form one object that moves up by the total cell count", one_object_all_colors),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b2bc3ffd.json").read_text())
    pairs = task["train"]

    def valid(g, out):
        return (
            isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
            and g != out
        )

    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
