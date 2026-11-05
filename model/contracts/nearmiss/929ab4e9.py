import json
from collections import Counter
from pathlib import Path

NOISE = 2


def _noise_cells(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == NOISE]


def _copy(g):
    return [list(row) for row in g]


def _fill_from(inp, f):
    """Replace each noise cell by inp at the cell f(r, c, h, w) gives."""
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c in _noise_cells(inp):
        rr, cc = f(r, c, h, w)
        g[r][c] = inp[rr % h][cc % w]
    return g


def blank_fill(inp, out):
    return [[0 if v == NOISE else v for v in row] for row in inp]


def vertical_only(inp, out):
    return _fill_from(inp, lambda r, c, h, w: (h - 1 - r, c))


def horizontal_only(inp, out):
    return _fill_from(inp, lambda r, c, h, w: (r, w - 1 - c))


def transpose_fill(inp, out):
    if len(inp) != len(inp[0]):
        return None
    return _fill_from(inp, lambda r, c, h, w: (c, r))


def rotate90_fill(inp, out):
    if len(inp) != len(inp[0]):
        return None
    return _fill_from(inp, lambda r, c, h, w: (c, w - 1 - r))


def most_common_fill(inp, out):
    cnt = Counter(v for row in inp for v in row if v != NOISE)
    col = cnt.most_common(1)[0][0]
    return [[col if v == NOISE else v for v in row] for row in inp]


def left_neighbor_fill(inp, out):
    g = _copy(inp)
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == NOISE:
                k = c - 1
                while k >= 0 and row[k] == NOISE:
                    k -= 1
                g[r][c] = row[k] if k >= 0 else row[(c + 1) % len(row)]
    return g


def top_half_only(inp, out):
    h = len(inp)
    g = _copy(out)
    for r, c in _noise_cells(inp):
        if r >= h // 2:
            g[r][c] = NOISE
    return g


def mirror_off_by_one(inp, out):
    return _fill_from(inp, lambda r, c, h, w: (h - 2 - r, c))


def shifted_column_fill(inp, out):
    g = _copy(out)
    w = len(out[0])
    for r, c in _noise_cells(inp):
        g[r][c] = out[r][(c + 1) % w]
    return g


def crop_noise_box(inp, out):
    cells = _noise_cells(inp)
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def largest_component_only(inp, out):
    """Repair only the largest 4-connected noise region."""
    h, w = len(inp), len(inp[0])
    seen = set()
    best = []
    for s in _noise_cells(inp):
        if s in seen:
            continue
        comp, stack = [], [s]
        seen.add(s)
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (r + dr, c + dc)
                if 0 <= n[0] < h and 0 <= n[1] < w and inp[n[0]][n[1]] == NOISE and n not in seen:
                    seen.add(n)
                    stack.append(n)
        if len(comp) > len(best):
            best = comp
    g = _copy(inp)
    for r, c in best:
        g[r][c] = out[r][c]
    return g


ALTERNATIVES = [
    ("noise cells are erased to background 0 instead of repaired", blank_fill),
    ("repair reads only the vertical mirror cell", vertical_only),
    ("repair reads only the horizontal mirror cell", horizontal_only),
    ("repair reads the transpose cell (diagonal symmetry)", transpose_fill),
    ("repair reads the 90-degree rotation cell", rotate90_fill),
    ("noise cells are filled with the most common clean color", most_common_fill),
    ("noise cells copy the nearest clean cell to the left", left_neighbor_fill),
    ("only noise in the top half is repaired", top_half_only),
    ("mirror axis is off by one row", mirror_off_by_one),
    ("repaired cells take the value one column to the right", shifted_column_fill),
    ("output is only the crop of the repaired noise bounding box", crop_noise_box),
    ("only the largest noise region is repaired", largest_component_only),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/929ab4e9.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
