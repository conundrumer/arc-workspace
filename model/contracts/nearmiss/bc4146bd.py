"""Near-miss rules for bc4146bd.

True rule: the output is the input tiled five times along the width, with
every odd tile (index 1, 3) mirrored left to right: I F I F I.
"""
import json
from pathlib import Path


def _hflip(g):
    return [r[::-1] for r in g]


def _vflip(g):
    return [r[:] for r in g[::-1]]


def _rot180(g):
    return [r[::-1] for r in g[::-1]]


def _transpose(g):
    return [list(c) for c in zip(*g)]


def _swap_colors(g):
    cols = sorted({c for r in g for c in r})
    if len(cols) != 2:
        return None
    a, b = cols
    return [[b if c == a else a for c in r] for r in g]


def _strip(tiles):
    return [sum((t[y] for t in tiles), []) for y in range(len(tiles[0]))]


def _copy(g):
    return [r[:] for r in g]


def three_tiles(inp, out):
    f = _hflip(inp)
    return _strip([inp, f, inp])


def four_tiles(inp, out):
    f = _hflip(inp)
    return _strip([inp, f, inp, f])


def start_flipped(inp, out):
    f = _hflip(inp)
    return _strip([f, inp, f, inp, f])


def plain_repeat(inp, out):
    return _strip([inp] * 5)


def vflip_odd(inp, out):
    v = _vflip(inp)
    return _strip([inp, v, inp, v, inp])


def rot180_odd(inp, out):
    r = _rot180(inp)
    return _strip([inp, r, inp, r, inp])


def stacked_vertically(inp, out):
    v = _vflip(inp)
    return _copy(inp) + v + _copy(inp) + v + _copy(inp)


def transpose_odd(inp, out):
    t = _transpose(inp)
    return _strip([inp, t, inp, t, inp])


def last_tile_flipped(inp, out):
    f = _hflip(inp)
    return _strip([inp, f, inp, f, f])


def all_but_first_flipped(inp, out):
    f = _hflip(inp)
    return _strip([inp, f, f, f, f])


def color_swapped_odd(inp, out):
    s = _swap_colors(_hflip(inp))
    if s is None:
        return None
    return _strip([inp, s, inp, s, inp])


def both_axes_pattern(inp, out):
    # mirror in a checkerboard of tiles, applied to the true output's rows
    f = _hflip(inp)
    return _strip([inp, f, inp, f, inp])[::-1]


ALTERNATIVES = [
    ("strip has three tiles instead of five", three_tiles),
    ("strip has four tiles instead of five", four_tiles),
    ("strip starts with a mirrored tile instead of the original", start_flipped),
    ("input repeated five times with no mirroring", plain_repeat),
    ("odd tiles flipped top to bottom instead of left to right", vflip_odd),
    ("odd tiles rotated 180 degrees instead of mirrored", rot180_odd),
    ("tiles stacked vertically with top-bottom mirroring instead of side by side", stacked_vertically),
    ("odd tiles transposed instead of mirrored", transpose_odd),
    ("last tile mirrored too, so the strip ends mirrored", last_tile_flipped),
    ("only the first tile is original, every later tile mirrored", all_but_first_flipped),
    ("odd tiles mirrored and their two colors swapped", color_swapped_odd),
    ("true strip with its rows in reverse order", both_axes_pattern),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/bc4146bd.json"))
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
