import json
from collections import Counter
from pathlib import Path

T = 3  # tile size
S = 4  # tile step (tile plus divider)


def _marker(inp):
    cnt = Counter(v for r in inp for v in r if v not in (0, 5))
    col = 4 if cnt.get(4) == 1 else min(cnt, key=lambda c: (cnt[c], c))
    for y, r in enumerate(inp):
        for x, v in enumerate(r):
            if v == col:
                return col, y, x


def _info(inp):
    col, y, x = _marker(inp)
    src = (y // S, x // S)
    inner = (y % S, x % S)
    return col, src, inner


def _tile(g, tr, tc):
    return [row[tc * S:tc * S + T] for row in g[tr * S:tr * S + T]]


def _put(g, tr, tc, t):
    for i in range(T):
        for j in range(T):
            g[tr * S + i][tc * S + j] = t[i][j]


def _blank_from_input(inp):
    # output skeleton: divider lines kept, all tiles blank
    g = [[0] * len(inp[0]) for _ in inp]
    for y in range(len(inp)):
        for x in range(len(inp[0])):
            if inp[y][x] == 5:
                g[y][x] = 5
    return g


def _compose(inp, dest, tile=None, src=None):
    col, s, inner = _info(inp)
    src = s if src is None else src
    t = _tile(inp, *src) if tile is None else tile
    g = _blank_from_input(inp)
    _put(g, dest[0], dest[1], t)
    return g


def _check(g, out):
    return g


def a_stay(inp, out):
    col, s, inner = _info(inp)
    return _compose(inp, s)


def a_transpose(inp, out):
    col, s, inner = _info(inp)
    return _compose(inp, (inner[1], inner[0]))


def a_mirror(inp, out):
    col, s, inner = _info(inp)
    return _compose(inp, (2 - inner[0], 2 - inner[1]))


def a_inverse(inp, out):
    col, s, inner = _info(inp)
    return _compose(inp, s, src=inner)


def a_keep_others(inp, out):
    col, s, inner = _info(inp)
    g = [r[:] for r in inp]
    _put(g, inner[0], inner[1], _tile(inp, *s))
    return g


def a_source_not_cleared(inp, out):
    col, s, inner = _info(inp)
    g = _compose(inp, inner)
    _put(g, s[0], s[1], _tile(inp, *s))
    return g


def a_flip(inp, out):
    col, s, inner = _info(inp)
    t = [r[::-1] for r in _tile(inp, *s)]
    return _compose(inp, inner, tile=t)


def a_marker_removed(inp, out):
    col, s, inner = _info(inp)
    t = [[0 if v == col else v for v in r] for r in _tile(inp, *s)]
    return _compose(inp, inner, tile=t)


def a_dividers_cleared(inp, out):
    return [[0 if v == 5 else v for v in r] for r in out]


def a_crop(inp, out):
    col, s, inner = _info(inp)
    return _tile(inp, *s)


def a_row_only(inp, out):
    col, s, inner = _info(inp)
    return _compose(inp, (s[0], inner[1]))


def a_col_only(inp, out):
    col, s, inner = _info(inp)
    return _compose(inp, (inner[0], s[1]))


def a_rotate(inp, out):
    col, s, inner = _info(inp)
    t = [list(r) for r in zip(*_tile(inp, *s)[::-1])]
    return _compose(inp, inner, tile=t)


ALTERNATIVES = [
    ("marker tile stays in place, other tiles blanked", a_stay),
    ("destination tile is the transposed inner position", a_transpose),
    ("destination tile is the point-mirrored inner position", a_mirror),
    ("direction reversed: tile at the inner position moves to the marker's tile", a_inverse),
    ("destination tile replaced but other tiles keep their input", a_keep_others),
    ("source tile is not cleared after the copy", a_source_not_cleared),
    ("moved tile is mirrored left to right", a_flip),
    ("marker cell is erased from the moved tile", a_marker_removed),
    ("divider lines are cleared along with the tiles", a_dividers_cleared),
    ("output is only the marker's 3x3 tile cropped", a_crop),
    ("destination keeps the source tile row, uses the inner column", a_row_only),
    ("destination keeps the source tile column, uses the inner row", a_col_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/6d0160f0.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
