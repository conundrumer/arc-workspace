import json
from pathlib import Path


def _parts(inp):
    h, w = len(inp), len(inp[0])
    tl, tr, bl, br = inp[0][0], inp[0][w - 1], inp[h - 1][0], inp[h - 1][w - 1]
    inner = [row[2:w - 2] for row in inp[2:h - 2]]
    return tl, tr, bl, br, inner


def _render(inner, colors, target=8, shift=0):
    """Replace cells equal to target by the color of their quadrant."""
    tl, tr, bl, br = colors
    n, m = len(inner), len(inner[0])
    hn, hm = n // 2 + shift, m // 2 + shift
    res = []
    for r in range(n):
        row = []
        for c in range(m):
            v = inner[r][c]
            if v == target:
                if r < hn:
                    v = tl if c < hm else tr
                else:
                    v = bl if c < hm else br
            row.append(v)
        res.append(row)
    return res


def _with(inp, colors, **kw):
    return _render(_parts(inp)[4], colors, **kw)


def swap_tr_bl(inp, out):
    tl, tr, bl, br, _ = _parts(inp)
    return _with(inp, (tl, bl, tr, br))


def mirror_lr(inp, out):
    tl, tr, bl, br, _ = _parts(inp)
    return _with(inp, (tr, tl, br, bl))


def mirror_ud(inp, out):
    tl, tr, bl, br, _ = _parts(inp)
    return _with(inp, (bl, br, tl, tr))


def rot180(inp, out):
    tl, tr, bl, br, _ = _parts(inp)
    return _with(inp, (br, bl, tr, tl))


def no_recolor(inp, out):
    return [row[:] for row in _parts(inp)[4]]


def recolor_zeros(inp, out):
    tl, tr, bl, br, inner = _parts(inp)
    return _render(inner, (tl, tr, bl, br), target=0)


def one_color(inp, out):
    tl, _, _, _, inner = _parts(inp)
    return _render(inner, (tl, tl, tl, tl))


def rows_by_left_corner(inp, out):
    tl, tr, bl, br, _ = _parts(inp)
    return _with(inp, (tl, tl, bl, bl))


def cols_by_top_corner(inp, out):
    tl, tr, bl, br, _ = _parts(inp)
    return _with(inp, (tl, tr, tl, tr))


def last_quadrant_unfilled(inp, out):
    res = [row[:] for row in out]
    n, m = len(res), len(res[0])
    for r in range(n // 2, n):
        for c in range(m // 2, m):
            if res[r][c] != 0:
                res[r][c] = 8
    return res


def flipped_pattern(inp, out):
    return [row[::-1] for row in out]


def transposed_pattern(inp, out):
    n, m = len(out), len(out[0])
    return [[out[r][c] for r in range(n)] for c in range(m)]


def with_frame(inp, out):
    h = len(inp)
    w = len(inp[0])
    tl, tr, bl, br, inner = _parts(inp)
    res = _render(inner, (tl, tr, bl, br))
    framed = [[1] * (len(res[0]) + 2)]
    for row in res:
        framed.append([1] + row + [1])
    framed.append([1] * (len(res[0]) + 2))
    return framed


def quadrant_split_shifted(inp, out):
    tl, tr, bl, br, inner = _parts(inp)
    if len(inner) < 4:
        return None
    return _render(inner, (tl, tr, bl, br), shift=1)


ALTERNATIVES = [
    ("top-right and bottom-left corner colors swapped", swap_tr_bl),
    ("corner colors mirrored left-right", mirror_lr),
    ("corner colors mirrored top-bottom", mirror_ud),
    ("corner colors rotated 180 degrees", rot180),
    ("interior cropped but 8 cells not recolored", no_recolor),
    ("0 cells recolored by quadrant instead of 8 cells", recolor_zeros),
    ("every 8 cell takes the top-left corner color", one_color),
    ("top half uses the top-left color, bottom half the bottom-left color", rows_by_left_corner),
    ("bottom-right quadrant left as 8 instead of recolored", last_quadrant_unfilled),
    ("true output mirrored left-right (interior pattern flipped)", flipped_pattern),
    ("output kept inside a ring of 1 separator cells (crop off by one)", with_frame),
    ("quadrant boundary placed one cell too far down and right", quadrant_split_shifted),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/77fdfe62.json').read_text())
    pairs = task['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(f'{n}/{len(pairs)}  {desc}')
