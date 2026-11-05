import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _objects(inp):
    """4-connected same-color components of non-background cells."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    objs = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] == bg or (i, j) in seen:
                continue
            col = inp[i][j]
            stack = [(i, j)]
            seen.add((i, j))
            cells = []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and (x, y) not in seen and inp[x][y] == col:
                        seen.add((x, y))
                        stack.append((x, y))
            objs.append((col, cells))
    return objs


def _hw(cells):
    rs = [c[0] for c in cells]
    cs = [c[1] for c in cells]
    return max(rs) - min(rs) + 1, max(cs) - min(cs) + 1


def _render(inp, shift_fn, keep_original=False, clip=True):
    """shift_fn(col, cells, objs) -> (dr, dc)."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    objs = _objects(inp)
    g = [row[:] for row in inp] if keep_original else [[bg] * w for _ in range(h)]
    for col, cells in objs:
        dr, dc = shift_fn(col, cells, objs)
        for a, b in cells:
            x, y = a + dr, b + dc
            if 0 <= x < h and 0 <= y < w:
                g[x][y] = col
    return g


def _width_up(inp, out):
    return _render(inp, lambda c, cells, o: (-_hw(cells)[1], 0))


def _down(inp, out):
    return _render(inp, lambda c, cells, o: (_hw(cells)[0], 0))


def _height_minus_one(inp, out):
    return _render(inp, lambda c, cells, o: (-(_hw(cells)[0] - 1), 0))


def _height_plus_one(inp, out):
    return _render(inp, lambda c, cells, o: (-(_hw(cells)[0] + 1), 0))


def _only_four(inp, out):
    return _render(inp, lambda c, cells, o: (-_hw(cells)[0], 0) if c == 4 else (0, 0))


def _copy_not_move(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for col, cells in _objects(inp):
        d = _hw(cells)[0]
        for a, b in cells:
            if 0 <= a - d < h:
                g[a - d][b] = col
    return g


def _tallest_height_all(inp, out):
    m = max(_hw(cells)[0] for _, cells in _objects(inp))
    return _render(inp, lambda c, cells, o: (-m, 0))


def _slide_to_top(inp, out):
    return _render(inp, lambda c, cells, o: (-min(a for a, _ in cells), 0))


def _left_by_width(inp, out):
    return _render(inp, lambda c, cells, o: (0, -_hw(cells)[1]))


def _right_by_height(inp, out):
    return _render(inp, lambda c, cells, o: (0, _hw(cells)[0]))


def _largest_only(inp, out):
    big = max(_objects(inp), key=lambda t: len(t[1]))
    return _render(inp, lambda c, cells, o: (-_hw(cells)[0], 0) if cells is big[1] else (0, 0))


def _fixed_two(inp, out):
    return _render(inp, lambda c, cells, o: (-2, 0))


def _wide_only_not_moved(inp, out):
    # objects wider than tall are treated as static
    return _render(inp, lambda c, cells, o: (-_hw(cells)[0], 0) if _hw(cells)[0] >= _hw(cells)[1] else (0, 0))


ALTERNATIVES = [
    ("objects move up by their width instead of their height", _width_up),
    ("objects move down by their height instead of up", _down),
    ("objects move up by height minus one (off-by-one distance)", _height_minus_one),
    ("objects move up by height plus one (off-by-one distance)", _height_plus_one),
    ("only the color-4 objects move; others stay", _only_four),
    ("objects are copied up by their height, old position not cleared", _copy_not_move),
    ("every object moves up by the height of the tallest object", _tallest_height_all),
    ("every object slides up until it touches the top edge", _slide_to_top),
    ("objects move left by their width", _left_by_width),
    ("objects move right by their height", _right_by_height),
    ("only the largest object (by area) moves up by its height", _largest_only),
    ("objects wider than tall stay in place; the rest move up by height", _wide_only_not_moved),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/5521c0d9.json"))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
