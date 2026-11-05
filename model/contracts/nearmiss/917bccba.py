import json
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    colors = {v for row in inp for v in row if v}
    rc = cc = None
    for c in colors:
        cells = [(r, k) for r in range(h) for k in range(w) if inp[r][k] == c]
        r0 = min(r for r, _ in cells)
        r1 = max(r for r, _ in cells)
        c0 = min(k for _, k in cells)
        c1 = max(k for _, k in cells)
        if inp[r0][c0] == c and inp[r1][c1] == c and (r1 - r0) < h - 1:
            rc = c
            box = (r0, r1, c0, c1)
    cc = next(c for c in colors if c != rc)
    # cross centre: row and column of cross color that span the grid
    row = next(r for r in range(h) if sum(inp[r][k] == cc for k in range(w)) >= w - (box[3] - box[2] + 1) + 1 and inp[r][0] == cc)
    col = next(k for k in range(w) if inp[0][k] == cc or inp[h - 1][k] == cc)
    return h, w, rc, cc, box, row, col


def _render(inp, row, col, fill=False, rect_over=True, rc_=None, cc_=None, half=None, rowline=True, colline=True, orig=None):
    h, w, rc, cc, (r0, r1, c0, c1), orow, ocol = _parse(inp)
    rc = rc if rc_ is None else rc_
    cc = cc if cc_ is None else cc_
    g = [[0] * w for _ in range(h)]
    if rowline:
        for k in range(w):
            g[row][k] = cc
    else:
        for k in range(w):
            g[orow][k] = cc
    if colline:
        for r in range(h):
            g[r][col] = cc
    else:
        for r in range(h):
            g[r][ocol] = cc
    for r in range(r0, r1 + 1):
        for k in range(c0, c1 + 1):
            edge = r in (r0, r1) or k in (c0, c1)
            if edge or fill:
                g[r][k] = rc
            elif rect_over:
                g[r][k] = 0
    return g


def _corner(which):
    def f(inp, out):
        h, w, rc, cc, (r0, r1, c0, c1), _, _ = _parse(inp)
        r = r0 if which[0] == "t" else r1
        c = c1 if which[1] == "r" else c0
        return _render(inp, r, c)
    return f


def top_left(inp, out):
    return _corner("tl")(inp, out)


def bottom_right(inp, out):
    return _corner("br")(inp, out)


def bottom_left(inp, out):
    return _corner("bl")(inp, out)


def cross_stays(inp, out):
    h, w, rc, cc, box, row, col = _parse(inp)
    return _render(inp, row, col)


def cross_over_rect(inp, out):
    h, w, rc, cc, (r0, r1, c0, c1), _, _ = _parse(inp)
    g = [r[:] for r in out]
    for k in range(w):
        g[r0][k] = cc
    for r in range(h):
        g[r][c1] = cc
    return g


def keep_interior_cross(inp, out):
    h, w, rc, cc, (r0, r1, c0, c1), _, _ = _parse(inp)
    g = [r[:] for r in out]
    for r in range(r0 + 1, r1):
        for k in range(c0 + 1, c1):
            if inp[r][k] == cc:
                g[r][k] = cc
    return g


def only_row_moves(inp, out):
    h, w, rc, cc, (r0, r1, c0, c1), _, _ = _parse(inp)
    return _render(inp, r0, c1, colline=False)


def only_col_moves(inp, out):
    h, w, rc, cc, (r0, r1, c0, c1), _, _ = _parse(inp)
    return _render(inp, r0, c1, rowline=False)


def half_lines(inp, out):
    h, w, rc, cc, (r0, r1, c0, c1), _, _ = _parse(inp)
    g = [r[:] for r in out]
    for k in range(c0):
        g[r0][k] = 0
    for r in range(r0 + 1, h):
        if r < r0 or g[r][c1] == cc:
            g[r][c1] = 0
    return g


def swapped_colors(inp, out):
    h, w, rc, cc, box, _, _ = _parse(inp)
    return [[cc if v == rc else rc if v == cc else v for v in r] for r in out]


def inner_offset(inp, out):
    h, w, rc, cc, (r0, r1, c0, c1), _, _ = _parse(inp)
    return _render(inp, r0 + 1, c1 - 1)


def filled_rect(inp, out):
    h, w, rc, cc, (r0, r1, c0, c1), _, _ = _parse(inp)
    return _render(inp, r0, c1, fill=True)


ALTERNATIVES = [
    ("cross lines meet at the top-left corner of the rectangle", top_left),
    ("cross lines meet at the bottom-right corner of the rectangle", bottom_right),
    ("cross lines meet at the bottom-left corner of the rectangle", bottom_left),
    ("cross stays at its original centre; only the rectangle interior is cleared", cross_stays),
    ("cross lines are drawn over the rectangle border at the right corner", cross_over_rect),
    ("cross moves but cross cells inside the rectangle are left in place", keep_interior_cross),
    ("only the horizontal line moves to the corner; vertical line stays", only_row_moves),
    ("only the vertical line moves to the corner; horizontal line stays", only_col_moves),
    ("cross becomes half-lines running only away from the corner", half_lines),
    ("rectangle and cross colors are swapped", swapped_colors),
    ("cross meets one cell inside the corner (off-by-one offset)", inner_offset),
    ("rectangle is filled solid instead of hollow", filled_rect),
]


def _valid(g):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/917bccba.json").read_text())
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
