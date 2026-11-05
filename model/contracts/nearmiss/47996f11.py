"""Near-miss readings for ARC task 47996f11.

Rule: the grid is symmetric under the full square group about a center at
(15.5, 15.5); color 6 marks occluded cells, restored from their symmetric
counterparts.
"""
import json
from collections import Counter
from pathlib import Path

NOISE = 6


def _copy(g):
    return [row[:] for row in g]


def _noise_cells(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == NOISE]


def _components(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r0, c0 in _noise_cells(inp):
        if (r0, c0) in seen:
            continue
        stack = [(r0, c0)]
        seen.add((r0, c0))
        comp = []
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] == NOISE and (rr, cc) not in seen:
                    seen.add((rr, cc))
                    stack.append((rr, cc))
        comps.append(comp)
    return comps


def fill_mode(inp, out):
    cnt = Counter(v for row in inp for v in row if v != NOISE)
    col = cnt.most_common(1)[0][0]
    g = _copy(inp)
    for r, c in _noise_cells(inp):
        g[r][c] = col
    return g


def fill_zero(inp, out):
    g = _copy(inp)
    for r, c in _noise_cells(inp):
        g[r][c] = 0
    return g


def leave_largest(inp, out):
    comps = _components(inp)
    big = max(comps, key=len)
    g = _copy(out)
    for r, c in big:
        g[r][c] = NOISE
    return g


def leave_smallest(inp, out):
    comps = _components(inp)
    if len(comps) < 2:
        return None
    small = min(comps, key=len)
    g = _copy(out)
    for r, c in small:
        g[r][c] = NOISE
    return g


def _reflect(inp, f):
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c in _noise_cells(inp):
        rr, cc = f(r, c)
        if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] != NOISE:
            g[r][c] = inp[rr][cc]
    return g


def horizontal_axis_shifted(inp, out):
    return _reflect(inp, lambda r, c: (r, 30 - c))


def vertical_axis_shifted(inp, out):
    return _reflect(inp, lambda r, c: (32 - r, c))


def rotation_about_grid_center(inp, out):
    return _reflect(inp, lambda r, c: (29 - r, 29 - c))


def antidiagonal_off_by_two(inp, out):
    return _reflect(inp, lambda r, c: (29 - c, 29 - r))


def nearest_left_color(inp, out):
    g = _copy(inp)
    w = len(inp[0])
    for r, c in _noise_cells(inp):
        v = None
        for cc in range(c - 1, -1, -1):
            if inp[r][cc] != NOISE:
                v = inp[r][cc]
                break
        if v is None:
            for cc in range(c + 1, w):
                if inp[r][cc] != NOISE:
                    v = inp[r][cc]
                    break
        g[r][c] = v
    return g


def true_fill_shifted_one_column(inp, out):
    w = len(out[0])
    g = _copy(out)
    for r, c in _noise_cells(inp):
        g[r][c] = out[r][c + 1] if c + 1 < w else out[r][c - 1]
    return g


def crop_to_noise_box(inp, out):
    cells = _noise_cells(inp)
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("fill every occluded cell with the grid's most common color", fill_mode),
    ("fill every occluded cell with 0", fill_zero),
    ("restore all occluded patches except the largest, which stays occluded", leave_largest),
    ("restore all occluded patches except the smallest, which stays occluded", leave_smallest),
    ("mirror left-right about a column axis off by one cell", horizontal_axis_shifted),
    ("mirror top-bottom about a row axis off by one cell", vertical_axis_shifted),
    ("rotate 180 degrees about the grid's geometric center instead of the symmetry center", rotation_about_grid_center),
    ("reflect across an anti-diagonal through the grid's geometric center", antidiagonal_off_by_two),
    ("fill each occluded cell with the nearest unoccluded color to its left in the row", nearest_left_color),
    ("restore with the correct symmetry but read each source one column to the right", true_fill_shifted_one_column),
    ("output only the true restoration cropped to the bounding box of all occluded cells", crop_to_noise_box),
    ("leave the input unchanged", unchanged),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/47996f11.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
