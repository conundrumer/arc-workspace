import json
from pathlib import Path


def _bg(g):
    from collections import Counter
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def _setup(g):
    h, w = len(g), len(g[0])
    top, bot = g[0][0], g[h - 1][0]
    bg = _bg(g)
    return h, w, top, bot, bg


def _comps(g, diag=True, rows=None):
    h, w, top, bot, bg = _setup(g)
    seen = set()
    res = []
    nb = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diag:
        nb += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for r in range(1, h - 1):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            col = g[r][c]
            st = [(r, c)]
            seen.add((r, c))
            cells = []
            while st:
                y, x = st.pop()
                cells.append((y, x))
                for dy, dx in nb:
                    ny, nx = y + dy, x + dx
                    if 1 <= ny < h - 1 and 0 <= nx < w and (ny, nx) not in seen and g[ny][nx] == col:
                        seen.add((ny, nx))
                        st.append((ny, nx))
            res.append((col, cells))
    return res


def _blank(g):
    h, w, top, bot, bg = _setup(g)
    return [list(g[0])] + [[bg] * w for _ in range(h - 2)] + [list(g[h - 1])]


def _render(g, moves, diag=True, keep_orig=False, drop_oob=False):
    """moves: fn(col, cells, h, w, top, bot) -> (dy, dx)"""
    h, w, top, bot, bg = _setup(g)
    o = _blank(g)
    if keep_orig:
        for r in range(1, h - 1):
            o[r] = list(g[r])
    for col, cells in _comps(g, diag):
        dy, dx = moves(col, cells, h, w, top, bot)
        for y, x in cells:
            ny, nx = y + dy, x + dx
            if 1 <= ny < h - 1 and 0 <= nx < w:
                o[ny][nx] = col
            elif not drop_oob:
                ny = min(max(ny, 1), h - 2)
                nx = min(max(nx, 0), w - 1)
                o[ny][nx] = col
    return o


def _dist_vert(col, cells, h, top, bot, swap=False):
    t, b = (bot, top) if swap else (top, bot)
    if col == t:
        return -(min(y for y, x in cells) - 1)
    if col == b:
        return (h - 2) - max(y for y, x in cells)
    return 0


def full(g):
    return _render(g, lambda c, cl, h, w, t, b: (_dist_vert(c, cl, h, t, b), 0))


def swapped(inp, out):
    return _render(inp, lambda c, cl, h, w, t, b: (_dist_vert(c, cl, h, t, b, True), 0))


def erase(inp, out):
    return _blank(inp)


def short_by_one(inp, out):
    def m(c, cl, h, w, t, b):
        d = _dist_vert(c, cl, h, t, b)
        return ((abs(d) - 1) * (1 if d > 0 else -1) if d else 0, 0)
    return _render(inp, m)


def cells_fall(inp, out):
    h, w, top, bot, bg = _setup(inp)
    o = _blank(inp)
    for x in range(w):
        up = [inp[y][x] for y in range(1, h - 1) if inp[y][x] == top]
        dn = [inp[y][x] for y in range(1, h - 1) if inp[y][x] == bot]
        for i, c in enumerate(up):
            o[1 + i][x] = c
        for i, c in enumerate(dn):
            o[h - 2 - i][x] = c
    return o


def four_connected(inp, out):
    return _render(inp, lambda c, cl, h, w, t, b: (_dist_vert(c, cl, h, t, b), 0), diag=False)


def only_top_color_moves(inp, out):
    h, w, top, bot, bg = _setup(inp)
    o = [list(r) for r in inp]
    for col, cells in _comps(inp):
        if col == top:
            for y, x in cells:
                o[y][x] = bg
    for col, cells in _comps(inp):
        if col == top:
            d = _dist_vert(col, cells, h, top, bot)
            for y, x in cells:
                o[y + d][x] = col
    return o


def only_bottom_color_moves(inp, out):
    h, w, top, bot, bg = _setup(inp)
    o = [list(r) for r in inp]
    for col, cells in _comps(inp):
        if col == bot:
            for y, x in cells:
                o[y][x] = bg
    for col, cells in _comps(inp):
        if col == bot:
            d = _dist_vert(col, cells, h, top, bot)
            for y, x in cells:
                o[y + d][x] = col
    return o


def sideways(inp, out):
    def m(c, cl, h, w, t, b):
        if c == t:
            return (0, -min(x for y, x in cl))
        if c == b:
            return (0, (w - 1) - max(x for y, x in cl))
        return (0, 0)
    return _render(inp, m)


def leave_copy(inp, out):
    return _render(inp, lambda c, cl, h, w, t, b: (_dist_vert(c, cl, h, t, b), 0), keep_orig=True)


def farthest_cell_distance(inp, out):
    # distance taken from the cell farthest from the border; cells past the border are dropped
    def m(c, cl, h, w, t, b):
        if c == t:
            return (-(max(y for y, x in cl) - 1), 0)
        if c == b:
            return ((h - 2) - min(y for y, x in cl), 0)
        return (0, 0)
    return _render(inp, m, drop_oob=True)


def move_half(inp, out):
    def m(c, cl, h, w, t, b):
        d = _dist_vert(c, cl, h, t, b)
        return (int(d / 2), 0)
    return _render(inp, m)


ALTERNATIVES = [
    ("each color goes to the opposite border", swapped),
    ("objects are erased instead of moved", erase),
    ("objects stop one row short of the border", short_by_one),
    ("each cell falls on its own, shapes not kept", cells_fall),
    ("objects use 4-connectivity, so diagonal parts move separately", four_connected),
    ("only objects of the top border color move", only_top_color_moves),
    ("only objects of the bottom border color move", only_bottom_color_moves),
    ("objects move sideways to the left and right edges", sideways),
    ("objects move but their original cells stay", leave_copy),
    ("travel distance from the farthest cell, cells past the border are cut", farthest_cell_distance),
    ("objects travel only half the way", move_half),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/17829a00.json'))
    train = task["train"]
    print("sanity: correct rule matches", [full(p["input"]) == p["output"] for p in train])
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
