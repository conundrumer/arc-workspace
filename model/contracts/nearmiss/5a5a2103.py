import json
from pathlib import Path


def geom(inp):
    h, w = len(inp), len(inp[0])
    sep = None
    d = None
    for i, row in enumerate(inp):
        if len(set(row)) == 1 and row[0] != 0:
            sep, d = row[0], i
            break
    p = d + 1
    return h, w, sep, d, p, h // p + (1 if h % p == d else 0), w // p + (1 if w % p == d else 0)


def tile_cells(d, p, r, c):
    return [(r * p + i, c * p + j) for i in range(d) for j in range(d)]


def legend_colors(inp):
    h, w, sep, d, p, nr, nc = geom(inp)
    cols = []
    for r in range(nr):
        cs = [inp[y][x] for y, x in tile_cells(d, p, r, 0) if inp[y][x] != 0]
        cols.append(cs[0])
    return cols


def stamp_mask(inp):
    """Local positions inked in any tile outside the legend column."""
    h, w, sep, d, p, nr, nc = geom(inp)
    m = set()
    for r in range(nr):
        for c in range(1, nc):
            for y, x in tile_cells(d, p, r, c):
                if inp[y][x] != 0:
                    m.add((y - r * p, x - c * p))
    return m


def legend_mask(inp):
    h, w, sep, d, p, nr, nc = geom(inp)
    m = set()
    for r in range(nr):
        for y, x in tile_cells(d, p, r, 0):
            if inp[y][x] != 0:
                m.add((y - r * p, x - 0))
    return m


def build(inp, mask_fn, color_fn, keep=None):
    """Copy inp; every tile (except those keep(r,c) says to keep) is redrawn
    with mask_fn(r,c) cells in color_fn(r,c), other cells 0."""
    h, w, sep, d, p, nr, nc = geom(inp)
    g = [row[:] for row in inp]
    for r in range(nr):
        for c in range(nc):
            if keep and keep(r, c):
                continue
            m = mask_fn(r, c)
            col = color_fn(r, c)
            for y, x in tile_cells(d, p, r, c):
                g[y][x] = col if (y - r * p, x - c * p) in m else 0
    return g


def dims(inp):
    h, w, sep, d, p, nr, nc = geom(inp)
    return nr, nc


def stale_legend_column(inp, out):
    # Legend tiles keep their input content instead of being redrawn.
    h, w, sep, d, p, nr, nc = geom(inp)
    g = [row[:] for row in out]
    for r in range(nr):
        for y, x in tile_cells(d, p, r, 0):
            g[y][x] = inp[y][x]
    return g


def legend_shape_stamped(inp, out):
    cols = legend_colors(inp)
    lm = legend_mask(inp)
    return build(inp, lambda r, c: lm, lambda r, c: cols[r])


def marker_color_kept(inp, out):
    h, w, sep, d, p, nr, nc = geom(inp)
    mc = next(inp[y][x] for r in range(nr) for c in range(1, nc)
              for y, x in tile_cells(d, p, r, c) if inp[y][x] != 0)
    sm = stamp_mask(inp)
    return build(inp, lambda r, c: sm, lambda r, c: mc)


def colors_shifted(inp, out):
    cols = legend_colors(inp)
    sm = stamp_mask(inp)
    return build(inp, lambda r, c: sm, lambda r, c: cols[(r + 1) % len(cols)])


def one_color_for_all(inp, out):
    cols = legend_colors(inp)
    sm = stamp_mask(inp)
    return build(inp, lambda r, c: sm, lambda r, c: cols[0])


def marker_tile_left_alone(inp, out):
    h, w, sep, d, p, nr, nc = geom(inp)
    sm = stamp_mask(inp)
    cols = legend_colors(inp)
    marker_tiles = {(r, c) for r in range(nr) for c in range(1, nc)
                    if any(inp[y][x] != 0 for y, x in tile_cells(d, p, r, c))}
    return build(inp, lambda r, c: sm, lambda r, c: cols[r],
                 keep=lambda r, c: (r, c) in marker_tiles)


def only_legend_column_stamped(inp, out):
    sm = stamp_mask(inp)
    cols = legend_colors(inp)
    return build(inp, lambda r, c: sm, lambda r, c: cols[r],
                 keep=lambda r, c: c != 0)


def tiles_filled_solid(inp, out):
    h, w, sep, d, p, nr, nc = geom(inp)
    cols = legend_colors(inp)
    full = {(i, j) for i in range(d) for j in range(d)}
    return build(inp, lambda r, c: full, lambda r, c: cols[r])


def stamp_shifted_down(inp, out):
    h, w, sep, d, p, nr, nc = geom(inp)
    sm = {((i + 1) % d, j) for i, j in stamp_mask(inp)}
    cols = legend_colors(inp)
    return build(inp, lambda r, c: sm, lambda r, c: cols[r])


def stamp_transposed_shifted(inp, out):
    # Marker read with rows and columns swapped, then moved one column right.
    h, w, sep, d, p, nr, nc = geom(inp)
    sm = {(j, (i + 1) % d) for i, j in stamp_mask(inp)}
    cols = legend_colors(inp)
    return build(inp, lambda r, c: sm, lambda r, c: cols[r])


def separators_dropped(inp, out):
    h, w, sep, d, p, nr, nc = geom(inp)
    keep_rows = [i for i in range(h) if i % p != d]
    keep_cols = [j for j in range(w) if j % p != d]
    return [[out[i][j] for j in keep_cols] for i in keep_rows]


def separator_recolored(inp, out):
    h, w, sep, d, p, nr, nc = geom(inp)
    cols = legend_colors(inp)
    g = [row[:] for row in out]
    for i in range(h):
        for j in range(w):
            if g[i][j] == sep:
                g[i][j] = 0
    return g


ALTERNATIVES = [
    ("legend column tiles keep their input content instead of being redrawn", stale_legend_column),
    ("the legend's own shape is stamped in every tile instead of the marker shape", legend_shape_stamped),
    ("the stamp keeps the marker's own color instead of the row's legend color", marker_color_kept),
    ("each row takes the legend color of the next row", colors_shifted),
    ("every row takes the first row's legend color", one_color_for_all),
    ("the tile that holds the marker is left as in the input", marker_tile_left_alone),
    ("only the legend column is stamped; other tiles stay as input", only_legend_column_stamped),
    ("each tile is filled solid with its row color", tiles_filled_solid),
    ("the stamp is shifted down one row inside each tile", stamp_shifted_down),
    ("the stamp is read transposed and shifted one column right", stamp_transposed_shifted),
    ("separator lines are cropped out of the output", separators_dropped),
    ("separator lines are erased to background in the output", separator_recolored),
]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/5a5a2103.json'))
    pairs = task['train']
    print('pairs', len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for pr in pairs:
            try:
                g = f(pr['input'], pr['output'])
            except Exception as e:
                print('  error', desc, repr(e))
                g = None
            n += valid(g, pr['output'])
        print(n, desc)
