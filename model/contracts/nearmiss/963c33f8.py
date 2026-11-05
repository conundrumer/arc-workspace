"""Near-miss readings for ARC task 963c33f8.

Rule: a piece (the cells that are neither background nor debris) falls down.
Each column of the piece travels separately, in jumps of its own height, through
debris. A column lands when its lowest cell (the rarest color) would enter debris.
"""
import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _piece_colors(g):
    b = _bg(g)
    cnt = Counter(v for r in g for v in r if v != b)
    if not cnt:
        return set()
    debris = cnt.most_common(1)[0][0]
    return {v for v in cnt if v != debris}


def _cells(g, cols):
    return [(r, c, v) for r, row in enumerate(g) for c, v in enumerate(row) if v in cols]


def _erased(g, cells, b):
    g = [list(r) for r in g]
    for r, c, _ in cells:
        g[r][c] = b
    return g


def _paint(g, cells):
    H, W = len(g), len(g[0])
    for r, c, v in cells:
        if 0 <= r < H and 0 <= c < W:
            g[r][c] = v
    return g


def _bycol(cells):
    d = {}
    for r, c, v in cells:
        d.setdefault(c, []).append((r, v))
    return {c: sorted(x) for c, x in d.items()}


def _ctx(inp, out):
    b = _bg(inp)
    pcs = _piece_colors(inp)
    return b, pcs, _cells(inp, pcs), _cells(out, pcs)


def erase_only(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    return _erased(inp, pin, b)


def landed_up_one(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    return _paint(_erased(out, pout, b), [(r - 1, c, v) for r, c, v in pout])


def landed_down_one(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    return _paint(_erased(out, pout, b), [(r + 1, c, v) for r, c, v in pout])


def landed_reflected(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    H = len(out)
    return _paint(_erased(out, pout, b), [(H - 1 - r, c, v) for r, c, v in pout])


def colors_swapped(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    cols = sorted(pcs)
    if len(cols) != 2:
        return None
    m = {cols[0]: cols[1], cols[1]: cols[0]}
    return [[m.get(v, v) for v in row] for row in out]


def fall_to_bottom(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    H = len(inp)
    g = _erased(inp, pin, b)
    new = []
    for c, lst in _bycol(pin).items():
        n = len(lst)
        for i, (_, v) in enumerate(lst):
            new.append((H - n + i, c, v))
    return _paint(g, new)


def single_jump(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    g = _erased(inp, pin, b)
    new = []
    for c, lst in _bycol(pin).items():
        n = len(lst)
        new += [(r + n, c, v) for r, v in lst]
    return _paint(g, new)


def copy_not_move(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    return _paint([list(r) for r in out], pin)


def rigid_block(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    ci, co = _bycol(pin), _bycol(pout)
    if set(ci) != set(co):
        return None
    d = min(co[c][0][0] - ci[c][0][0] for c in ci)
    return _paint(_erased(inp, pin, b), [(r + d, c, v) for r, c, v in pin])


def one_jump_short(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    new = []
    for c, lst in _bycol(pout).items():
        n = len(lst)
        new += [(r - n, c, v) for r, v in lst]
    return _paint(_erased(out, pout, b), new)


def falls_left(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    g = _erased(inp, pin, b)
    rows = {}
    for r, c, v in pin:
        rows.setdefault(r, []).append((c, v))
    new = []
    for r, lst in rows.items():
        for i, (_, v) in enumerate(sorted(lst)):
            new.append((r, i, v))
    return _paint(g, new)


def one_color_piece(inp, out):
    b, pcs, pin, pout = _ctx(inp, out)
    if len(pcs) != 2:
        return None
    top = max(pcs, key=lambda v: sum(1 for _, _, x in pout if x == v))
    return [[top if v in pcs else v for v in row] for row in out]


ALTERNATIVES = [
    ("piece is erased and never redrawn", erase_only),
    ("landed piece sits one row too high", landed_up_one),
    ("landed piece sits one row too low", landed_down_one),
    ("piece falls upward: landed cells mirrored top to bottom", landed_reflected),
    ("piece colors swapped (rarest color on top)", colors_swapped),
    ("piece ignores debris and falls to the bottom edge", fall_to_bottom),
    ("each column moves down only one jump", single_jump),
    ("piece is copied down, original left in place", copy_not_move),
    ("piece falls as one rigid block, stopping at the first column to land", rigid_block),
    ("each column stops one jump before its true landing", one_jump_short),
    ("piece slides left along rows instead of falling down", falls_left),
    ("every piece cell takes the most common piece color", one_color_piece),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/963c33f8.json"))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for name, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, name)
