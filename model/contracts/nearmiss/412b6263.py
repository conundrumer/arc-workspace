from pathlib import Path
import json


def ccw(g):
    h, w = len(g), len(g[0])
    return [[g[j][w - 1 - i] for j in range(h)] for i in range(w)]


def cw(g):
    h, w = len(g), len(g[0])
    return [[g[h - 1 - j][i] for j in range(h)] for i in range(w)]


def transpose(g):
    return [list(r) for r in zip(*g)]


def flip_v(g):
    return [list(r) for r in reversed(g)]


def build(tile, n, vertical=True, ring=1, corner=7, outer=True, shared=True):
    """Tiles joined by lines of color ring; bg is 7."""
    h, w = len(tile), len(tile[0])
    # a segment list per axis: 'L' = line, int = index within tile
    def seg(size):
        s = []
        for k in range(n if True else 1):
            pass
        return s

    def axis(size, count):
        s = []
        if outer or not shared:
            s.append('L')
        for k in range(count):
            if k > 0:
                s.append('L')
                if not shared:
                    s.append('L')
            s.extend(range(size))
        if outer or not shared:
            s.append('L')
        return s

    rows = axis(h, n if vertical else 1)
    cols = axis(w, 1 if vertical else n)
    if not outer and shared:
        pass
    grid = []
    for r in rows:
        row = []
        for c in cols:
            if r == 'L' and c == 'L':
                row.append(corner)
            elif r == 'L' or c == 'L':
                row.append(ring)
            else:
                row.append(tile[r][c])
        grid.append(row)
    return grid


def true_tile(inp):
    return ccw(inp)


def a_transpose(inp, out):
    return build(transpose(inp), 2)


def a_cw(inp, out):
    return build(cw(inp), 2)


def a_identity(inp, out):
    return build(inp, 2)


def a_flip(inp, out):
    return build(flip_v(ccw(inp)), 2)


def a_horizontal(inp, out):
    return build(ccw(inp), 2, vertical=False)


def a_one_copy(inp, out):
    return build(ccw(inp), 1)


def a_three_copies(inp, out):
    return build(ccw(inp), 3)


def a_corner_ring(inp, out):
    return build(ccw(inp), 2, corner=1)


def a_ring_color(inp, out):
    return build(ccw(inp), 2, ring=5)


def a_no_outer(inp, out):
    return build(ccw(inp), 2, outer=False)


def a_double_lines(inp, out):
    return build(ccw(inp), 2, shared=False)


def a_no_marker(inp, out):
    return [[5 if v == 9 else v for v in r] for r in out]


ALTERNATIVES = [
    ("tile is the transpose of the input, not its counter-clockwise rotation", a_transpose),
    ("tile is the clockwise rotation of the input", a_cw),
    ("tile is the input unrotated", a_identity),
    ("tile is the rotation then flipped top to bottom", a_flip),
    ("copies are stacked horizontally instead of vertically", a_horizontal),
    ("one copy only (copy count taken as 1)", a_one_copy),
    ("three copies (count off by one)", a_three_copies),
    ("junction cells where lines cross are colored like the lines", a_corner_ring),
    ("lines are colored 5 (the block color) instead of 1", a_ring_color),
    ("no outer ring, only the line between copies", a_no_outer),
    ("each copy has its own ring, so two lines between copies", a_double_lines),
    ("the 9 marker cells are painted as 5", a_no_marker),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/412b6263.json')))
    pairs = t["train"]
    # sanity: the correct rule reproduces the output
    ok = all(build(true_tile(p["input"]), 2) == p["output"] for p in pairs)
    print("true rule reproduces outputs:", ok)
    for name, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), name)
