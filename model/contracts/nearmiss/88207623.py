import json
from pathlib import Path

LINE, SHAPE = 2, 4


def info(inp):
    """Vertical line segments of color 2, each with its band's shape cells and dot."""
    H, W = len(inp), len(inp[0])
    cols = {}
    for r in range(H):
        for c in range(W):
            if inp[r][c] == LINE:
                cols.setdefault(c, []).append(r)
    lines = []
    for c, rows in sorted(cols.items()):
        rows.sort()
        start = rows[0]
        prev = rows[0]
        for r in rows[1:] + [None]:
            if r is None or r != prev + 1:
                lines.append({"L": c, "r0": start, "r1": prev})
                start = r
            prev = r
    for ln in lines:
        band = range(ln["r0"], ln["r1"] + 1)
        ln["shape"] = [(r, c) for r in band for c in range(W) if inp[r][c] == SHAPE]
        ln["dot"] = None
        for r in band:
            for c in range(W):
                if inp[r][c] not in (0, LINE, SHAPE):
                    ln["dot"] = (r, c, inp[r][c])
    lines.sort(key=lambda ln: ln["r0"])
    return lines


def paint(grid, cells, color):
    H, W = len(grid), len(grid[0])
    for r, c in cells:
        if 0 <= r < H and 0 <= c < W:
            grid[r][c] = color


def mirror(cells, L):
    return [(r, 2 * L - c) for r, c in cells]


def copy(g):
    return [row[:] for row in g]


def usable(inp):
    ls = info(inp)
    if not ls or any(ln["dot"] is None for ln in ls):
        return None
    return ls


def shape_color_kept(inp, out):
    ls = usable(inp)
    if ls is None:
        return None
    g = copy(inp)
    for ln in ls:
        paint(g, mirror(ln["shape"], ln["L"]), SHAPE)
    return g


def moved_not_copied(inp, out):
    ls = usable(inp)
    if ls is None:
        return None
    g = copy(inp)
    for ln in ls:
        paint(g, ln["shape"], 0)
    for ln in ls:
        paint(g, mirror(ln["shape"], ln["L"]), ln["dot"][2])
    return g


def translated_not_flipped(inp, out):
    ls = usable(inp)
    if ls is None:
        return None
    g = copy(inp)
    for ln in ls:
        cs = [c for _, c in ln["shape"]]
        shift = (2 * ln["L"] - max(cs)) - min(cs)
        paint(g, [(r, c + shift) for r, c in ln["shape"]], ln["dot"][2])
    return g


def axis_off_by_one(inp, out):
    ls = usable(inp)
    if ls is None:
        return None
    g = copy(inp)
    for ln in ls:
        L = ln["L"]
        cells = []
        for r, c in ln["shape"]:
            s = 1 if c < L else -1
            cells.append((r, 2 * L - c + s))
        paint(g, cells, ln["dot"][2])
    return g


def rotated_half_turn(inp, out):
    ls = usable(inp)
    if ls is None:
        return None
    g = copy(inp)
    for ln in ls:
        cells = [(ln["r0"] + ln["r1"] - r, 2 * ln["L"] - c) for r, c in ln["shape"]]
        paint(g, cells, ln["dot"][2])
    return g


def one_dot_color_for_all(inp, out):
    ls = usable(inp)
    if ls is None:
        return None
    color = ls[0]["dot"][2]
    g = copy(inp)
    for ln in ls:
        paint(g, mirror(ln["shape"], ln["L"]), color)
    return g


def only_first_line(inp, out):
    ls = usable(inp)
    if ls is None:
        return None
    g = copy(inp)
    ln = ls[0]
    paint(g, mirror(ln["shape"], ln["L"]), ln["dot"][2])
    return g


def dot_colors_swapped(inp, out):
    ls = usable(inp)
    if ls is None or len(ls) < 2:
        return None
    g = copy(inp)
    for i, ln in enumerate(ls):
        color = ls[(i + 1) % len(ls)]["dot"][2]
        paint(g, mirror(ln["shape"], ln["L"]), color)
    return g


def every_shape_across_every_line(inp, out):
    ls = usable(inp)
    if ls is None:
        return None
    allshape = [(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] == SHAPE]
    g = copy(inp)
    for ln in ls:
        paint(g, mirror(allshape, ln["L"]), ln["dot"][2])
    return g


def only_cells_next_to_line(inp, out):
    ls = usable(inp)
    if ls is None:
        return None
    g = copy(inp)
    for ln in ls:
        near = [(r, c) for r, c in ln["shape"] if abs(c - ln["L"]) == 1]
        paint(g, mirror(near, ln["L"]), ln["dot"][2])
    return g


def filled_mirrored_box(inp, out):
    ls = usable(inp)
    if ls is None:
        return None
    g = copy(inp)
    for ln in ls:
        m = mirror(ln["shape"], ln["L"])
        rs = [r for r, _ in m]
        cs = [c for _, c in m]
        box = [(r, c) for r in range(min(rs), max(rs) + 1) for c in range(min(cs), max(cs) + 1)]
        paint(g, box, ln["dot"][2])
    return g


ALTERNATIVES = [
    ("Mirrored shape keeps the shape color 4 instead of taking the dot color", shape_color_kept),
    ("Shape moves across the line: original cells are erased", moved_not_copied),
    ("Shape is translated across the line without flipping", translated_not_flipped),
    ("Mirror axis is one column off, away from the line", axis_off_by_one),
    ("Shape is rotated a half turn about the line's center instead of mirrored", rotated_half_turn),
    ("All lines use the first line's dot color", one_dot_color_for_all),
    ("Only the topmost line reflects its shape", only_first_line),
    ("Each line takes the dot color of the next line", dot_colors_swapped),
    ("Every shape cell in the grid reflects across every line", every_shape_across_every_line),
    ("Only shape cells adjacent to the line reflect", only_cells_next_to_line),
    ("Whole bounding box of the mirrored shape is filled with the dot color", filled_mirrored_box),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not isinstance(g[0], list):
        return False
    w = len(g[0])
    for row in g:
        if not isinstance(row, list) or len(row) != w:
            return False
        for v in row:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/88207623.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
