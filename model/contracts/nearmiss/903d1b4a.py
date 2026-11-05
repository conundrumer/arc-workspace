"""Near-miss rules for ARC task 903d1b4a.

The grid is a D4-symmetric (4-fold mirror and transpose) tile pattern. One or
more rectangular patches of a single noise color overwrite it. The output is
the grid with the patches repaired from their symmetric counterparts.
"""
import json
from collections import Counter
from pathlib import Path


def _noise(inp, out):
    return [(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] != out[r][c]]


def _copy(g):
    return [row[:] for row in g]


def _bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def _repair_with(inp, out, maps):
    """Repair noise cells using only the given coordinate maps; leave a cell
    as noise when none of its images is clean."""
    cells = _noise(inp, out)
    nset = set(cells)
    h, w = len(inp), len(inp[0])
    res = _copy(inp)
    for r, c in cells:
        for f in maps:
            r2, c2 = f(r, c, h, w)
            if 0 <= r2 < h and 0 <= c2 < w and (r2, c2) not in nset:
                res[r][c] = inp[r2][c2]
                break
    return res


def alt_unchanged(inp, out):
    return _copy(inp)


def alt_zero_fill(inp, out):
    res = _copy(out)
    for r, c in _noise(inp, out):
        res[r][c] = 0
    return res


def alt_majority_fill(inp, out):
    cnt = Counter(v for row in out for v in row)
    major = cnt.most_common(1)[0][0]
    res = _copy(out)
    for r, c in _noise(inp, out):
        res[r][c] = major
    return res


def alt_horizontal_only(inp, out):
    return _repair_with(inp, out, [lambda r, c, h, w: (r, w - 1 - c)])


def alt_vertical_only(inp, out):
    return _repair_with(inp, out, [lambda r, c, h, w: (h - 1 - r, c)])


def alt_transpose_only(inp, out):
    return _repair_with(inp, out, [lambda r, c, h, w: (c, r)])


def alt_rot180_only(inp, out):
    return _repair_with(inp, out, [lambda r, c, h, w: (h - 1 - r, w - 1 - c)])


def alt_mirror_off_by_one(inp, out):
    # Mirror axis taken as w - c instead of w - 1 - c (clamped at the edge).
    cells = _noise(inp, out)
    h, w = len(inp), len(inp[0])
    res = _copy(inp)
    for r, c in cells:
        res[r][c] = inp[r][min(w - 1, w - c)]
    return res


def alt_nearest_left_fill(inp, out):
    # Fill each noise cell with the nearest clean cell to the left in its row.
    cells = _noise(inp, out)
    nset = set(cells)
    res = _copy(inp)
    for r, c in sorted(cells):
        c2 = c
        while c2 >= 0 and (r, c2) in nset:
            c2 -= 1
        if c2 < 0:
            c2 = c
            while (r, c2) in nset and c2 < len(inp[0]) - 1:
                c2 += 1
        res[r][c] = inp[r][c2]
    return res


def alt_flat_patch(inp, out):
    # Repair the patch with one color: the most common color of the true repair.
    cells = _noise(inp, out)
    cnt = Counter(out[r][c] for r, c in cells)
    col = cnt.most_common(1)[0][0]
    res = _copy(out)
    for r, c in cells:
        res[r][c] = col
    return res


def alt_patch_flipped_in_place(inp, out):
    # The right content, but the repaired bounding box is flipped left-right.
    r0, r1, c0, c1 = _bbox(_noise(inp, out))
    res = _copy(out)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            res[r][c] = out[r][c0 + c1 - c]
    return res


def alt_half_repaired(inp, out):
    # Only the top half of the noise rows is repaired.
    cells = _noise(inp, out)
    r0, r1, _, _ = _bbox(cells)
    cut = (r0 + r1) // 2
    res = _copy(out)
    for r, c in cells:
        if r > cut:
            res[r][c] = inp[r][c]
    return res


def alt_crop_patch(inp, out):
    # Output only the repaired bounding box instead of the whole grid.
    r0, r1, c0, c1 = _bbox(_noise(inp, out))
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("return the input with the noise patch untouched", alt_unchanged),
    ("fill the noise patch with color 0", alt_zero_fill),
    ("fill the noise patch with the grid's most common color", alt_majority_fill),
    ("repair noise only from the up-down mirror", alt_vertical_only),
    ("mirror axis off by one column (w - c instead of w - 1 - c)", alt_mirror_off_by_one),
    ("fill each noise cell with the nearest clean cell to its left", alt_nearest_left_fill),
    ("fill the whole patch with its single most common repaired color", alt_flat_patch),
    ("repair the patch correctly but flip its bounding box left-right", alt_patch_flipped_in_place),
    ("repair only the top half of the noise rows", alt_half_repaired),
    ("output only the cropped repaired patch", alt_crop_patch),
]


def _valid(g):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    return all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/903d1b4a.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
