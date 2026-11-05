import json
from pathlib import Path


def _markers(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v]


def _sign(x):
    return (x > 0) - (x < 0)


def _geom(inp):
    (r1, c1), (r2, c2) = _markers(inp)
    dr, dc = r2 - r1, c2 - c1
    sr, sc = _sign(dr), _sign(dc)
    m = min(abs(dr), abs(dc))
    s = abs(abs(dr) - abs(dc))
    straight = (sr, 0) if abs(dr) > abs(dc) else (0, sc)
    return (r1, c1), (r2, c2), straight, (sr, sc), s, m


def _walk(start, steps):
    r, c = start
    cells = []
    for (d, n) in steps:
        for _ in range(n):
            r, c = r + d[0], c + d[1]
            cells.append((r, c))
    return cells


def _path_color(inp, out):
    for row_i, row_o in zip(inp, out):
        for a, b in zip(row_i, row_o):
            if a != b:
                return b
    return 3


def _paint(inp, cells, color, keep_markers=True):
    g = [row[:] for row in inp]
    mk = set(_markers(inp))
    h, w = len(g), len(g[0])
    for r, c in cells:
        if 0 <= r < h and 0 <= c < w and not (keep_markers and (r, c) in mk):
            g[r][c] = color
    return g


def _straight_first(inp):
    a, b, st, dg, s, m = _geom(inp)
    return _walk(a, [(st, s), (dg, m)])


def _diag_first(inp):
    a, b, st, dg, s, m = _geom(inp)
    return _walk(a, [(dg, m), (st, s)])


def only_straight_first(inp, out):
    return _paint(inp, _straight_first(inp), _path_color(inp, out))


def only_diag_first(inp, out):
    return _paint(inp, _diag_first(inp), _path_color(inp, out))


def rook_l_paths(inp, out):
    a, b, st, dg, s, m = _geom(inp)
    (r1, c1), (r2, c2) = a, b
    cells = []
    cells += [(r, c1) for r in range(min(r1, r2), max(r1, r2) + 1)]
    cells += [(r2, c) for c in range(min(c1, c2), max(c1, c2) + 1)]
    cells += [(r1, c) for c in range(min(c1, c2), max(c1, c2) + 1)]
    cells += [(r, c2) for r in range(min(r1, r2), max(r1, r2) + 1)]
    return _paint(inp, cells, _path_color(inp, out))


def diagonals_only(inp, out):
    a, b, st, dg, s, m = _geom(inp)
    cells = _walk(a, [(dg, m)]) + _walk(b, [((-dg[0], -dg[1]), m)])
    return _paint(inp, cells, _path_color(inp, out))


def markers_overpainted(inp, out):
    g = [row[:] for row in out]
    col = _path_color(inp, out)
    for r, c in _markers(inp):
        g[r][c] = col
    return g


def marker_colored_paths(inp, out):
    mc = inp[_markers(inp)[0][0]][_markers(inp)[0][1]]
    pc = _path_color(inp, out)
    return [[mc if v == pc else v for v in row] for row in out]


def split_diagonal_middle(inp, out):
    a, b, st, dg, s, m = _geom(inp)
    h1 = m // 2
    p1 = _walk(a, [(dg, h1), (st, s), (dg, m - h1)])
    p2 = _walk(a, [(dg, m - h1), (st, s), (dg, h1)])
    return _paint(inp, p1 + p2, _path_color(inp, out))


def filled_between_paths(inp, out):
    col = _path_color(inp, out)
    mk = _markers(inp)
    cells = set(_straight_first(inp) + _diag_first(inp) + mk)
    rows = {}
    for r, c in cells:
        rows.setdefault(r, []).append(c)
    fill = [(r, c) for r, cs in rows.items() for c in range(min(cs), max(cs) + 1)]
    return _paint(inp, fill, col)


def bounding_box_crop(inp, out):
    mk = _markers(inp)
    r0, r1 = min(r for r, _ in mk), max(r for r, _ in mk)
    c0, c1 = min(c for _, c in mk), max(c for _, c in mk)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def paths_stop_one_short(inp, out):
    # path cells adjacent to either marker are left unpainted
    col = _path_color(inp, out)
    mk = _markers(inp)
    g = [row[:] for row in out]
    h, w = len(g), len(g[0])
    for r, c in mk:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w and g[rr][cc] == col:
                    g[rr][cc] = 0
    return g


def diagonal_rays_to_edge(inp, out):
    col = _path_color(inp, out)
    h, w = len(inp), len(inp[0])
    cells = []
    for r, c in _markers(inp):
        for dr in (-1, 1):
            for dc in (-1, 1):
                rr, cc = r + dr, c + dc
                while 0 <= rr < h and 0 <= cc < w:
                    cells.append((rr, cc))
                    rr, cc = rr + dr, cc + dc
    return _paint(inp, cells, col)


def swapped_straight_axis(inp, out):
    # straight run drawn along the axis of the smaller offset, from the same start
    a, b, st, dg, s, m = _geom(inp)
    st2 = (0, dg[1]) if st[0] else (dg[0], 0)
    cells = _walk(a, [(st2, s), (dg, m)]) + _walk(a, [(dg, m), (st2, s)])
    return _paint(inp, cells, _path_color(inp, out))


ALTERNATIVES = [
    ("only the path that runs straight first from the first marker", only_straight_first),
    ("only the path that runs diagonal first from the first marker", only_diag_first),
    ("rook-style rectangle outline between the markers instead of king paths", rook_l_paths),
    ("only the two diagonal runs, straight runs omitted", diagonals_only),
    ("markers repainted with the path color", markers_overpainted),
    ("paths drawn in the marker color", marker_colored_paths),
    ("diagonal run split around a middle straight run", split_diagonal_middle),
    ("whole region between the two paths filled", filled_between_paths),
    ("output cropped to the markers' bounding box", bounding_box_crop),
    ("path cells next to the markers left unpainted", paths_stop_one_short),
    ("diagonal rays from both markers extended to the grid edge", diagonal_rays_to_edge),
    ("straight run drawn along the axis of the smaller offset", swapped_straight_axis),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/cb227835.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
