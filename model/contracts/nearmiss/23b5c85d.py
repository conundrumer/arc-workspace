import json
from pathlib import Path


def _objs(inp):
    cells = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != 0:
                cells.setdefault(v, []).append((r, c))
    return cells


def _bbox(cs):
    rs = [r for r, _ in cs]
    cc = [c for _, c in cs]
    return min(rs), min(cc), max(rs), max(cc)


def _area(cs):
    r0, c0, r1, c1 = _bbox(cs)
    return (r1 - r0 + 1) * (c1 - c0 + 1)


def _crop(inp, color, box=None, keep_all=False):
    cells = _objs(inp)
    r0, c0, r1, c1 = box or _bbox(cells[color])
    return [[(inp[r][c] if keep_all or inp[r][c] == color else 0)
             for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]


def _ranked(inp, key):
    cells = _objs(inp)
    return sorted(cells, key=lambda col: (key(cells[col]), col))


def _by(key, idx):
    def f(inp, out):
        order = _ranked(inp, key)
        if len(order) <= abs(idx) - (1 if idx < 0 else 0) or len(order) < 2:
            return None
        return _crop(inp, order[idx])
    return f


def largest_count(inp, out):
    return _by(len, -1)(inp, out)


def second_smallest(inp, out):
    return _by(len, 1)(inp, out)


def smallest_bbox(inp, out):
    return _by(_area, 0)(inp, out)


def union_extent(inp, out):
    cells = _objs(inp)
    col = _ranked(inp, len)[0]
    allc = [c for cs in cells.values() for c in cs]
    return _crop(inp, col, _bbox(allc))


def largest_bbox(inp, out):
    return _by(_area, -1)(inp, out)


def topmost(inp, out):
    order = _ranked(inp, lambda cs: _bbox(cs)[0])
    return _crop(inp, order[0])


def leftmost(inp, out):
    order = _ranked(inp, lambda cs: _bbox(cs)[1])
    return _crop(inp, order[0])


def pad_box(inp, out):
    cells = _objs(inp)
    col = _ranked(inp, len)[0]
    r0, c0, r1, c1 = _bbox(cells[col])
    h, w = len(inp), len(inp[0])
    box = (max(r0 - 1, 0), max(c0 - 1, 0), min(r1 + 1, h - 1), min(c1 + 1, w - 1))
    return _crop(inp, col, box, keep_all=True)


def drop_last_row(inp, out):
    return out[:-1]


def drop_first_col(inp, out):
    return [row[1:] for row in out]


def full_width_rows(inp, out):
    cells = _objs(inp)
    col = _ranked(inp, len)[0]
    r0, _, r1, _ = _bbox(cells[col])
    return [[(v if v == col else 0) for v in inp[r]] for r in range(r0, r1 + 1)]


def keep_only_smallest(inp, out):
    col = _ranked(inp, len)[0]
    return [[(v if v == col else 0) for v in row] for row in inp]


def wrong_color(inp, out):
    order = _ranked(inp, len)
    if len(order) < 2:
        return None
    return [[(order[-1] if v else 0) for v in row] for row in out]


def input_unchanged(inp, out):
    return inp


ALTERNATIVES = [
    ("crop the object with the most visible cells", largest_count),
    ("crop the object with the second fewest visible cells", second_smallest),
    ("crop the extent of all objects together, keeping only the smallest object's color", union_extent),
    ("crop the object with the largest bounding box", largest_bbox),
    ("crop the topmost object", topmost),
    ("crop the leftmost object", leftmost),
    ("crop the smallest object's box with a one-cell margin, keeping occluders", pad_box),
    ("crop one row too few", drop_last_row),
    ("crop one column too few at the left", drop_first_col),
    ("keep the smallest object's rows across the full grid width", full_width_rows),
    ("erase every object but the smallest, no crop", keep_only_smallest),
    ("crop the right box but fill it with the largest object's color", wrong_color),
    ("return the input unchanged", input_unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/23b5c85d.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
