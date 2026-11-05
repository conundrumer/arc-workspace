"""Near-miss readings for 79cce52d.

The true output is the interior of the input (the 7 corner cell, its row and
its column removed), cyclically rolled along both axes by amounts set by the
marker cell. Helpers recover those amounts from the true output.
"""
import json
from pathlib import Path


def _interior(inp):
    return [row[1:] for row in inp[1:]]


def _roll(g, dr, dc):
    h, w = len(g), len(g[0])
    return [[g[(r - dr) % h][(c - dc) % w] for c in range(w)] for r in range(h)]


def _true_shift(inp, out):
    g = _interior(inp)
    h, w = len(g), len(g[0])
    for dr in range(h):
        for dc in range(w):
            if _roll(g, dr, dc) == out:
                return dr, dc
    return 0, 0


def _same(g, out):
    return g == out


def no_roll(inp, out):
    return _interior(inp)


def rows_only(inp, out):
    dr, dc = _true_shift(inp, out)
    return _roll(_interior(inp), dr, 0)


def cols_only(inp, out):
    dr, dc = _true_shift(inp, out)
    return _roll(_interior(inp), 0, dc)


def reverse_direction(inp, out):
    dr, dc = _true_shift(inp, out)
    return _roll(_interior(inp), -dr, -dc)


def cols_one_too_far(inp, out):
    dr, dc = _true_shift(inp, out)
    return _roll(_interior(inp), dr, dc + 1)


def one_too_far(inp, out):
    dr, dc = _true_shift(inp, out)
    return _roll(_interior(inp), dr + 1, dc + 1)


def one_too_short(inp, out):
    dr, dc = _true_shift(inp, out)
    return _roll(_interior(inp), dr - 1, dc - 1)


def keep_border(inp, out):
    dr, dc = _true_shift(inp, out)
    return _roll(inp, dr, dc)


def crop_far_corner(inp, out):
    dr, dc = _true_shift(inp, out)
    g = [row[:-1] for row in inp[:-1]]
    return _roll(g, dr, dc)


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirrored(inp, out):
    return [row[::-1] for row in out]


def over_crop(inp, out):
    return [row[1:] for row in out[1:]]


ALTERNATIVES = [
    ("crop the interior but do not roll it at all", no_roll),
    ("roll only the rows, leave columns unrolled", rows_only),
    ("roll only the columns, leave rows unrolled", cols_only),
    ("roll both axes in the opposite direction", reverse_direction),
    ("roll the rows correctly but the columns one step too far", cols_one_too_far),
    ("roll each axis one step too far", one_too_far),
    ("roll each axis one step too short", one_too_short),
    ("roll the whole input and keep the corner row and column", keep_border),
    ("crop away the far edges instead of the corner row and column", crop_far_corner),
    ("true output transposed", transposed),
    ("true output mirrored left to right", mirrored),
    ("crop one extra row and column off the true output", over_crop),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/79cce52d.json"))
    train = task["train"]
    print(f"pairs: {len(train)}")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
