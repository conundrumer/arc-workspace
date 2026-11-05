import json
from collections import Counter
from pathlib import Path

RAY = 2


def _parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    ink = sorted({v for r in inp for v in r if v != bg})
    legend_rows = {i for i in range(h) if all(v != bg for v in inp[i])}
    legend_cols = {j for j in range(w) if all(inp[i][j] != bg for i in range(h))}
    block = [(i, j) for i in range(h) for j in range(w)
             if inp[i][j] != bg and i not in legend_rows and j not in legend_cols]
    return bg, ink, block


def _scale(g, n):
    return [[v for v in row for _ in range(n)] for row in g for _ in range(n)]


def _ray(g, start, d, bg, halt=True, skip=0, paint_over=False):
    """Cells reached from start (exclusive) stepping by d."""
    h, w = len(g), len(g[0])
    cells = []
    i, j = start[0] + d[0], start[1] + d[1]
    while 0 <= i < h and 0 <= j < w:
        if g[i][j] != bg and halt and not paint_over:
            break
        cells.append((i, j))
        i += d[0]
        j += d[1]
    return cells[skip:]


DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def solve(inp, scale=None, color=None, dirs_per_corner=None, corners=(0, 1, 2, 3),
          paint_over=False, include_corner=False, skip=0, rays=True):
    bg, ink, block = _parse(inp)
    n = len(ink) if scale is None else scale
    s = _scale(inp, n)
    if not rays:
        return s
    r0 = min(i for i, _ in block) * n
    r1 = (max(i for i, _ in block) + 1) * n - 1
    c0 = min(j for _, j in block) * n
    c1 = (max(j for _, j in block) + 1) * n - 1
    pts = [(r0, c0), (r0, c1), (r1, c0), (r1, c1)]
    if color is None:
        color = RAY
    res = [row[:] for row in s]
    for k in corners:
        p = pts[k]
        dirs = [DIAG[k]] if dirs_per_corner is None else dirs_per_corner(k)
        for d in dirs:
            cells = _ray(s, p, d, bg, paint_over=paint_over, skip=skip)
            if include_corner:
                cells = [p] + cells
            for (i, j) in cells:
                res[i][j] = color
    return res


def _block_color(inp):
    bg, ink, block = _parse(inp)
    return inp[block[0][0]][block[0][1]]


def _upscaled_rays(inp, out):
    bg, ink, block = _parse(inp)
    n = len(ink)
    h, w = len(inp), len(inp[0])
    small = [row[:] for row in inp]
    r0 = min(i for i, _ in block); r1 = max(i for i, _ in block)
    c0 = min(j for _, j in block); c1 = max(j for _, j in block)
    pts = [(r0, c0), (r0, c1), (r1, c0), (r1, c1)]
    for k, p in enumerate(pts):
        for (i, j) in _ray(inp, p, DIAG[k], bg):
            small[i][j] = RAY
    return _scale(small, n)


def a_scale_plus_one(inp, out):
    return solve(inp, scale=len(_parse(inp)[1]) + 1)


def a_scale_minus_one(inp, out):
    return solve(inp, scale=len(_parse(inp)[1]) - 1)


def a_block_color_rays(inp, out):
    return solve(inp, color=_block_color(inp))


def a_overwrite_legend(inp, out):
    return solve(inp, paint_over=True)


def a_top_corners_only(inp, out):
    return solve(inp, corners=(0, 1))


def a_start_inside(inp, out):
    return solve(inp, include_corner=True)


def a_input_resolution_rays(inp, out):
    return _upscaled_rays(inp, out)


def a_no_rays(inp, out):
    return solve(inp, rays=False)


def a_orthogonal(inp, out):
    ortho = {0: [(-1, 0), (0, -1)], 1: [(-1, 0), (0, 1)],
             2: [(1, 0), (0, -1)], 3: [(1, 0), (0, 1)]}
    return solve(inp, dirs_per_corner=lambda k: ortho[k])


def a_all_diagonals(inp, out):
    return solve(inp, dirs_per_corner=lambda k: DIAG)


def a_gap_before_ray(inp, out):
    return solve(inp, skip=1)


def a_one_diagonal(inp, out):
    return solve(inp, corners=(0, 3))


ALTERNATIVES = [
    ("scale factor is the palette size plus one (background counted)", a_scale_plus_one),
    ("scale factor is the palette size minus one", a_scale_minus_one),
    ("rays take the block's color instead of the new color", a_block_color_rays),
    ("rays are not halted by the legend and overwrite it", a_overwrite_legend),
    ("only the two top corners emit rays", a_top_corners_only),
    ("rays start on the box corner cell, overwriting the block", a_start_inside),
    ("rays are drawn at input resolution then scaled up", a_input_resolution_rays),
    ("no rays are drawn, only the scaled input", a_no_rays),
    ("rays leave the corners horizontally and vertically", a_orthogonal),
    ("each corner emits rays in all four diagonal directions", a_all_diagonals),
    ("rays start one cell away from the box corner", a_gap_before_ray),
    ("only the main-diagonal corners emit rays", a_one_diagonal),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/469497ad.json'))
    train = task['train']
    for p in train:
        assert solve(p['input']) == p['output'], 'reference solver mismatch'
    for desc, f in ALTERNATIVES:
        cnt = 0
        for p in train:
            g = f(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                cnt += 1
        print(f'{cnt}/{len(train)}  {desc}')
