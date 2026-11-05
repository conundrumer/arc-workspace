import json
from collections import Counter
from pathlib import Path

WALL = 5


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _regions(inp, ok):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if (r, c) in seen or not ok(r, c):
                continue
            seen.add((r, c))
            stack = [(r, c)]
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and ok(ny, nx):
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append(cells)
    return comps


def _analyze(inp):
    """Return (holes, shapes, match) for the true rule."""
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    # holes: non-wall regions that do not touch the grid edge
    holes = []
    for comp in _regions(inp, lambda r, c: inp[r][c] != WALL):
        if not any(y in (0, h - 1) or x in (0, w - 1) for y, x in comp):
            holes.append(sorted(comp))
    shapes = []
    for color in set(v for r in inp for v in r) - {bg, WALL}:
        for comp in _regions(inp, lambda r, c, col=color: inp[r][c] == col):
            shapes.append((color, sorted(comp)))

    def norm(cells):
        y0 = min(y for y, _ in cells)
        x0 = min(x for _, x in cells)
        return sorted((y - y0, x - x0) for y, x in cells)

    colcount = Counter(c for c, _ in shapes)
    match = []  # (hole index, shape index)
    for hi, hc in enumerate(holes):
        for si, (col, cells) in enumerate(shapes):
            if colcount[col] == 1 and norm(cells) == norm(hc):
                match.append((hi, si))
    return holes, shapes, match


def _copy(g):
    return [row[:] for row in g]


def _apply(inp, fills=(), erases=()):
    """fills: list of (cells, color); erases: list of cell lists."""
    bg = _bg(inp)
    g = _copy(inp)
    for cells in erases:
        for y, x in cells:
            g[y][x] = bg
    for cells, col in fills:
        for y, x in cells:
            if 0 <= y < len(g) and 0 <= x < len(g[0]):
                g[y][x] = col
    return g


def _true_parts(inp):
    holes, shapes, match = _analyze(inp)
    fills = [(holes[hi], shapes[si][0]) for hi, si in match]
    erases = [shapes[si][1] for _, si in match]
    return holes, shapes, match, fills, erases


def unchanged(inp, out):
    return _copy(inp)


def fill_no_erase(inp, out):
    holes, shapes, match, fills, erases = _true_parts(inp)
    return _apply(inp, fills, [])


def erase_no_fill(inp, out):
    holes, shapes, match, fills, erases = _true_parts(inp)
    return _apply(inp, [], erases)


def only_first_hole(inp, out):
    holes, shapes, match, fills, erases = _true_parts(inp)
    if len(match) < 2:
        return None
    order = sorted(range(len(match)), key=lambda i: min(holes[match[i][0]]))
    k = order[0]
    return _apply(inp, [fills[k]], [erases[k]])


def swapped_colors(inp, out):
    holes, shapes, match, fills, erases = _true_parts(inp)
    if len(match) < 2:
        return None
    new = [(fills[i][0], fills[(i + 1) % len(fills)][1]) for i in range(len(fills))]
    return _apply(inp, new, erases)


def nearest_shape_color(inp, out):
    holes, shapes, match, fills, erases = _true_parts(inp)
    new, er = [], []
    for hc in holes:
        cy = sum(y for y, _ in hc) / len(hc)
        cx = sum(x for _, x in hc) / len(hc)
        best = min(
            shapes,
            key=lambda s: min(abs(y - cy) + abs(x - cx) for y, x in s[1]),
        )
        new.append((hc, best[0]))
        er.append(best[1])
    return _apply(inp, new, er)


def fill_with_wall_color(inp, out):
    holes, shapes, match, fills, erases = _true_parts(inp)
    return _apply(inp, [(hc, WALL) for hc, _ in fills], erases)


def erase_all_shapes(inp, out):
    holes, shapes, match, fills, erases = _true_parts(inp)
    return _apply(inp, fills, [cells for _, cells in shapes])


def mirrored_fill(inp, out):
    holes, shapes, match, fills, erases = _true_parts(inp)
    new = []
    for hi, si in match:
        cells = shapes[si][1]
        x0 = min(x for _, x in cells)
        x1 = max(x for _, x in cells)
        y0 = min(y for y, _ in cells)
        hy0 = min(y for y, _ in holes[hi])
        hx0 = min(x for _, x in holes[hi])
        new.append(([(y - y0 + hy0, x1 - x + hx0) for y, x in cells], shapes[si][0]))
    return _apply(inp, new, erases)


def offset_fill(inp, out):
    holes, shapes, match, fills, erases = _true_parts(inp)
    new = []
    for hi, si in match:
        new.append(([(y, x + 1) for y, x in holes[hi]], shapes[si][0]))
    return _apply(inp, new, erases)


def bbox_fill(inp, out):
    holes, shapes, match, fills, erases = _true_parts(inp)
    new = []
    for hc, col in fills:
        ys = [y for y, _ in hc]
        xs = [x for _, x in hc]
        cells = [(y, x) for y in range(min(ys), max(ys) + 1) for x in range(min(xs), max(xs) + 1)]
        new.append((cells, col))
    return _apply(inp, new, erases)


def fill_all_shapes_into_holes(inp, out):
    """Every hole takes the color of the largest shape, ignoring footprint."""
    holes, shapes, match, fills, erases = _true_parts(inp)
    big = max(shapes, key=lambda s: len(s[1]))
    return _apply(inp, [(hc, big[0]) for hc in holes], [big[1]])


ALTERNATIVES = [
    ("return the input unchanged", unchanged),
    ("fill holes with the matching shape but leave the shape at its old place", fill_no_erase),
    ("erase the matching shape but leave the holes empty", erase_no_fill),
    ("move only the shape for the top-most hole; the other hole stays empty", only_first_hole),
    ("each hole gets the color of the other hole's matching shape", swapped_colors),
    ("each hole gets the color of the nearest shape, without checking footprint", nearest_shape_color),
    ("fill holes with the wall color instead of the shape color", fill_with_wall_color),
    ("erase every loose shape, not only the ones that moved", erase_all_shapes),
    ("place the shape mirrored left-right in the hole", mirrored_fill),
    ("place the shape one column right of the hole (off-by-one offset)", offset_fill),
    ("fill the whole bounding box of each hole instead of the hole cells", bbox_fill),
    ("every hole gets the color of the largest shape, which alone is erased", fill_all_shapes_into_holes),
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
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/228f6490.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
