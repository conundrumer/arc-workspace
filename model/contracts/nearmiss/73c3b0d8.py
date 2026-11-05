import json
from pathlib import Path


def _dims(g):
    return len(g), len(g[0])


def _blank(inp):
    return [[0 if v == 4 else v for v in row] for row in inp]


def _fours(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 4]


def _is_wall(inp, r, c):
    h, w = _dims(inp)
    return 0 <= r < h and 0 <= c < w and inp[r][c] == 2


def _ray(g, r, c, dr, dc, color=4, limit=None, through_wall=False):
    h, w = _dims(g)
    n = 0
    r, c = r + dr, c + dc
    while 0 <= r < h and 0 <= c < w:
        if limit is not None and n >= limit:
            break
        if g[r][c] == 2 and not through_wall:
            break
        g[r][c] = color
        n += 1
        r, c = r + dr, c + dc


def _build(inp, step=1, dr=1, ray_dirs=((-1, -1), (-1, 1)), ray_all=False,
           ray_from_orig=False, limit=None, color=4, move=True, ray_cond=True,
           through_wall=False):
    """Parametrised solver; the true rule is the defaults."""
    h, w = _dims(inp)
    g = _blank(inp)
    for r, c in _fours(inp):
        nr = r + dr * step
        if move and 0 <= nr < h:
            if g[nr][c] != 2:
                g[nr][c] = 4
        elif not move:
            g[r][c] = 4
        hit = _is_wall(inp, nr + dr, c)
        if ray_all or (hit and ray_cond):
            sr, sc = (r, c) if ray_from_orig else (nr, c)
            for ddr, ddc in ray_dirs:
                _ray(g, sr, sc, ddr, ddc, color=color, limit=limit,
                     through_wall=through_wall)
    return g


def r_all_diag(inp, out):
    return _build(inp, ray_dirs=((-1, -1), (-1, 1), (1, -1), (1, 1)), through_wall=True)


def r_no_rays(inp, out):
    return _build(inp, ray_cond=False)


def r_rays_every_four(inp, out):
    return _build(inp, ray_all=True)


def r_ray_len1(inp, out):
    return _build(inp, limit=1)


def r_ray_color(inp, out):
    return _build(inp, color=8)


def r_no_move(inp, out):
    return _build(inp, move=False)


def r_ray_from_orig(inp, out):
    return _build(inp, ray_from_orig=True)


def r_move_up(inp, out):
    return _build(inp, dr=-1, ray_dirs=((1, -1), (1, 1)), ray_all=True)


def r_move_two(inp, out):
    return _build(inp, step=2, ray_all=True)


def r_slide_to_wall(inp, out):
    h, w = _dims(inp)
    g = _blank(inp)
    for r, c in _fours(inp):
        nr = r
        while nr + 1 < h and inp[nr + 1][c] != 2:
            nr += 1
        g[nr][c] = 4
        if nr + 1 < h and inp[nr + 1][c] == 2:
            for dc in (-1, 1):
                _ray(g, nr, c, -1, dc)
    return g


def r_horizontal_rays(inp, out):
    return _build(inp, ray_dirs=((0, -1), (0, 1)))


def r_vertical_ray(inp, out):
    return _build(inp, ray_dirs=((-1, 0),))


def r_left_ray_only(inp, out):
    return _build(inp, ray_dirs=((-1, -1),))


def r_ray_ends_on_wall_row(inp, out):
    # rays are drawn in all four diagonals but only when the 4 is adjacent to wall,
    # and the moved 4 itself is omitted
    g = _build(inp)
    h, w = _dims(inp)
    for r, c in _fours(inp):
        if _is_wall(inp, r + 2, c) and 0 <= r + 1 < h:
            g[r + 1][c] = 0
    return g


ALTERNATIVES = [
    ("rays go in all four diagonals (downward ones cross the wall row) instead of only the two backward ones", r_all_diag),
    ("fours move one step but no diagonal rays are drawn", r_no_rays),
    ("every moved four emits rays, not only those landing next to the wall", r_rays_every_four),
    ("rays are one cell long instead of reaching the grid edge", r_ray_len1),
    ("rays are drawn in color 8 instead of 4", r_ray_color),
    ("fours stay in place and rays are drawn from them where adjacent to the wall", r_no_move),
    ("rays start from the four's original cell instead of its moved cell", r_ray_from_orig),
    ("fours move up, away from the wall, and rays go downward", r_move_up),
    ("fours move two cells instead of one", r_move_two),
    ("every four slides down until it touches the wall", r_slide_to_wall),
    ("rays go horizontally instead of diagonally", r_horizontal_rays),
    ("single vertical ray upward instead of two diagonals", r_vertical_ray),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/73c3b0d8.json').read_text())
    pairs = task['train']
    # sanity: the true rule reproduces every output
    print('true rule matches:', sum(_build(p['input']) == p['output'] for p in pairs), '/', len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, '/', len(pairs), desc)
