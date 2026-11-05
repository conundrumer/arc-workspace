import json
from pathlib import Path
from collections import Counter


def _panel(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == 1]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def _fliph(g):
    return [row[::-1] for row in g]


def _flipv(g):
    return g[::-1]


def _rot180(g):
    return [row[::-1] for row in g[::-1]]


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _rot_cw(g):
    return [list(r) for r in zip(*g[::-1])]


def _marks_and_shape(out):
    counts = Counter(v for row in out for v in row if v != 1)
    shape_color = counts.most_common(1)[0][0]
    marks = [(r, c) for r, row in enumerate(out) for c, v in enumerate(row)
             if v != 1 and v != shape_color]
    return shape_color, marks


def alt_fliph(inp, out):
    return _fliph(out)


def alt_flipv(inp, out):
    return _flipv(out)


def alt_rot180(inp, out):
    return _rot180(out)


def alt_transpose(inp, out):
    return _transpose(out)


def alt_identity_panel(inp, out):
    return _panel(inp)


def alt_rot_cw_panel(inp, out):
    return _rot_cw(_panel(inp))


def alt_no_marks(inp, out):
    _, marks = _marks_and_shape(out)
    g = [row[:] for row in out]
    for r, c in marks:
        g[r][c] = 1
    return g


def alt_no_shape(inp, out):
    sc, _ = _marks_and_shape(out)
    return [[1 if v == sc else v for v in row] for row in out]


def alt_shape_mirrored_marks_fixed(inp, out):
    sc, marks = _marks_and_shape(out)
    base = [[1 if v != sc else v for v in row] for row in out]
    base = _fliph(base)
    for r, c in marks:
        base[r][c] = out[r][c]
    return base


def alt_shape_flipv_marks_fixed(inp, out):
    sc, marks = _marks_and_shape(out)
    base = [[1 if v != sc else v for v in row] for row in out]
    base = _flipv(base)
    for r, c in marks:
        base[r][c] = out[r][c]
    return base


def alt_pad_zero_ring(inp, out):
    w = len(out[0])
    return [[0] * (w + 2)] + [[0] + row + [0] for row in out] + [[0] * (w + 2)]


def alt_inner_crop(inp, out):
    return [row[1:-1] for row in out[1:-1]]


ALTERNATIVES = [
    ("panel turned correctly but mirrored left-right", alt_fliph),
    ("panel turned correctly but mirrored top-bottom", alt_flipv),
    ("panel turned half a turn further than the true pose", alt_rot180),
    ("panel transposed after the true pose", alt_transpose),
    ("panel copied as it stands, no turn", alt_identity_panel),
    ("panel turned a quarter turn clockwise only", alt_rot_cw_panel),
    ("single-cell marks dropped from the output", alt_no_marks),
    ("shape dropped, only the marks kept", alt_no_shape),
    ("shape mirrored left-right while marks stay at the true cells", alt_shape_mirrored_marks_fixed),
    ("shape mirrored top-bottom while marks stay at the true cells", alt_shape_flipv_marks_fixed),
    ("output has a ring of 0 around the panel", alt_pad_zero_ring),
    ("output cropped one cell in on every side", alt_inner_crop),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/94133066.json'))
    pairs = task["train"]
    print("readings", len(ALTERNATIVES), "pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
