import json
from pathlib import Path


def objects(inp):
    """Hollow 5-boxes with a gap in the top wall: (r0, r1, c0, c1, gap_col)."""
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0 and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                r0 = min(y for y, _ in cells)
                r1 = max(y for y, _ in cells)
                c0 = min(x for _, x in cells)
                c1 = max(x for _, x in cells)
                gaps = [x for x in range(c0, c1 + 1) if inp[r0][x] == 0]
                res.append((r0, r1, c0, c1, gaps[0]))
    return res


def build(inp, fill_gap=True, color=2, spill_color=None, whole_box=False,
          direction="far", row_off=1, spill=True, which="all", start_off=0,
          interior=True):
    g = [row[:] for row in inp]
    w = len(inp[0])
    sc = color if spill_color is None else spill_color
    objs = sorted(objects(inp))
    for i, (r0, r1, c0, c1, gc) in enumerate(objs):
        if whole_box:
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    g[r][c] = color
        elif interior:
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    if inp[r][c] == 0 and (fill_gap or not (r == r0 and c == gc)):
                        g[r][c] = color
        if not spill or (which == "first" and i > 0):
            continue
        left_len = gc - c0
        right_len = c1 - gc
        far_left = left_len > right_len
        if direction == "far":
            left = far_left
        elif direction == "near":
            left = not far_left
        elif direction == "up":
            left = None
        row = r0 - row_off
        if row < 0:
            continue
        if direction == "both":
            cols = range(0, w)
        elif direction == "up":
            for r in range(0, r0 + 1):
                if g[r][gc] == 0 or r == r0:
                    g[r][gc] = sc
            continue
        elif direction == "box":
            cols = range(c0, gc + 1) if far_left else range(gc, c1 + 1)
        elif left:
            cols = range(0, gc + 1 - start_off)
        else:
            cols = range(gc + start_off, w)
        for c in cols:
            g[row][c] = sc
    return g


def f_nospill(inp, out):
    return build(inp, spill=False)


def f_near(inp, out):
    return build(inp, direction="near")


def f_row2(inp, out):
    return build(inp, row_off=2)


def f_skipgap_col(inp, out):
    return build(inp, start_off=1)


def f_gap_open(inp, out):
    return build(inp, fill_gap=False)


def f_up(inp, out):
    return build(inp, direction="up")


def f_first_only(inp, out):
    if len(objects(inp)) < 2:
        return None
    return build(inp, which="first")


def f_spill_color(inp, out):
    return build(inp, spill_color=8)


def f_both(inp, out):
    return build(inp, direction="both")


def f_wholebox(inp, out):
    return build(inp, whole_box=True)


def f_boxspill(inp, out):
    return build(inp, direction="box")


def f_fill_color(inp, out):
    return build(inp, color=3)


ALTERNATIVES = [
    ("fill the box interior but never spill outside the wall", f_nospill),
    ("spill runs toward the nearer side of the gap instead of the farther", f_near),
    ("spill row sits two rows above the wall instead of one", f_row2),
    ("spill starts one column past the gap column", f_skipgap_col),
    ("fill the interior but leave the gap cell empty", f_gap_open),
    ("spill goes straight up from the gap to the grid edge", f_up),
    ("only the topmost box is filled and spilled, others are left unfilled", f_first_only),
    ("spill drawn in color 8 while the interior is color 2", f_spill_color),
    ("spill runs both ways along the whole row above the wall", f_both),
    ("whole bounding box including walls is painted over", f_wholebox),
    ("spill stops at the bounding box edge instead of the grid edge", f_boxspill),
    ("everything painted in color 3 instead of the new color 2", f_fill_color),
]


def valid(g, true):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
            and g != true)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/4e469f39.json"))
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
