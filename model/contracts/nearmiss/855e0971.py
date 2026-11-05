"""Near-miss readings for 855e0971.

Rule: the grid is a stack of uniform bands (rows or columns). Each cell of the
rarest color (the marker) paints a line of the marker color through its own
band, across the stacking axis, from band edge to band edge.
"""
import json
from pathlib import Path


def _prep(inp):
    """Return (g, transposed, marker color, bands, markers) with bands as row ranges."""
    flat = [v for row in inp for v in row]
    m = min(set(flat), key=lambda v: (flat.count(v), v))

    def single(g):
        return all(len(set(v for v in row if v != m)) == 1 for row in g)

    t = not single(inp)
    g = [list(r) for r in zip(*inp)] if t else [list(r) for r in inp]
    bands = []
    for i, row in enumerate(g):
        col = next(v for v in row if v != m)
        if bands and bands[-1][2] == col and bands[-1][1] == i - 1:
            bands[-1][1] = i
        else:
            bands.append([i, i, col])
    markers = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v == m]
    return g, t, m, bands, markers


def _band_of(bands, r):
    return next(b for b in bands if b[0] <= r <= b[1])


def _render(inp, cells_fn, select=None, erase_marker=False):
    g, t, m, bands, markers = _prep(inp)
    H, W = len(g), len(g[0])
    res = [row[:] for row in g]
    sel = markers if select is None else select(markers, bands)
    painted = set()
    for (r, c) in sel:
        lo, hi, col = _band_of(bands, r)
        for (rr, cc) in cells_fn(r, c, lo, hi, H, W):
            if 0 <= rr < H and 0 <= cc < W:
                painted.add((rr, cc))
    for (rr, cc) in painted:
        res[rr][cc] = m
    if erase_marker:
        for (r, c) in markers:
            res[r][c] = _band_of(bands, r)[2]
    return [list(r) for r in zip(*res)] if t else res


def _col_in_band(r, c, lo, hi, H, W):
    return [(i, c) for i in range(lo, hi + 1)]


def alt_wrong_axis(inp, out):
    return _render(inp, lambda r, c, lo, hi, H, W: [(r, j) for j in range(W)])


def alt_unblocked(inp, out):
    return _render(inp, lambda r, c, lo, hi, H, W: [(i, c) for i in range(H)])


def alt_first_marker_per_band(inp, out):
    def select(markers, bands):
        seen, keep = set(), []
        for (r, c) in sorted(markers):
            b = _band_of(bands, r)[0]
            if b not in seen:
                seen.add(b)
                keep.append((r, c))
        return keep
    return _render(inp, _col_in_band, select)


def alt_one_direction(inp, out):
    return _render(inp, lambda r, c, lo, hi, H, W: [(i, c) for i in range(r, hi + 1)])


def alt_short_of_edges(inp, out):
    return _render(inp, lambda r, c, lo, hi, H, W: [(r, c)] + [(i, c) for i in range(lo + 1, hi)])


def alt_marker_erased(inp, out):
    return _render(inp, _col_in_band, erase_marker=True)


def alt_whole_band(inp, out):
    return _render(inp, lambda r, c, lo, hi, H, W: [(i, j) for i in range(lo, hi + 1) for j in range(W)])


def alt_overshoot_one(inp, out):
    return _render(inp, lambda r, c, lo, hi, H, W: [(i, c) for i in range(lo - 1, hi + 2)])


def alt_cross(inp, out):
    return _render(
        inp,
        lambda r, c, lo, hi, H, W: [(i, c) for i in range(lo, hi + 1)] + [(r, j) for j in range(W)],
    )


def alt_largest_band_only(inp, out):
    def select(markers, bands):
        big = max(bands, key=lambda b: (b[1] - b[0], -b[0]))
        return [(r, c) for (r, c) in markers if big[0] <= r <= big[1]]
    return _render(inp, _col_in_band, select)


def alt_thick_ray(inp, out):
    return _render(
        inp,
        lambda r, c, lo, hi, H, W: [(i, j) for i in range(lo, hi + 1) for j in (c - 1, c, c + 1)],
    )


ALTERNATIVES = [
    ("line drawn along the band (across the full width) instead of across it", alt_wrong_axis),
    ("line runs the full grid length, not stopped at the band edges", alt_unblocked),
    ("only the first marker of each band casts a line", alt_first_marker_per_band),
    ("line goes from the marker toward one end of the band only", alt_one_direction),
    ("line stops one cell short of each band edge", alt_short_of_edges),
    ("line is drawn but the marker cell itself is restored to the band color", alt_marker_erased),
    ("the whole band holding a marker is filled with the marker color", alt_whole_band),
    ("line overshoots the band by one cell into the neighbor band at each end", alt_overshoot_one),
    ("marker casts a cross: its band line plus a full-width line along the band", alt_cross),
    ("only markers in the largest band cast lines", alt_largest_band_only),
    ("line is three cells thick instead of one", alt_thick_ray),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/855e0971.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
