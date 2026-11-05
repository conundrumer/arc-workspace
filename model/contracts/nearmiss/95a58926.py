import json
from pathlib import Path


def _colors(out):
    counts = {}
    for row in out:
        for v in row:
            if v:
                counts[v] = counts.get(v, 0) + 1
    ranked = sorted(counts, key=lambda c: -counts[c])
    return ranked[0], ranked[1]  # mesh color, accent color


def _lines(out):
    h, w = len(out), len(out[0])
    mesh, _ = _colors(out)
    rows = [r for r in range(h) if sum(1 for v in out[r] if v) * 2 > w]
    cols = [c for c in range(w) if sum(1 for r in range(h) if out[r][c]) * 2 > h]
    return rows, cols


def _render(h, w, rows, cols, mesh, acc, line=None, cross=None, hrows=True, vcols=True):
    line = mesh if line is None else line
    cross = acc if cross is None else cross
    g = [[0] * w for _ in range(h)]
    for r in rows if hrows else []:
        for c in range(w):
            g[r][c] = line
    for c in cols if vcols else []:
        for r in range(h):
            g[r][c] = line
    if hrows and vcols:
        for r in rows:
            for c in cols:
                g[r][c] = cross
    return g


def _ctx(out):
    rows, cols = _lines(out)
    mesh, acc = _colors(out)
    return len(out), len(out[0]), rows, cols, mesh, acc


def crossings_mesh_color(inp, out):
    h, w, rows, cols, mesh, acc = _ctx(out)
    return _render(h, w, rows, cols, mesh, acc, cross=mesh)


def crossings_background(inp, out):
    h, w, rows, cols, mesh, acc = _ctx(out)
    return _render(h, w, rows, cols, mesh, acc, cross=0)


def horizontal_only(inp, out):
    h, w, rows, cols, mesh, acc = _ctx(out)
    return _render(h, w, rows, cols, mesh, acc, vcols=False)


def vertical_only(inp, out):
    h, w, rows, cols, mesh, acc = _ctx(out)
    return _render(h, w, rows, cols, mesh, acc, hrows=False)


def last_line_missing(inp, out):
    h, w, rows, cols, mesh, acc = _ctx(out)
    return _render(h, w, rows[:-1], cols[:-1], mesh, acc)


def lines_shifted_by_one(inp, out):
    h, w, rows, cols, mesh, acc = _ctx(out)
    return _render(h, w, [r + 1 for r in rows if r + 1 < h],
                   [c + 1 for c in cols if c + 1 < w], mesh, acc)


def lines_anchored_opposite_corner(inp, out):
    h, w, rows, cols, mesh, acc = _ctx(out)
    return _render(h, w, [h - 1 - r for r in rows], [w - 1 - c for c in cols], mesh, acc)


def only_pure_lines(inp, out):
    h, w, rows, cols, mesh, acc = _ctx(out)
    keep_r = [r for r in rows if all(v == mesh for v in inp[r])]
    keep_c = [c for c in cols if all(inp[r][c] == mesh for r in range(h))]
    return _render(h, w, keep_r, keep_c, mesh, acc)


def accent_noise_kept(inp, out):
    h, w, rows, cols, mesh, acc = _ctx(out)
    g = [row[:] for row in out]
    for r in range(h):
        for c in range(w):
            if inp[r][c] == acc:
                g[r][c] = acc
    return g


def colors_swapped(inp, out):
    h, w, rows, cols, mesh, acc = _ctx(out)
    return _render(h, w, rows, cols, mesh, acc, line=acc, cross=mesh)


def accent_cells_cleared_only(inp, out):
    mesh, acc = _colors(out)
    return [[0 if v == acc else v for v in row] for row in inp]


def crop_last_row_col(inp, out):
    return [row[:-1] for row in out[:-1]]


ALTERNATIVES = [
    ("crossings drawn in the mesh color instead of the accent color", crossings_mesh_color),
    ("crossings left as background", crossings_background),
    ("only the horizontal mesh lines are drawn", horizontal_only),
    ("only the vertical mesh lines are drawn", vertical_only),
    ("the last horizontal and vertical mesh line are missing", last_line_missing),
    ("every mesh line is placed one cell too late", lines_shifted_by_one),
    ("mesh period anchored at the opposite corner", lines_anchored_opposite_corner),
    ("only lines made purely of mesh color in the input count as mesh", only_pure_lines),
    ("accent noise cells off the mesh are kept in the output", accent_noise_kept),
    ("mesh lines drawn in the accent color, crossings in the mesh color", colors_swapped),
    ("input with accent cells cleared, mesh left as found", accent_cells_cleared_only),
    ("true output cropped by one row and one column", crop_last_row_col),
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
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/95a58926.json").read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(1 for p in train if _valid(fn(p["input"], p["output"]), p["output"]))
        print(f"{n}/{len(train)}  {desc}")
