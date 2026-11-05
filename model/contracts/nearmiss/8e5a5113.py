import json
from pathlib import Path

W = 3  # tile side
STARTS = (0, 4, 8)  # tile column starts


def tile(g, k):
    c = STARTS[k]
    return [row[c:c + W] for row in g]


def put(g, k, t):
    g = [r[:] for r in g]
    c = STARTS[k]
    for i in range(len(g)):
        for j in range(W):
            g[i][c + j] = t[i][j]
    return g


def hflip(t):
    return [r[::-1] for r in t]


def vflip(t):
    return t[::-1]


def transpose(t):
    return [list(r) for r in zip(*t)]


def rot_ccw(t):
    return [list(r) for r in zip(*t)][::-1]


def zeros(t):
    return [[0] * W for _ in t]


def left_tile2_empty(inp, out):
    return put(out, 1, zeros(out))


def left_tile3_empty(inp, out):
    return put(out, 2, zeros(out))


def no_transform(inp, out):
    p = tile(out, 0)
    return put(put(out, 1, p), 2, p)


def not_cumulative(inp, out):
    # every tile gets the one-step transform of the pattern
    return put(out, 2, tile(out, 1))


def reversed_flow(inp, out):
    return put(put(out, 1, tile(out, 2)), 2, tile(out, 1))


def rotate_ccw_steps(inp, out):
    p = tile(out, 0)
    r1 = rot_ccw(p)
    return put(put(out, 1, r1), 2, rot_ccw(r1))


def transpose_steps(inp, out):
    p = tile(out, 0)
    t1 = transpose(p)
    return put(put(out, 1, t1), 2, transpose(t1))


def separators_dropped(inp, out):
    g = [r[:] for r in out]
    for r in g:
        r[3] = 0
        r[7] = 0
    return g


def pattern_tile_flipped(inp, out):
    # pattern tile itself is replaced by its mirror image
    return put(out, 0, hflip(tile(out, 0)))


def only_pattern_tile(inp, out):
    return tile(out, 0)


def last_tile_narrow(inp, out):
    # last tile is one column short
    g = [r[:] for r in out]
    for r in g:
        r[10] = 0
    return g


def third_from_second_transposed(inp, out):
    return put(out, 2, transpose(tile(out, 1)))


ALTERNATIVES = [
    ("second tile left unfilled", left_tile2_empty),
    ("third tile left unfilled", left_tile3_empty),
    ("pattern copied unchanged into both tiles", no_transform),
    ("turn not accumulated: third tile repeats second", not_cumulative),
    ("flow runs the other way: second and third tiles swapped", reversed_flow),
    ("each step is a quarter turn counterclockwise", rotate_ccw_steps),
    ("each step is a transpose", transpose_steps),
    ("separator columns cleared", separators_dropped),
    ("pattern tile replaced by its mirror image", pattern_tile_flipped),
    ("only the pattern tile output", only_pattern_tile),
    ("last tile one column short", last_tile_narrow),
    ("third tile is the second tile transposed", third_from_second_transposed),
]


def valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/8e5a5113.json'))
    pairs = task['train']
    for name, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(f'{n}/{len(pairs)}  {name}')
