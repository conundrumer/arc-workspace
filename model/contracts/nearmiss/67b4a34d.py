"""Near-miss readings for ARC task 67b4a34d.

Rule: one rectangular block of the symmetric grid is masked (color 3).
The output is the content hidden under the mask, recovered from the grid's
dihedral symmetries.
"""
import json
from collections import Counter
from pathlib import Path

MASK = 3


def _hole(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == MASK]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return r0, r1, c0, c1


def _full(inp, out):
    """The unmasked grid."""
    r0, r1, c0, c1 = _hole(inp)
    g = [row[:] for row in inp]
    for i in range(r1 - r0 + 1):
        for j in range(c1 - c0 + 1):
            g[r0 + i][c0 + j] = out[i][j]
    return g


def _fill(inp, ops, fallback=0):
    """Fill the hole using the first op whose image cell is unmasked."""
    n = len(inp)
    r0, r1, c0, c1 = _hole(inp)
    res = []
    for r in range(r0, r1 + 1):
        row = []
        for c in range(c0, c1 + 1):
            v = fallback
            for op in ops:
                rr, cc = op(r, c, n)
                if 0 <= rr < n and 0 <= cc < len(inp[0]) and inp[rr][cc] != MASK:
                    v = inp[rr][cc]
                    break
            row.append(v)
        res.append(row)
    return res


HFLIP = lambda r, c, n: (r, n - 1 - c)
VFLIP = lambda r, c, n: (n - 1 - r, c)
TRANS = lambda r, c, n: (c, r)
ROT180 = lambda r, c, n: (n - 1 - r, n - 1 - c)
ANTI = lambda r, c, n: (n - 1 - c, n - 1 - r)
HFLIP_OFF = lambda r, c, n: (r, n - c)          # axis off by one
VFLIP_OFF = lambda r, c, n: (n - r, c)


def shift_up_copy(inp, out):
    """Copy the block directly above the hole (below when none fits)."""
    r0, r1, c0, c1 = _hole(inp)
    h = r1 - r0 + 1
    s = -h if r0 - h >= 0 else h
    return [[inp[r + s][c] for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]


def shift_left_copy(inp, out):
    """Copy the block directly left of the hole (right when none fits)."""
    r0, r1, c0, c1 = _hole(inp)
    w = c1 - c0 + 1
    s = -w if c0 - w >= 0 else w
    return [[inp[r][c + s] for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]


def hflip_short_axis(inp, out):
    """Horizontal mirror about an axis one cell too far left (n-2-c)."""
    return _fill(inp, [lambda r, c, n: (r, n - 2 - c)])


def vflip_short_axis(inp, out):
    """Vertical mirror about an axis one cell too far up (n-2-r)."""
    return _fill(inp, [lambda r, c, n: (n - 2 - r, c)])


def offbyone_axis(inp, out):
    return _fill(inp, [HFLIP_OFF, VFLIP_OFF, TRANS])


def crop_shifted(inp, out):
    g = _full(inp, out)
    r0, r1, c0, c1 = _hole(inp)
    n = len(g)
    r0 = min(r0 + 1, n - (r1 - r0 + 1))
    c0 = min(c0 + 1, n - (c1 - c0 + 1))
    if (r0, c0) == (_hole(inp)[0], _hole(inp)[2]):
        r0 -= 2
        c0 -= 2
    h, w = len(out), len(out[0])
    return [g[r][c0:c0 + w] for r in range(r0, r0 + h)]


def crop_expanded(inp, out):
    g = _full(inp, out)
    r0, r1, c0, c1 = _hole(inp)
    n = len(g)
    return [g[r][max(0, c0 - 1):min(n, c1 + 2)] for r in range(max(0, r0 - 1), min(n, r1 + 2))]


def mask_unfilled(inp, out):
    r0, r1, c0, c1 = _hole(inp)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def out_transposed(inp, out):
    return [list(r) for r in zip(*out)]


def out_hflipped(inp, out):
    return [row[::-1] for row in out]


def out_vflipped(inp, out):
    return out[::-1]


def most_common_fill(inp, out):
    cnt = Counter(v for row in inp for v in row if v != MASK)
    col = cnt.most_common(1)[0][0]
    return [[col] * len(out[0]) for _ in out]


def hole_with_ring(inp, out):
    """Output the whole grid with the hole filled, instead of only the hole."""
    return _full(inp, out)


ALTERNATIVES = [
    ("copy the block directly above the hole (below if none fits) instead of mirroring", shift_up_copy),
    ("copy the block directly left of the hole (right if none fits) instead of mirroring", shift_left_copy),
    ("horizontal mirror about an axis one cell too far left", hflip_short_axis),
    ("vertical mirror about an axis one cell too far up", vflip_short_axis),
    ("mirror axes placed one cell off (n-c, n-r instead of n-1-c, n-1-r)", offbyone_axis),
    ("correct fill but cropped one cell right and down of the hole", crop_shifted),
    ("correct fill but cropped with a one-cell border around the hole", crop_expanded),
    ("output the hole's mask content unfilled", mask_unfilled),
    ("correct fill but transposed (wrong orientation)", out_transposed),
    ("correct fill but flipped left-right", out_hflipped),
    ("correct fill but flipped top-bottom", out_vflipped),
    ("fill the hole with the grid's most common color", most_common_fill),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/67b4a34d.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
