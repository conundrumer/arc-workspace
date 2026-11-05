import json
from collections import Counter
from pathlib import Path

MARK = 8


def _shapes(inp):
    """Return (bg, [(color, cells, marker_cell, (dr, dc))])."""
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    cols = sorted({v for r in inp for v in r} - {bg, MARK})
    marks = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == MARK]
    shapes = []
    for c in cols:
        cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == c]
        r0 = min(i for i, _ in cells)
        r1 = max(i for i, _ in cells)
        c0 = min(j for _, j in cells)
        c1 = max(j for _, j in cells)
        mk = None
        for (i, j) in marks:
            if r0 <= i <= r1 and c0 <= j <= c1:
                mk = (i, j)
        if mk is None:
            continue
        dr = -1 if mk[0] == r0 else 1
        dc = -1 if mk[1] == c0 else 1
        shapes.append((c, cells, mk, (dr, dc)))
    return bg, shapes


def _render(inp, f):
    """f(shape) -> list of (cell, color) painted; later shapes overwrite earlier."""
    bg, shapes = _shapes(inp)
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    for s in shapes:
        for (i, j), v in f(s, shapes):
            if 0 <= i < h and 0 <= j < w:
                g[i][j] = v
    return g


def _moved(inp, mv, color=None, keep_marker=False, fill_bite=False):
    def f(s, shapes):
        c, cells, mk, d = s
        dr, dc = mv(d)
        col = c if color is None else color
        out = [((i + dr, j + dc), col) for i, j in cells]
        if keep_marker:
            out.append(((mk[0] + dr, mk[1] + dc), MARK))
        if fill_bite:
            out.append(((mk[0] + dr, mk[1] + dc), col))
        return out
    return _render(inp, f)


def opposite(inp, out):
    return _moved(inp, lambda d: (-d[0], -d[1]))


def two_steps(inp, out):
    return _moved(inp, lambda d: (2 * d[0], 2 * d[1]))


def vertical_only(inp, out):
    return _moved(inp, lambda d: (d[0], 0))


def horizontal_only(inp, out):
    return _moved(inp, lambda d: (0, d[1]))


def keep_marker(inp, out):
    return _moved(inp, lambda d: d, keep_marker=True)


def marker_stays(inp, out):
    def f(s, shapes):
        c, cells, mk, (dr, dc) = s
        return [((i + dr, j + dc), c) for i, j in cells] + [(mk, MARK)]
    return _render(inp, f)


def stay_fill_bite(inp, out):
    return _moved(inp, lambda d: (0, 0), fill_bite=True)


def stay_drop_marker(inp, out):
    return _moved(inp, lambda d: (0, 0))


def trail(inp, out):
    def f(s, shapes):
        c, cells, mk, (dr, dc) = s
        return [((i, j), c) for i, j in cells] + [((i + dr, j + dc), c) for i, j in cells]
    return _render(inp, f)


def only_largest(inp, out):
    def f(s, shapes):
        c, cells, mk, (dr, dc) = s
        if len(cells) == max(len(x[1]) for x in shapes):
            return [((i + dr, j + dc), c) for i, j in cells]
        return [((i, j), c) for i, j in cells]
    return _render(inp, f)


def flip_vertical(inp, out):
    return _moved(inp, lambda d: (-d[0], d[1]))


def swap_axes(inp, out):
    return _moved(inp, lambda d: (d[1], d[0]))


def marker_color(inp, out):
    return _moved(inp, lambda d: d, color=MARK)


ALTERNATIVES = [
    ("shape moves away from the marker corner instead of toward it", opposite),
    ("shape moves two cells diagonally instead of one", two_steps),
    ("shape moves only vertically toward the marker corner", vertical_only),
    ("shape moves only horizontally toward the marker corner", horizontal_only),
    ("shape moves correctly but the marker cell is kept, moved with it", keep_marker),
    ("shape moves but the marker stays at its old cell", marker_stays),
    ("shape stays in place and the bite is filled with the shape color", stay_fill_bite),
    ("shape stays in place and only the marker is erased", stay_drop_marker),
    ("shape moves but leaves its old copy behind as a trail", trail),
    ("only the largest shape moves; the others stay in place", only_largest),
    ("vertical direction taken from the wrong side of the marker", flip_vertical),
    ("row and column components of the direction swapped", swap_axes),
    ("moved shape is painted in the marker color", marker_color),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/470c91de.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
