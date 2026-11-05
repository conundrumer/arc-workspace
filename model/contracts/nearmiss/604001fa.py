import json
from collections import Counter
from pathlib import Path

CORNER_COLOR = {(0, 0): 3, (0, 1): 8, (1, 1): 6, (1, 0): 4}


def _comps(inp, conn8=True):
    h, w = len(inp), len(inp[0])
    counts = Counter(v for r in inp for v in r if v != 0)
    mark = min(counts, key=lambda k: (counts[k], k))
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    if not conn8:
        nb = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in nb:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            marks = [p for p in cells if inp[p[0]][p[1]] == mark]
            shape = [p for p in cells if inp[p[0]][p[1]] != mark]
            if not marks:
                res.append(dict(cells=cells, marks=[], shape=shape, box=None, missing=None))
                continue
            r0 = min(p[0] for p in marks)
            r1 = max(p[0] for p in marks)
            c0 = min(p[1] for p in marks)
            c1 = max(p[1] for p in marks)
            ms = set(marks)
            missing = None
            for rr in (0, 1):
                for cc in (0, 1):
                    pos = (r1 if rr else r0, c1 if cc else c0)
                    if pos not in ms:
                        missing = (rr, cc)
            res.append(dict(cells=cells, marks=marks, shape=shape, box=(r0, r1, c0, c1), missing=missing))
    return mark, res


def _render(inp, colorfn, keep_marks=False, conn8=True, recolor_marks=False, fill_corner=False):
    h, w = len(inp), len(inp[0])
    mark, comps = _comps(inp, conn8)
    g = [[0] * w for _ in range(h)]
    for k in comps:
        if k["missing"] is None:
            continue
        col = colorfn(k["missing"])
        if recolor_marks:
            for y, x in k["marks"]:
                g[y][x] = col
        else:
            for y, x in k["shape"]:
                g[y][x] = col
        if keep_marks:
            for y, x in k["marks"]:
                g[y][x] = mark
        if fill_corner:
            r0, r1, c0, c1 = k["box"]
            g[r1 if k["missing"][0] else r0][c1 if k["missing"][1] else c0] = col
    return g


def _copy(g):
    return [list(r) for r in g]


def keep_marks(inp, out):
    return _render(inp, lambda m: CORNER_COLOR[m], keep_marks=True)


def opposite_corner(inp, out):
    return _render(inp, lambda m: CORNER_COLOR[(1 - m[0], 1 - m[1])])


def mirror_horizontal(inp, out):
    return _render(inp, lambda m: CORNER_COLOR[(m[0], 1 - m[1])])


def mirror_vertical(inp, out):
    return _render(inp, lambda m: CORNER_COLOR[(1 - m[0], m[1])])


def rotated_corner(inp, out):
    order = [(0, 0), (0, 1), (1, 1), (1, 0)]
    return _render(inp, lambda m: CORNER_COLOR[order[(order.index(m) + 1) % 4]])


def recolor_marks_not_shape(inp, out):
    return _render(inp, lambda m: CORNER_COLOR[m], recolor_marks=True)


def shape_unchanged_marks_removed(inp, out):
    mark, comps = _comps(inp)
    h, w = len(inp), len(inp[0])
    return [[0 if inp[y][x] == mark else inp[y][x] for x in range(w)] for y in range(h)]


def fill_missing_corner_too(inp, out):
    return _render(inp, lambda m: CORNER_COLOR[m], fill_corner=True)


def one_color_for_all(inp, out):
    mark, comps = _comps(inp)
    cols = [CORNER_COLOR[k["missing"]] for k in comps if k["missing"] is not None]
    if len(set(cols)) < 2:
        return None
    return _render(inp, lambda m: cols[0])


def four_connected(inp, out):
    mark, comps = _comps(inp, conn8=False)
    # components without marks stay uncoloured; a split shape loses its colour
    return _render(inp, lambda m: CORNER_COLOR[m], conn8=False)


def shifted_down_one(inp, out):
    h, w = len(out), len(out[0])
    return [[0] * w] + _copy(out[:-1])


def shifted_right_one(inp, out):
    return [[0] + list(r[:-1]) for r in out]


def shape_bbox_filled(inp, out):
    # colour every non-marked cell inside each mark box, not only the shape cells
    g = _copy(out)
    mark, comps = _comps(inp)
    for k in comps:
        if k["box"] is None:
            continue
        r0, r1, c0, c1 = k["box"]
        for y in range(r0, r1 + 1):
            for x in range(c0, c1 + 1):
                g[y][x] = CORNER_COLOR[k["missing"]]
    return g


ALTERNATIVES = [
    ("marks (7) kept in output instead of erased", keep_marks),
    ("colour taken from the corner opposite the missing one", opposite_corner),
    ("left and right corner colours swapped", mirror_horizontal),
    ("top and bottom corner colours swapped", mirror_vertical),
    ("colour taken from the next corner clockwise", rotated_corner),
    ("mark cells recoloured and shape cells erased", recolor_marks_not_shape),
    ("shape keeps its input colour, marks erased", shape_unchanged_marks_removed),
    ("missing corner cell of the mark box also painted", fill_missing_corner_too),
    ("every shape gets the colour of the first shape", one_color_for_all),
    ("4-connected components used instead of 8-connected", four_connected),
    ("true output shifted down one row", shifted_down_one),
    ("true output shifted right one column", shifted_right_one),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/604001fa.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
