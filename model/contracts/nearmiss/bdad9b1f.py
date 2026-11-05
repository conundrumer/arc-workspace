import json
from pathlib import Path


def _parse(inp):
    """Return (vcolor, col, hcolor, row, vcells, hcells) for the two segments."""
    cells = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v:
                cells.setdefault(v, []).append((r, c))
    v = h = None
    for color, pts in cells.items():
        if len({c for _, c in pts}) == 1 and len(pts) > 1:
            v = color
        elif len({r for r, _ in pts}) == 1:
            h = color
    vcells, hcells = cells[v], cells[h]
    return v, vcells[0][1], h, hcells[0][0], vcells, hcells


def _draw(inp, vcol, hcol, cross, vfill=True, hfill=True, vcolor_axis="v", shift_row=0, shift_col=0):
    n, m = len(inp), len(inp[0])
    v, col, h, row, _, _ = _parse(inp)
    g = [[0] * m for _ in range(n)]
    col = min(max(col + shift_col, 0), m - 1)
    row = min(max(row + shift_row, 0), n - 1)
    if vfill:
        for r in range(n):
            g[r][col] = vcol
    if hfill:
        for c in range(m):
            g[row][c] = hcol
    if vfill and hfill:
        g[row][col] = cross
    return g


def cross_keeps_vertical(inp, out):
    v, _, h, _, _, _ = _parse(inp)
    return _draw(inp, v, h, v)


def cross_keeps_horizontal(inp, out):
    v, _, h, _, _, _ = _parse(inp)
    return _draw(inp, v, h, h)


def cross_zero(inp, out):
    v, _, h, _, _, _ = _parse(inp)
    return _draw(inp, v, h, 0)


def cross_wrong_color(inp, out):
    v, _, h, _, _, _ = _parse(inp)
    return _draw(inp, v, h, 3)


def swapped_axes(inp, out):
    # each color extends along the other axis (8 horizontal, 2 vertical)
    n, m = len(inp), len(inp[0])
    v, col, h, row, vcells, hcells = _parse(inp)
    g = [[0] * m for _ in range(n)]
    r0 = vcells[0][0]
    c0 = hcells[0][1]
    for c in range(m):
        g[r0][c] = v
    for r in range(n):
        g[r][c0] = h
    g[r0][c0] = 4
    return g


def only_vertical_extended(inp, out):
    v, _, h, _, _, hcells = _parse(inp)
    g = _draw(inp, v, h, v, hfill=False)
    for r, c in hcells:
        g[r][c] = h
    return g


def only_horizontal_extended(inp, out):
    v, _, h, _, vcells, _ = _parse(inp)
    g = _draw(inp, v, h, h, vfill=False)
    for r, c in vcells:
        g[r][c] = v
    return g


def horizontal_stops_at_crossing(inp, out):
    n, m = len(inp), len(inp[0])
    v, col, h, row, vcells, hcells = _parse(inp)
    g = [r[:] for r in out]
    hc = [c for _, c in hcells]
    if max(hc) < col:
        rng = range(col + 1, m)
    else:
        rng = range(0, col)
    for c in rng:
        g[row][c] = 0
    return g


def vertical_stops_at_crossing(inp, out):
    n, m = len(inp), len(inp[0])
    v, col, h, row, vcells, hcells = _parse(inp)
    g = [r[:] for r in out]
    vr = [r for r, _ in vcells]
    if max(vr) < row:
        rng = range(row + 1, n)
    else:
        rng = range(0, row)
    for r in rng:
        g[r][col] = 0
    return g


def horizontal_line_row_off_by_one(inp, out):
    v, _, h, _, _, _ = _parse(inp)
    return _draw(inp, v, h, 4, shift_row=1)


def vertical_line_col_off_by_one(inp, out):
    v, _, h, _, _, _ = _parse(inp)
    return _draw(inp, v, h, 4, shift_col=1)


def extend_one_cell_only(inp, out):
    # segments grow by a single cell at each end instead of reaching the grid edge
    n, m = len(inp), len(inp[0])
    v, col, h, row, vcells, hcells = _parse(inp)
    g = [[0] * m for _ in range(n)]
    for r in range(max(min(r for r, _ in vcells) - 1, 0), min(max(r for r, _ in vcells) + 2, n)):
        g[r][col] = v
    for c in range(max(min(c for _, c in hcells) - 1, 0), min(max(c for _, c in hcells) + 2, m)):
        g[row][c] = h
    if g[row][col] and g[row][col] != 0:
        g[row][col] = 4
    return g


ALTERNATIVES = [
    ("crossing cell keeps the vertical line color instead of 4", cross_keeps_vertical),
    ("crossing cell keeps the horizontal line color instead of 4", cross_keeps_horizontal),
    ("crossing cell left empty (0)", cross_zero),
    ("crossing cell painted with a wrong color (3)", cross_wrong_color),
    ("each color extends along the other axis (8 horizontal, 2 vertical)", swapped_axes),
    ("only the vertical segment is extended", only_vertical_extended),
    ("only the horizontal segment is extended", only_horizontal_extended),
    ("horizontal line stops at the crossing instead of reaching the far edge", horizontal_stops_at_crossing),
    ("vertical line stops at the crossing instead of reaching the far edge", vertical_stops_at_crossing),
    ("horizontal line drawn one row too low", horizontal_line_row_off_by_one),
    ("vertical line drawn one column too far right", vertical_line_col_off_by_one),
    ("segments grow by one cell per end instead of reaching the edges", extend_one_cell_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(x, int) and 0 <= x <= 9 for r in g for x in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/bdad9b1f.json').read_text())
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(train)}  {desc}")
