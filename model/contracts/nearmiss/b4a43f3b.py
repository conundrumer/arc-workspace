"""Near-miss rules for ARC task b4a43f3b.

Input: two 6-row halves split by a full row of 5. One half is a picture
scaled up by 2 (blocks of one color); the other is a mask of 2s. The output
tiles the (downscaled) picture at every marked mask cell.
"""
import json
from collections import Counter
from pathlib import Path


def _parts(inp):
    """Return (picture_half, mask_half) of a vertically split input."""
    r = next(i for i, row in enumerate(inp) if all(v == 5 for v in row))
    a, b = inp[:r], inp[r + 1:]

    def inks(h):
        return {v for row in h for v in row if v != 0}

    return (a, b) if len(inks(a)) > 1 else (b, a)


def _down(g, k):
    return [row[::k] for row in g[::k]]


def _picture_mask(inp):
    pic_half, mask_half = _parts(inp)
    return _down(pic_half, 2), mask_half


def _stamp(pic, mask, marked=lambda v: v != 0, fill=None):
    ph, pw = len(pic), len(pic[0])
    out = []
    for mrow in mask:
        for pr in range(ph):
            row = []
            for v in mrow:
                if marked(v):
                    row.extend(pic[pr] if fill is None else [fill] * pw)
                else:
                    row.extend([0] * pw)
            out.append(row)
    return out


def scale_one(inp, out):
    pic_half, mask = _parts(inp)
    return _stamp(pic_half, mask)


def roles_swapped(inp, out):
    pic_half, mask_half = _parts(inp)
    return _stamp(mask_half, _down(pic_half, 2))


def inverted_mask(inp, out):
    pic, mask = _picture_mask(inp)
    return _stamp(pic, mask, marked=lambda v: v == 0)


def mask_flipped(inp, out):
    pic, mask = _picture_mask(inp)
    return _stamp(pic, mask[::-1])


def picture_transposed(inp, out):
    pic, mask = _picture_mask(inp)
    return _stamp([list(r) for r in zip(*pic)], mask)


def picture_rot180(inp, out):
    pic, mask = _picture_mask(inp)
    return _stamp([r[::-1] for r in pic[::-1]], mask)


def solid_tiles(inp, out):
    pic, mask = _picture_mask(inp)
    return _stamp(pic, mask, fill=2)


def mask_downscaled(inp, out):
    pic, mask = _picture_mask(inp)
    return _stamp(pic, _down(mask, 2))


def shifted_down_right(inp, out):
    h, w = len(out), len(out[0])
    return [[0] * w] + [[0] + row[:-1] for row in out[:-1]]


def cropped_to_marks(inp, out):
    pic, mask = _picture_mask(inp)
    rows = [i for i, r in enumerate(mask) if any(r)]
    cols = [j for j in range(len(mask[0])) if any(r[j] for r in mask)]
    sub = [r[cols[0]:cols[-1] + 1] for r in mask[rows[0]:rows[-1] + 1]]
    return _stamp(pic, sub)


def single_ink(inp, out):
    pic, mask = _picture_mask(inp)
    ink = Counter(v for r in pic for v in r if v != 0).most_common(1)[0][0]
    return _stamp([[ink if v else 0 for v in r] for r in pic], mask)


def scale_three(inp, out):
    pic_half, mask = _parts(inp)
    return _stamp(_down(pic_half, 3), mask)


ALTERNATIVES = [
    ("picture read at one cell per cell, ignoring the scale of 2 (36x36 output)", scale_one),
    ("picture and mask halves swapped: the blocky half is the mask", roles_swapped),
    ("picture stamped on the unmarked mask cells instead of the marked ones", inverted_mask),
    ("mask read upside down", mask_flipped),
    ("picture stamped transposed", picture_transposed),
    ("picture stamped rotated by 180 degrees", picture_rot180),
    ("marked tiles filled with solid 2 instead of the picture", solid_tiles),
    ("mask also downscaled by 2 (9x9 output)", mask_downscaled),
    ("correct output shifted one cell down and right", shifted_down_right),
    ("mask cropped to the bounding box of its marks before tiling", cropped_to_marks),
    ("picture reduced to one ink color (the most common)", single_ink),
    ("picture sampled at blocks of 3 instead of 2 (12x12 output)", scale_three),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b4a43f3b.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
