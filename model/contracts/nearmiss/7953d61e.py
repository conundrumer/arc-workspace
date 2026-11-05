import json
from pathlib import Path


def cw(g):
    return [list(r) for r in zip(*g[::-1])]


def ccw(g):
    return [list(r) for r in zip(*g)][::-1]


def r180(g):
    return [r[::-1] for r in g[::-1]]


def fliplr(g):
    return [r[::-1] for r in g]


def flipud(g):
    return [list(r) for r in g[::-1]]


def transpose(g):
    return [list(r) for r in zip(*g)]


def assemble(tl, tr, bl, br):
    return [a + b for a, b in zip(tl, tr)] + [a + b for a, b in zip(bl, br)]


def n_of(inp):
    return len(inp)


def swap_cw_ccw(inp, out):
    return assemble(inp, cw(inp), r180(inp), ccw(inp))


def clockwise_sequence(inp, out):
    return assemble(inp, cw(inp), ccw(inp), r180(inp))


def mirror_tiling(inp, out):
    return assemble(inp, fliplr(inp), flipud(inp), r180(inp))


def plain_tiling(inp, out):
    return assemble(inp, inp, inp, inp)


def bl_flip_lr(inp, out):
    return assemble(inp, ccw(inp), fliplr(inp), cw(inp))


def br_unrotated(inp, out):
    n = n_of(inp)
    g = [list(r) for r in out]
    for i in range(n):
        g[n + i][n:] = inp[i]
    return g


def tr_transpose(inp, out):
    return assemble(inp, transpose(inp), r180(inp), cw(inp))


def swap_right_quadrants(inp, out):
    n = n_of(inp)
    g = [list(r) for r in out]
    for i in range(n):
        g[i][n:], g[n + i][n:] = out[n + i][n:], out[i][n:]
    return g


def top_half_only(inp, out):
    n = n_of(inp)
    return [list(r) for r in out[:n]]


def no_bottom_left_rotation(inp, out):
    n = n_of(inp)
    g = [list(r) for r in out]
    for i in range(n):
        g[n + i][:n] = inp[i]
    return g


def whole_output_transposed(inp, out):
    return transpose(out)


def bottom_row_flipped(inp, out):
    return assemble(inp, ccw(inp), flipud(r180(inp)), cw(inp))


ALTERNATIVES = [
    ("top-right and bottom-right rotations swapped (cw top, ccw bottom)", swap_cw_ccw),
    ("quadrants are inp, cw, ccw, 180 in reading order", clockwise_sequence),
    ("mirror reflection tiling instead of rotations", mirror_tiling),
    ("plain 2x2 repetition of the input", plain_tiling),
    ("bottom-left is a horizontal flip, not a 180 rotation", bl_flip_lr),
    ("bottom-right quadrant left as the unrotated input", br_unrotated),
    ("top-right is a transpose, not a ccw rotation", tr_transpose),
    ("right-hand quadrants swapped top for bottom", swap_right_quadrants),
    ("only the top half is output (4 rows)", top_half_only),
    ("bottom-left quadrant left as the unrotated input", no_bottom_left_rotation),
    ("true output transposed (wrong orientation overall)", whole_output_transposed),
    ("bottom-left is a vertical flip, not a 180 rotation", bottom_row_flipped),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/7953d61e.json'))
    pairs = task['train']
    print('pairs', len(pairs))
    for desc, f in ALTERNATIVES:
        c = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and valid(g) and g != p['output']:
                c += 1
        print(c, desc)
