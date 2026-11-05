import json
from pathlib import Path


def _marks(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def _paint(inp, rows=False, cols=True, color=8, keep_markers=True):
    h, w = len(inp), len(inp[0])
    mk = _marks(inp)
    mr = {r for r, _ in mk}
    mc = {c for _, c in mk}
    g = [row[:] for row in inp]
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0:
                if not keep_markers:
                    g[r][c] = color
                continue
            if (cols and c in mc) or (rows and r in mr):
                g[r][c] = color
    return g


def _tile(g, kr=2, kc=2):
    return [row * kc for row in g] * kr


def rows_instead_of_columns(inp, out):
    return _tile(_paint(inp, rows=True, cols=False))


def rows_and_columns(inp, out):
    return _tile(_paint(inp, rows=True, cols=True))


def marker_color_fill(inp, out):
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for r, c in _marks(inp):
        for rr in range(h):
            if inp[rr][c] == 0:
                g[rr][c] = inp[r][c]
    return _tile(g)


def no_tiling(inp, out):
    return _paint(inp)


def tile_horizontal_only(inp, out):
    return _tile(_paint(inp), 1, 2)


def tile_vertical_only(inp, out):
    return _tile(_paint(inp), 2, 1)


def tile_three_by_three(inp, out):
    return _tile(_paint(inp), 3, 3)


def markers_overpainted(inp, out):
    return _tile(_paint(inp, keep_markers=False))


def paint_only_below_marker(inp, out):
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for r, c in _marks(inp):
        for rr in range(r + 1, h):
            if inp[rr][c] == 0:
                g[rr][c] = 8
    return _tile(g)


def column_shifted_by_one(inp, out):
    h, w = len(inp), len(inp[0])
    mc = {(c + 1) % w for _, c in _marks(inp)}
    g = [row[:] for row in inp]
    for r in range(h):
        for c in mc:
            if inp[r][c] == 0:
                g[r][c] = 8
    return _tile(g)


def mirrored_tiling(inp, out):
    g = _paint(inp)
    top = [row + row[::-1] for row in g]
    return top + top[::-1]


def markers_erased(inp, out):
    g = _paint(inp)
    g = [[8 if inp[r][c] != 0 else v for c, v in enumerate(row)] for r, row in enumerate(g)]
    g = [[0 if inp[r][c] != 0 else v for c, v in enumerate(row)] for r, row in enumerate(g)]
    return _tile(g)


ALTERNATIVES = [
    ("mark the rows of the non-background cells instead of the columns", rows_instead_of_columns),
    ("mark both the rows and the columns of the non-background cells", rows_and_columns),
    ("fill the marked columns with the marker's own color instead of 8", marker_color_fill),
    ("paint the columns but output one copy, with no 2x2 tiling", no_tiling),
    ("tile only side by side (1x2)", tile_horizontal_only),
    ("tile only top to bottom (2x1)", tile_vertical_only),
    ("tile 3x3 instead of 2x2", tile_three_by_three),
    ("paint the marker cells themselves with 8 too", markers_overpainted),
    ("paint only the cells below each marker, not the whole column", paint_only_below_marker),
    ("mark the column right of each marker (off by one, wrapping)", column_shifted_by_one),
    ("tile with mirrored copies instead of plain copies", mirrored_tiling),
    ("erase the markers to background after painting the columns", markers_erased),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/f5b8619d.json").read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, "/", len(train), desc)
