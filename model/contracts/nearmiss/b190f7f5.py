import json
from pathlib import Path


def halves(inp):
    h, w = len(inp), len(inp[0])
    if w >= h:
        a = [r[:w // 2] for r in inp]
        b = [r[w // 2:] for r in inp]
    else:
        a = inp[:h // 2]
        b = inp[h // 2:]
    return a, b


def ncolors(g):
    return len({v for r in g for v in r if v != 0})


def split(inp):
    """Return (shape_half, pattern_half) under the correct reading."""
    a, b = halves(inp)
    if ncolors(a) <= ncolors(b):
        return a, b
    return b, a


def shape_color(s):
    return next(v for r in s for v in r if v != 0)


def mask(s):
    return [[1 if v else 0 for v in r] for r in s]


def build(shape, pattern, color_of=None, cell_ok=None):
    """Stamp a 0/1 mask `shape` into every block selected by pattern."""
    n, m = len(shape), len(shape[0])
    pn, pm = len(pattern), len(pattern[0])
    out = [[0] * (pm * m) for _ in range(pn * n)]
    for I in range(pn):
        for J in range(pm):
            pv = pattern[I][J]
            if cell_ok is not None and not cell_ok(pv):
                continue
            c = color_of(pv) if color_of else pv
            for i in range(n):
                for j in range(m):
                    if shape[i][j]:
                        out[I * n + i][J * m + j] = c
    return out


def transpose(g):
    return [list(r) for r in zip(*g)]


def flip_h(g):
    return [r[::-1] for r in g]


def flip_v(g):
    return g[::-1]


def nz(v):
    return v != 0


def swapped_roles(inp, out):
    s, p = split(inp)
    # pattern half used as the shape, template half used as the pattern
    return build(mask(p), s)


def transposed_shape(inp, out):
    s, p = split(inp)
    return build(transpose(mask(s)), p, cell_ok=nz)


def mirrored_shape(inp, out):
    s, p = split(inp)
    return build(flip_h(mask(s)), p, cell_ok=nz)


def flipped_shape_v(inp, out):
    s, p = split(inp)
    return build(flip_v(mask(s)), p, cell_ok=nz)


def inverted_shape(inp, out):
    s, p = split(inp)
    return build([[1 - v for v in r] for r in mask(s)], p, cell_ok=nz)


def template_color_blocks(inp, out):
    s, p = split(inp)
    t = shape_color(s)
    return build(mask(s), p, color_of=lambda v: t, cell_ok=nz)


def background_cells_stamped(inp, out):
    s, p = split(inp)
    t = shape_color(s)
    return build(mask(s), p, color_of=lambda v: v if v else t)


def transposed_pattern(inp, out):
    s, p = split(inp)
    return build(mask(s), transpose(p), cell_ok=nz)


def mirrored_pattern(inp, out):
    s, p = split(inp)
    return build(mask(s), flip_h(p), cell_ok=nz)


def filled_blocks(inp, out):
    s, p = split(inp)
    n, m = len(s), len(s[0])
    return build([[1] * m for _ in range(n)], p, cell_ok=nz)


def shifted_shape(inp, out):
    s, p = split(inp)
    m = mask(s)
    rolled = [r[1:] + r[:1] for r in m]
    return build(rolled, p, cell_ok=nz)


def first_half_is_shape(inp, out):
    a, b = halves(inp)
    return build(mask(a), b, cell_ok=nz)


def one_pattern_color(inp, out):
    s, p = split(inp)
    first = next(v for r in p for v in r if v)
    return build(mask(s), p, color_of=lambda v: first, cell_ok=nz)


ALTERNATIVES = [
    ("pattern half used as the shape and template half as the pattern", swapped_roles),
    ("shape transposed before stamping", transposed_shape),
    ("shape mirrored left-right before stamping", mirrored_shape),
    ("complement of the shape stamped (background cells of the shape inked)", inverted_shape),
    ("blocks inked with the template color instead of the pattern cell color", template_color_blocks),
    ("background pattern cells also get a block, inked with the template color", background_cells_stamped),
    ("pattern grid transposed in the output layout", transposed_pattern),
    ("pattern grid mirrored left-right in the output layout", mirrored_pattern),
    ("each non-background pattern cell becomes a fully filled block, no shape", filled_blocks),
    ("the first half is always taken as the shape", first_half_is_shape),
    ("every block inked with the first pattern color found", one_pattern_color),
    ("shape shifted one column left (wrapping) before stamping", shifted_shape),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/b190f7f5.json'))
    train = task['train']
    print('pairs', len(train))
    for desc, fn in ALTERNATIVES:
        cnt = 0
        for pr in train:
            g = fn(pr['input'], pr['output'])
            if g is not None and _valid(g) and g != pr['output']:
                cnt += 1
        print(cnt, desc)
