import json
from pathlib import Path


def _src(out):
    n = len(out) // 2
    return [r[:n] for r in out[:n]]


def _hf(g):
    return [r[::-1] for r in g]


def _vf(g):
    return g[::-1]


def _tr(g):
    return [list(r) for r in zip(*g)]


def _rot_cw(g):
    return [list(r) for r in zip(*g[::-1])]


def _quad(tl, tr, bl, br):
    return [a + b for a, b in zip(tl, tr)] + [a + b for a, b in zip(bl, br)]


def horizontal_only(inp, out):
    return [r + r[::-1] for r in inp]


def vertical_only(inp, out):
    return [list(r) for r in inp] + [list(r) for r in inp[::-1]]


def plain_tiling(inp, out):
    return _quad(inp, inp, inp, inp)


def center_tile_flipped_vert(inp, out):
    v = _vf(inp)
    return _quad(v, _hf(v), inp, _hf(inp))


def center_tile_flipped_horiz(inp, out):
    h = _hf(inp)
    return _quad(h, inp, _vf(h), _vf(inp))


def shared_boundary(inp, out):
    n = len(inp)
    cols = [r + r[-2::-1] for r in inp]
    return cols + cols[-2::-1]


def transpose_quadrant(inp, out):
    return _quad(inp, _tr(inp), _vf(inp), _vf(_tr(inp)))


def top_right_unmirrored(inp, out):
    g = [list(r) for r in out]
    n = len(inp)
    for i in range(n):
        g[i][n:] = inp[i]
    return g


def bottom_right_unfilled(inp, out):
    g = [list(r) for r in out]
    n = len(inp)
    for i in range(n, 2 * n):
        g[i][n:] = [0] * n
    return g


def rotation_pinwheel(inp, out):
    r1 = _rot_cw(inp)
    r2 = _rot_cw(r1)
    r3 = _rot_cw(r2)
    return _quad(inp, r1, r3, r2)


def bottom_not_flipped(inp, out):
    top = [r + r[::-1] for r in inp]
    return top + [list(r) for r in top]


def bottom_right_copy(inp, out):
    return _quad(inp, _hf(inp), _vf(inp), inp)


ALTERNATIVES = [
    ("mirror only left-right, output stays input height", horizontal_only),
    ("mirror only top-bottom, output stays input width", vertical_only),
    ("tile the input 2x2 without any mirroring", plain_tiling),
    ("the input is placed upside down at the outer corner, mirrored toward the center", center_tile_flipped_vert),
    ("the input is placed left-right reversed at the outer corner, mirrored toward the center", center_tile_flipped_horiz),
    ("mirror across a shared boundary row/col, giving a 5x5 grid", shared_boundary),
    ("quadrants use the transpose instead of the mirror images", transpose_quadrant),
    ("top-right quadrant is a plain copy of the input, not mirrored", top_right_unmirrored),
    ("bottom-right quadrant left unfilled (0)", bottom_right_unfilled),
    ("quadrants are successive 90-degree rotations of the input", rotation_pinwheel),
    ("bottom half repeats the top half instead of flipping it", bottom_not_flipped),
    ("bottom-right quadrant is a plain copy of the input, not the 180-degree turn", bottom_right_copy),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/67e8384a.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
