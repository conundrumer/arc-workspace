"""Near-miss rules for ARC task 4364c1c4.

True rule: the commonest color is the field. Each other colored part touches
another part above or below it. A part with a neighbor below slides 1 left;
a part with a neighbor above slides 1 right.
"""
import json
from collections import Counter
from pathlib import Path


def _field(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _parts(inp):
    """Return (field, list of (color, cells, role)); role is 'up' (neighbor
    below), 'low' (neighbor above), or 'none'."""
    f = _field(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    parts = []
    for y in range(h):
        for x in range(w):
            if inp[y][x] == f or (y, x) in seen:
                continue
            col = inp[y][x]
            stack, cells = [(y, x)], []
            seen.add((y, x))
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] == col:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            below = any(cy + 1 < h and inp[cy + 1][cx] not in (f, col) for cy, cx in cells)
            above = any(cy - 1 >= 0 and inp[cy - 1][cx] not in (f, col) for cy, cx in cells)
            role = "up" if below and not above else "low" if above and not below else "none"
            parts.append((col, cells, role))
    return f, parts


def _render(inp, moves, keep_old=False, fill=None):
    """moves: function (role, index) -> (dy, dx)."""
    f, parts = _parts(inp)
    h, w = len(inp), len(inp[0])
    g = [[f] * w for _ in range(h)]
    if keep_old:
        for col, cells, _ in parts:
            for y, x in cells:
                g[y][x] = col
    elif fill is not None:
        for _, cells, _ in parts:
            for y, x in cells:
                g[y][x] = fill
    for i, (col, cells, role) in enumerate(parts):
        dy, dx = moves(role, i)
        for y, x in cells:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                g[ny][nx] = col
    return g


def swapped(inp, out):
    return _render(inp, lambda r, i: (0, 1) if r == "up" else (0, -1) if r == "low" else (0, 0))


def shift2(inp, out):
    return _render(inp, lambda r, i: (0, -2) if r == "up" else (0, 2) if r == "low" else (0, 0))


def only_upper(inp, out):
    return _render(inp, lambda r, i: (0, -1) if r == "up" else (0, 0))


def only_lower(inp, out):
    return _render(inp, lambda r, i: (0, 1) if r == "low" else (0, 0))


def all_left(inp, out):
    return _render(inp, lambda r, i: (0, -1))


def all_right(inp, out):
    return _render(inp, lambda r, i: (0, 1))


def vertical(inp, out):
    return _render(inp, lambda r, i: (-1, 0) if r == "up" else (1, 0) if r == "low" else (0, 0))


def smear(inp, out):
    return _render(inp, lambda r, i: (0, -1) if r == "up" else (0, 1) if r == "low" else (0, 0),
                   keep_old=True)


def vacated_zero(inp, out):
    return _render(inp, lambda r, i: (0, -1) if r == "up" else (0, 1) if r == "low" else (0, 0),
                   fill=0 if _field(inp) != 0 else 1)


def first_only(inp, out):
    f, parts = _parts(inp)
    first = min(range(len(parts)), key=lambda i: min(y for y, _ in parts[i][1]))
    return _render(inp, lambda r, i: (0, -1) if i == first and r == "up" else (0, 0))


def diagonal(inp, out):
    return _render(inp, lambda r, i: (-1, -1) if r == "up" else (1, 1) if r == "low" else (0, 0))


def by_order_alternate(inp, out):
    """Parts alternate left/right by scan order of their first cell."""
    f, parts = _parts(inp)
    order = sorted(range(len(parts)), key=lambda i: min(parts[i][1]))
    rank = {i: k for k, i in enumerate(order)}
    return _render(inp, lambda r, i: (0, 1) if rank[i] % 2 == 0 else (0, -1))


ALTERNATIVES = [
    ("slide directions swapped: upper parts right, lower parts left", swapped),
    ("slide distance 2 instead of 1", shift2),
    ("only parts with a neighbor below move", only_upper),
    ("only parts with a neighbor above move", only_lower),
    ("every part slides 1 left", all_left),
    ("every part slides 1 right", all_right),
    ("parts slide vertically (upper up, lower down) instead of sideways", vertical),
    ("parts are copied to the new place but the old cells stay (smear)", smear),
    ("vacated cells filled with a non-field color", vacated_zero),
    ("only the topmost part moves", first_only),
    ("diagonal slide: upper up-left, lower down-right", diagonal),
    ("parts alternate right/left by scan order, not by neighbor side", by_order_alternate),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/4364c1c4.json"))
    pairs = task["train"]

    def valid(g, out):
        return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1
                and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
                and g != out)

    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
