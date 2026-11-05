import json
from pathlib import Path


def _color(inp):
    return max((v for r in inp for v in r), key=lambda v: sum(r.count(v) for r in inp) if v else -1)


def _corner(inp, k, top, left):
    h, w = len(inp), len(inp[0])
    r0 = 0 if top else h - k
    c0 = 0 if left else w - k
    return [row[c0:c0 + k] for row in inp[r0:r0 + k]]


def _combine(grids, mode, col):
    k = len(grids[0])
    kw = len(grids[0][0])
    res = []
    for r in range(k):
        row = []
        for c in range(kw):
            n = sum(1 for g in grids if g[r][c] != 0)
            if mode == "or":
                on = n >= 1
            elif mode == "and":
                on = n == len(grids)
            else:
                on = n % 2 == 1
            row.append(col if on else 0)
        res.append(row)
    return res


def _corners(inp, k, which=(0, 1, 2, 3), flip=()):
    spec = [(True, True), (True, False), (False, True), (False, False)]
    gs = []
    for i in which:
        g = _corner(inp, k, *spec[i])
        if i in flip:
            g = [row[::-1] for row in g] if flip[i] == "h" else g[::-1]
        gs.append(g)
    return gs


def _flip(g, kind):
    return [row[::-1] for row in g] if kind == "h" else g[::-1]


def and_corners(inp, out):
    return _combine(_corners(inp, 3), "and", _color(inp))


def xor_corners(inp, out):
    return _combine(_corners(inp, 3), "xor", _color(inp))


def top_left_only(inp, out):
    return _combine(_corners(inp, 3, (0,)), "or", _color(inp))


def right_corners_mirrored(inp, out):
    gs = _corners(inp, 3)
    gs[1] = _flip(gs[1], "h")
    gs[3] = _flip(gs[3], "h")
    return _combine(gs, "or", _color(inp))


def bottom_corners_flipped(inp, out):
    gs = _corners(inp, 3)
    gs[2] = _flip(gs[2], "v")
    gs[3] = _flip(gs[3], "v")
    return _combine(gs, "or", _color(inp))


def corner_size_two(inp, out):
    return _combine(_corners(inp, 2), "or", _color(inp))


def corner_size_four(inp, out):
    return _combine(_corners(inp, 4), "or", _color(inp))


def omit_bottom_right(inp, out):
    g = _combine(_corners(inp, 3, (0, 1, 2)), "or", _color(inp))
    return g if g != out else None


def omit_top_right(inp, out):
    g = _combine(_corners(inp, 3, (0, 2, 3)), "or", _color(inp))
    return g if g != out else None


def wrong_color(inp, out):
    return [[5 if v else 0 for v in row] for row in out]


def inverted(inp, out):
    c = _color(inp)
    return [[0 if v else c for v in row] for row in out]


def transposed(inp, out):
    g = [list(r) for r in zip(*out)]
    return g if g != out else None


ALTERNATIVES = [
    ("intersection (AND) of the four corner patches instead of union", and_corners),
    ("XOR (odd count) of the four corner patches instead of union", xor_corners),
    ("only the top-left corner patch is used", top_left_only),
    ("right-hand corner patches are mirrored left-right before overlaying", right_corners_mirrored),
    ("bottom corner patches are flipped top-bottom before overlaying", bottom_corners_flipped),
    ("corner patches taken as 2x2 instead of 3x3, giving a 2x2 output", corner_size_two),
    ("corner patches taken as 4x4 instead of 3x3, giving a 4x4 output", corner_size_four),
    ("bottom-right corner patch is left out of the union", omit_bottom_right),
    ("top-right corner patch is left out of the union", omit_top_right),
    ("union painted with color 5 instead of the input color", wrong_color),
    ("background and color swapped in the union", inverted),
    ("union transposed", transposed),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/bc1d5164.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
