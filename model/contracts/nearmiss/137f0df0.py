import json
from pathlib import Path


def _analyze(inp):
    h, w = len(inp), len(inp[0])
    blocks = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != 0]
    r0 = min(r for r, c in blocks)
    r1 = max(r for r, c in blocks)
    c0 = min(c for r, c in blocks)
    c1 = max(c for r, c in blocks)
    busy_rows = {r for r, c in blocks}
    busy_cols = {c for r, c in blocks}
    return h, w, (r0, r1, c0, c1), busy_rows, busy_cols


def _solve(inp, inside=2, outside=1, use_rows=True, use_cols=True,
           box_delta=(0, 0, 0, 0), full_width=False, low_side=True,
           high_side=True, paint_empty_lines=False):
    h, w, (r0, r1, c0, c1), busy_rows, busy_cols = _analyze(inp)
    r0 += box_delta[0]
    r1 += box_delta[1]
    c0 += box_delta[2]
    c1 += box_delta[3]
    if full_width:
        c0, c1 = 0, w - 1
    g = [row[:] for row in inp]
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0:
                continue
            in_box = r0 <= r <= r1 and c0 <= c <= c1
            row_free = use_rows and r not in busy_rows
            col_free = use_cols and c not in busy_cols
            row_hit = row_free and (r0 <= r <= r1)
            col_hit = col_free and (c0 <= c <= c1)
            if in_box and (row_free or col_free):
                g[r][c] = inside
                continue
            # outside the box: a free line runs on past the box edge
            paint = False
            if row_hit and not in_box:
                side_low = c < c0
                paint = paint or (side_low and low_side) or (not side_low and high_side)
            if col_hit and not in_box:
                side_low = r < r0
                paint = paint or (side_low and low_side) or (not side_low and high_side)
            if paint_empty_lines and not in_box and (row_free or col_free):
                paint = True
            if paint:
                g[r][c] = outside
    return g


def swap_colors(inp, out):
    m = {1: 2, 2: 1}
    return [[m.get(v, v) for v in row] for row in out]


def no_outside(inp, out):
    return [[0 if v == 1 else v for v in row] for row in out]


def single_color(inp, out):
    return [[2 if v == 1 else v for v in row] for row in out]


def rows_only(inp, out):
    return _solve(inp, use_cols=False)


def cols_only(inp, out):
    return _solve(inp, use_rows=False)


def box_shrunk(inp, out):
    return _solve(inp, box_delta=(0, -1, 0, -1))


def box_grown(inp, out):
    return _solve(inp, box_delta=(-1, 1, -1, 1))


def full_width_box(inp, out):
    return _solve(inp, full_width=True)


def empty_lines_whole(inp, out):
    return _solve(inp, paint_empty_lines=True)


def high_side_only(inp, out):
    return _solve(inp, low_side=False)


def rows_outside_cols_inside(inp, out):
    # beyond the box, columns get the inside color and rows the outside color
    h, w, (r0, r1, c0, c1), busy_rows, busy_cols = _analyze(inp)
    g = [row[:] for row in out]
    for r in range(h):
        for c in range(w):
            if out[r][c] == 1 and inp[r][c] == 0:
                if c0 <= c <= c1 and (r < r0 or r > r1):
                    g[r][c] = 2
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("inside and outside paint colors swapped (1 inside the box, 2 beyond)", swap_colors),
    ("free lines painted only inside the blocks' bounding box, not beyond it", no_outside),
    ("free lines painted with one color (2) both inside and beyond the box", single_color),
    ("only block-free rows are painted, block-free columns ignored", rows_only),
    ("only block-free columns are painted, block-free rows ignored", cols_only),
    ("bounding box one row and column too small at the far edge", box_shrunk),
    ("bounding box one cell too large on every side", box_grown),
    ("bounding box spans the full grid width", full_width_box),
    ("fully empty lines outside the box are painted along their whole length", empty_lines_whole),
    ("free lines extend beyond the box only past the high (right/bottom) edge", high_side_only),
    ("vertical lines beyond the box get the inside color instead of the outside color", rows_outside_cols_inside),
    ("input returned unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/137f0df0.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
