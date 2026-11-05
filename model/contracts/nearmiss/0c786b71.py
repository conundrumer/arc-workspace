"""Near-miss readings for ARC task 0c786b71 (HxW input -> 2Hx2W mirrored tiling, input in bottom-right)."""
import json
from pathlib import Path


def _fh(g):
    return [r[::-1] for r in g]


def _fv(g):
    return g[::-1]


def _r180(g):
    return _fv(_fh(g))


def _tr(g):
    return [list(c) for c in zip(*g)]


def _grid(tl, tr, bl, br):
    return [a + b for a, b in zip(tl, tr)] + [a + b for a, b in zip(bl, br)]


def plain_tiling(inp, out):
    return _grid(inp, inp, inp, inp)


def anchor_top_left(inp, out):
    return _grid(inp, _fh(inp), _fv(inp), _r180(inp))


def anchor_top_right(inp, out):
    return _grid(_fh(inp), inp, _r180(inp), _fv(inp))


def anchor_bottom_left(inp, out):
    return _grid(_fv(inp), _r180(inp), inp, _fh(inp))


def swapped_flips(inp, out):
    return _grid(_r180(inp), _fh(inp), _fv(inp), inp)


def horizontal_only(inp, out):
    return [a + b for a, b in zip(_fh(inp), inp)]


def vertical_only(inp, out):
    return _fv(inp) + inp


def transposed_tiles(inp, out):
    t = _tr(inp)
    return _grid(_r180(t), _fv(t), _fh(t), t)


def top_left_unflipped(inp, out):
    h, w = len(inp), len(inp[0])
    res = [r[:] for r in out]
    for i in range(h):
        for j in range(w):
            res[i][j] = inp[i][j]
    return res


def rotations_not_mirrors(inp, out):
    return _grid(_r180(inp), _r180(inp), _r180(inp), inp)


def shifted_one_column(inp, out):
    return [r[1:] + r[:1] for r in out]


def input_unchanged(inp, out):
    return [r[:] for r in inp]


ALTERNATIVES = [
    ("plain 2x2 tiling of the input with no mirroring", plain_tiling),
    ("input anchored in the top-left tile, mirrors grow away from it", anchor_top_left),
    ("input anchored in the top-right tile", anchor_top_right),
    ("input anchored in the bottom-left tile", anchor_bottom_left),
    ("top-right tile flipped left-right and bottom-left flipped top-bottom (axes swapped)", swapped_flips),
    ("mirror only across the vertical axis, output 1x2 tiles", horizontal_only),
    ("mirror only across the horizontal axis, output 2x1 tiles", vertical_only),
    ("tiles built from the transposed input (diagonal reflection)", transposed_tiles),
    ("top-left tile left as the unflipped input, rest correct", top_left_unflipped),
    ("every non-anchor tile is the 180-degree rotation", rotations_not_mirrors),
    ("correct output cyclically shifted one column (off-by-one offset)", shifted_one_column),
    ("input returned unchanged", input_unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/0c786b71.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
