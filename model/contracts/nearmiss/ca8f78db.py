"""Near-miss rules for ca8f78db.

The input is a grid of rows: constant background rows alternate with pattern
rows that repeat a short period. Cells of color 0 are noise. The output
restores every noise cell: pattern rows continue their period, background
rows return to the background color.
"""
import json
from collections import Counter
from pathlib import Path

NOISE = 0


def _copy(g):
    return [list(r) for r in g]


def _noise_cells(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == NOISE]


def _is_pattern_row(out, r):
    return len(set(out[r])) > 1


def _period(row):
    n = len(row)
    for p in range(1, n):
        if all(row[i] == row[i + p] for i in range(n - p)):
            return p
    return n


def _bg(out):
    return Counter(v for row in out for v in row).most_common(1)[0][0]


def fill_background(inp, out):
    # Noise is always repainted with the background color.
    bg = _bg(out)
    return [[bg if v == NOISE else v for v in row] for row in inp]


def copy_left(inp, out):
    # Noise takes the nearest clean cell to its left in the same row.
    g = _copy(inp)
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == NOISE:
                cc = c
                while cc >= 0 and inp[r][cc] == NOISE:
                    cc -= 1
                if cc < 0:
                    cc = c
                    while cc < len(row) and inp[r][cc] == NOISE:
                        cc += 1
                row[c] = inp[r][cc] if 0 <= cc < len(row) else _bg(out)
    return g


def background_noise_left(inp, out):
    # Only pattern rows are repaired; noise on background rows stays.
    g = _copy(out)
    for r, c in _noise_cells(inp):
        if not _is_pattern_row(out, r):
            g[r][c] = NOISE
    return g


def pattern_noise_left(inp, out):
    # Only background rows are repaired; noise on pattern rows stays.
    g = _copy(out)
    for r, c in _noise_cells(inp):
        if _is_pattern_row(out, r):
            g[r][c] = NOISE
    return g


def phase_shift(inp, out):
    # Pattern continuation is off by one cell: noise takes its right neighbor's color.
    g = _copy(out)
    for r, c in _noise_cells(inp):
        if _is_pattern_row(out, r):
            g[r][c] = out[r][(c + 1) % len(out[r])]
    return g


def mirrored_pattern(inp, out):
    # The pattern is read mirrored left to right.
    g = _copy(out)
    for r, c in _noise_cells(inp):
        if _is_pattern_row(out, r):
            g[r][c] = out[r][len(out[r]) - 1 - c]
    return g


def period_plus_one(inp, out):
    # The period is taken as one longer than it is.
    g = _copy(out)
    for r, c in _noise_cells(inp):
        if not _is_pattern_row(out, r):
            continue
        p = _period(out[r]) + 1
        n = len(out[r])
        val = None
        for k in range(1, n):
            for cc in (c - k * p, c + k * p):
                if 0 <= cc < n and inp[r][cc] != NOISE:
                    val = inp[r][cc]
                    break
            if val is not None:
                break
        g[r][c] = out[r][c] if val is None else val
    return g


def background_gets_pattern(inp, out):
    # Noise on background rows is filled from the pattern row below (or above).
    g = _copy(out)
    h = len(out)
    for r, c in _noise_cells(inp):
        if _is_pattern_row(out, r):
            continue
        for rr in (r + 1, r - 1):
            if 0 <= rr < h and _is_pattern_row(out, rr):
                g[r][c] = out[rr][c]
                break
    return g


def _components(cells):
    cells = set(cells)
    comps = []
    while cells:
        stack = [cells.pop()]
        comp = list(stack)
        while stack:
            r, c = stack.pop()
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (r + d[0], c + d[1])
                if q in cells:
                    cells.remove(q)
                    stack.append(q)
                    comp.append(q)
        comps.append(comp)
    return comps


def largest_blob_only(inp, out):
    # Only the largest connected noise blob is repaired; the others stay.
    comps = _components(_noise_cells(inp))
    if len(comps) < 2:
        return None
    comps.sort(key=lambda s: (-len(s), min(s)))
    g = _copy(inp)
    for r, c in comps[0]:
        g[r][c] = out[r][c]
    return g


def crop_to_noise(inp, out):
    # Only the repaired region is returned: the bounding box of all noise.
    cells = _noise_cells(inp)
    if not cells:
        return None
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def most_common_pattern_color(inp, out):
    # Noise on pattern rows takes that row's most common non-background color.
    bg = _bg(out)
    g = _copy(out)
    for r, c in _noise_cells(inp):
        if _is_pattern_row(out, r):
            cnt = Counter(v for v in out[r] if v != bg)
            top = max(cnt.values())
            g[r][c] = min(v for v, k in cnt.items() if k == top)
    return g


ALTERNATIVES = [
    ("every noise cell becomes the background color", fill_background),
    ("noise takes the nearest clean cell to its left in the row", copy_left),
    ("noise on background rows is not repaired", background_noise_left),
    ("noise on pattern rows is not repaired", pattern_noise_left),
    ("pattern continuation off by one cell (right neighbor's color)", phase_shift),
    ("pattern read mirrored left to right", mirrored_pattern),
    ("period taken one longer than the true period", period_plus_one),
    ("noise on background rows filled with the adjacent pattern row's colors", background_gets_pattern),
    ("only the largest noise blob is repaired", largest_blob_only),
    ("output is only the bounding box of the repaired region", crop_to_noise),
    ("noise on pattern rows takes the row's most common non-background color", most_common_pattern_color),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not isinstance(g[0], list) or not g[0]:
        return False
    w = len(g[0])
    for row in g:
        if not isinstance(row, list) or len(row) != w:
            return False
        for v in row:
            if type(v) is not int or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/ca8f78db.json"))
    pairs = task["train"]
    print(f"{len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
