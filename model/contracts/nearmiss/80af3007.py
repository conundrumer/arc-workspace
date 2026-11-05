import json
from pathlib import Path


def _parse(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v]
    r0 = min(r for r, c in cells)
    r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells)
    c1 = max(c for r, c in cells)
    ink = inp[cells[0][0]][cells[0][1]]
    s = (r1 - r0 + 1) // 3
    pat = [[1 if inp[r0 + i * s][c0 + j * s] else 0 for j in range(3)] for i in range(3)]
    return pat, ink, s, (r0, r1, c0, c1)


def _kron(outer, inner, ink):
    n, m = len(outer), len(inner)
    return [
        [ink if outer[i // m][j // m] and inner[i % m][j % m] else 0
         for j in range(len(outer[0]) * len(inner[0]))]
        for i in range(n * m)
    ]


def _ne(g, out):
    return None if g == out else g


def _comp(p):
    return [[1 - v for v in row] for row in p]


def _tr(p):
    return [list(r) for r in zip(*p)]


def _hflip(p):
    return [row[::-1] for row in p]


def _rot(p):
    return [list(r) for r in zip(*p[::-1])]


def inner_inverted(inp, out):
    p, ink, s, _ = _parse(inp)
    return _ne(_kron(p, _comp(p), ink), out)


def outer_inverted(inp, out):
    p, ink, s, _ = _parse(inp)
    return _ne(_kron(_comp(p), p, ink), out)


def outer_transposed(inp, out):
    p, ink, s, _ = _parse(inp)
    return _ne(_kron(_tr(p), p, ink), out)


def inner_mirrored(inp, out):
    p, ink, s, _ = _parse(inp)
    return _ne(_kron(p, _hflip(p), ink), out)


def inner_rotated(inp, out):
    p, ink, s, _ = _parse(inp)
    return _ne(_kron(p, _rot(p), ink), out)


def pattern_only(inp, out):
    p, ink, s, _ = _parse(inp)
    return _ne([[ink if v else 0 for v in row] for row in p], out)


def upscaled_pattern(inp, out):
    p, ink, s, _ = _parse(inp)
    return _ne(_kron(p, [[1] * 3 for _ in range(3)], ink), out)


def tiled_everywhere(inp, out):
    p, ink, s, _ = _parse(inp)
    return _ne(_kron([[1] * 3 for _ in range(3)], p, ink), out)


def colors_swapped(inp, out):
    ink = _parse(inp)[1]
    return _ne([[0 if v else ink for v in row] for row in out], out)


def scale_kept(inp, out):
    p, ink, s, _ = _parse(inp)
    big = _kron(p, p, ink)
    return _ne([[v for v in row for _ in range(s)] for row in big for _ in range(s)], out)


def last_tile_row_dropped(inp, out):
    return _ne([row[:] for row in out[:-3]], out)


def inner_only_first_row_tile(inp, out):
    # stamp only where the outer cell is in the first pattern row; other rows left blank
    p, ink, s, _ = _parse(inp)
    q = [p[0], [0, 0, 0], [0, 0, 0]]
    return _ne(_kron(q, p, ink), out)


ALTERNATIVES = [
    ("inner stamp uses the complement of the pattern", inner_inverted),
    ("outer layout uses the complement of the pattern", outer_inverted),
    ("outer layout is the transposed pattern", outer_transposed),
    ("each stamp is the pattern mirrored left-right", inner_mirrored),
    ("each stamp is the pattern rotated 90 degrees", inner_rotated),
    ("output is the pattern alone, not expanded", pattern_only),
    ("each pattern cell becomes a filled 3x3 block, no stamp", upscaled_pattern),
    ("pattern stamped in every outer cell, ignoring the outer pattern", tiled_everywhere),
    ("ink and background swapped in the output", colors_swapped),
    ("output kept at input pixel scale (each cell enlarged by the pixel size)", scale_kept),
    ("last row of stamps missing (off-by-one in size)", last_tile_row_dropped),
    ("only the first pattern row is used for the outer layout", inner_only_first_row_tile),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/80af3007.json").read_text())
    train = task["train"]
    for desc, f in ALTERNATIVES:
        n = 0
        for pr in train:
            g = f(pr["input"], pr["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != pr["output"])
            n += ok
        print(n, "/", len(train), desc)
