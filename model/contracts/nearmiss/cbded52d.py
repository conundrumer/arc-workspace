import json
from pathlib import Path

# 8x8 grid: 3x3 tiles of 2x2 cells, separated by 0 lines at rows/cols 2 and 5.
# Marks are cells that are neither 0 nor the base color 1.


def marks(inp):
    d = {}
    for i, row in enumerate(inp):
        for j, v in enumerate(row):
            if v not in (0, 1):
                key = (v, (i % 3, j % 3))
                d.setdefault(key, []).append((i // 3, j // 3))
    return d


def between(a, b, diagonal=False):
    """Tiles strictly between tiles a and b along a row, a column (or a diagonal)."""
    (r1, c1), (r2, c2) = a, b
    res = []
    if r1 == r2 and c1 != c2:
        res = [(r1, c) for c in range(min(c1, c2) + 1, max(c1, c2))]
    elif c1 == c2 and r1 != r2:
        res = [(r, c1) for r in range(min(r1, r2) + 1, max(r1, r2))]
    elif diagonal and abs(r1 - r2) == abs(c1 - c2) and r1 != r2:
        n = abs(r1 - r2)
        sr = 1 if r2 > r1 else -1
        sc = 1 if c2 > c1 else -1
        res = [(r1 + sr * k, c1 + sc * k) for k in range(1, n)]
    return res


def fills(inp, rows=True, cols=True, diagonal=False):
    out = set()
    for (col, inner), tiles in marks(inp).items():
        for x in tiles:
            for y in tiles:
                if x >= y:
                    continue
                horizontal = x[0] == y[0]
                vertical = x[1] == y[1]
                if horizontal and not rows:
                    continue
                if vertical and not cols:
                    continue
                if not (horizontal or vertical) and not diagonal:
                    continue
                for t in between(x, y, diagonal):
                    out.add((col, inner, t))
    return out


def apply(inp, fl, inner_map=None, whole_tile=False, color=None):
    g = [r[:] for r in inp]
    for col, (ir, ic), (ti, tj) in fl:
        if inner_map:
            ir, ic = inner_map(ir, ic)
        c = col if color is None else color
        if whole_tile:
            for a in range(2):
                for b in range(2):
                    g[3 * ti + a][3 * tj + b] = c
        else:
            g[3 * ti + ir][3 * tj + ic] = c
    return g


def ne(g, out):
    return None if g == out else g


def wrong_color(inp, out):
    g = [r[:] for r in inp]
    for i in range(8):
        for j in range(8):
            if inp[i][j] != out[i][j]:
                g[i][j] = 5
    return g


def whole_tile(inp, out):
    return apply(inp, fills(inp), whole_tile=True)


def vertical_only(inp, out):
    return ne(apply(inp, fills(inp, rows=False)), out)


def horizontal_only(inp, out):
    return ne(apply(inp, fills(inp, cols=False)), out)


def top_left(inp, out):
    return apply(inp, fills(inp), inner_map=lambda r, c: (0, 0))


def mirrored(inp, out):
    return apply(inp, fills(inp), inner_map=lambda r, c: (r, 1 - c))


def all_tiles(inp, out):
    g = [r[:] for r in inp]
    for (col, (ir, ic)) in marks(inp):
        for ti in range(3):
            for tj in range(3):
                g[3 * ti + ir][3 * tj + ic] = col
    return g


def connect_through_gaps(inp, out):
    g = [r[:] for r in inp]
    for (col, (ir, ic)), tiles in marks(inp).items():
        for x in tiles:
            for y in tiles:
                if x >= y:
                    continue
                if x[0] == y[0]:
                    r = 3 * x[0] + ir
                    for c in range(3 * x[1] + ic, 3 * y[1] + ic + 1):
                        g[r][c] = col
                elif x[1] == y[1]:
                    c = 3 * x[1] + ic
                    for r in range(3 * x[0] + ir, 3 * y[0] + ir + 1):
                        g[r][c] = col
    return ne(g, out)


def with_diagonals(inp, out):
    return ne(apply(inp, fills(inp, diagonal=True)), out)


def move_not_copy(inp, out):
    g = [r[:] for r in out]
    for i in range(8):
        for j in range(8):
            if inp[i][j] not in (0, 1):
                g[i][j] = 1
    return g


def drop_separators(inp, out):
    keep = [0, 1, 3, 4, 6, 7]
    return [[out[i][j] for j in keep] for i in keep]


ALTERNATIVES = [
    ("fill cells get the wrong color 5 instead of the mark color", wrong_color),
    ("fill the whole 2x2 tile instead of the single cell at the mark's position", whole_tile),
    ("only vertical pairs of marks fill; horizontal pairs ignored", vertical_only),
    ("only horizontal pairs of marks fill; vertical pairs ignored", horizontal_only),
    ("fill the top-left cell of each in-between tile instead of the mark's position", top_left),
    ("fill the horizontally mirrored position within each in-between tile", mirrored),
    ("copy every mark into all nine tiles, not just between pairs", all_tiles),
    ("draw a continuous line between marks, also across the 0 separator lines", connect_through_gaps),
    ("also fill tiles between marks that lie on a diagonal", with_diagonals),
    ("move marks into the in-between tiles, clearing the original marks", move_not_copy),
    ("output with the 0 separator lines removed (6x6)", drop_separators),
    ("no fill is made, only the original marks remain in the input", lambda inp, out: [r[:] for r in inp]),
]

def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/cbded52d.json").read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
