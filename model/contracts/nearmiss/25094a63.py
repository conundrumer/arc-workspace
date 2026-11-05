"""Near-miss readings for ARC task 25094a63.

Rule: the grid is noise with a few solid single-color rectangles whose sides
are all at least 5 cells; each such rectangle is repainted with color 4.
"""
import json
from pathlib import Path

PAINT = 4


def _copy(g):
    return [list(r) for r in g]


def _blocks(inp, out):
    """Repainted rectangles as (r0, r1, c0, c1, color), from the diff."""
    h, w = len(inp), len(inp[0])
    ch = {(r, c) for r in range(h) for c in range(w) if inp[r][c] != out[r][c]}
    seen = set()
    res = []
    for s in sorted(ch):
        if s in seen:
            continue
        col = inp[s[0]][s[1]]
        st = [s]
        seen.add(s)
        cs = []
        while st:
            r, c = st.pop()
            cs.append((r, c))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (r + dr, c + dc)
                if n in ch and n not in seen and inp[n[0]][n[1]] == col:
                    seen.add(n)
                    st.append(n)
        rs = [a for a, _ in cs]
        cc = [b for _, b in cs]
        res.append((min(rs), max(rs), min(cc), max(cc), col))
    return res


def _revert(inp, out, keep):
    """Start from inp; paint only the blocks for which keep(block) is true."""
    g = _copy(inp)
    for b in _blocks(inp, out):
        if keep(b):
            r0, r1, c0, c1, _ = b
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    g[r][c] = PAINT
    return g


def _area(b):
    return (b[1] - b[0] + 1) * (b[3] - b[2] + 1)


def wrong_color(inp, out):
    g = _copy(out)
    for r0, r1, c0, c1, _ in _blocks(inp, out):
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                g[r][c] = 5
    return g


def largest_only(inp, out):
    bs = _blocks(inp, out)
    best = max(bs, key=_area)
    return _revert(inp, out, lambda b: b == best)


def min_side_two(inp, out):
    """Every solid 2x2 patch counts as a footprint."""
    g = _copy(out)
    h, w = len(inp), len(inp[0])
    for r in range(h - 1):
        for c in range(w - 1):
            v = inp[r][c]
            if v == inp[r][c + 1] == inp[r + 1][c] == inp[r + 1][c + 1]:
                for a in (r, r + 1):
                    for b in (c, c + 1):
                        g[a][b] = PAINT
    return g


def min_side_six(inp, out):
    return _revert(inp, out, lambda b: b[1] - b[0] + 1 >= 6 and b[3] - b[2] + 1 >= 6)


def border_only(inp, out):
    g = _copy(out)
    for r0, r1, c0, c1, _ in _blocks(inp, out):
        for r in range(r0 + 1, r1):
            for c in range(c0 + 1, c1):
                g[r][c] = inp[r][c]
    return g


def interior_only(inp, out):
    g = _copy(out)
    for r0, r1, c0, c1, _ in _blocks(inp, out):
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if r in (r0, r1) or c in (c0, c1):
                    g[r][c] = inp[r][c]
    return g


def grown_by_one(inp, out):
    g = _copy(out)
    h, w = len(inp), len(inp[0])
    for r0, r1, c0, c1, _ in _blocks(inp, out):
        for r in range(r0, min(r1 + 1, h - 1) + 1):
            for c in range(c0, min(c1 + 1, w - 1) + 1):
                g[r][c] = PAINT
    return g


def color_eight_only(inp, out):
    return _revert(inp, out, lambda b: b[4] == 8)


def global_recolor(inp, out):
    cols = {b[4] for b in _blocks(inp, out)}
    return [[PAINT if v in cols else v for v in row] for row in inp]


def transposed_regions(inp, out):
    g = _copy(inp)
    for r0, r1, c0, c1, _ in _blocks(inp, out):
        for r in range(c0, c1 + 1):
            for c in range(r0, r1 + 1):
                g[r][c] = PAINT
    return g


def crop_largest(inp, out):
    best = max(_blocks(inp, out), key=_area)
    r0, r1, c0, c1, _ = best
    return [[PAINT] * (c1 - c0 + 1) for _ in range(r0, r1 + 1)]


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("repaint the footprints with color 5 instead of 4", wrong_color),
    ("repaint only the largest footprint", largest_only),
    ("footprint threshold too low: any solid 2x2 patch is repainted too", min_side_two),
    ("footprint threshold too high: only rectangles with both sides at least 6", min_side_six),
    ("repaint only the outline of each footprint", border_only),
    ("repaint only the interior of each footprint, one cell in from the edge", interior_only),
    ("repaint each footprint one cell too large on the bottom and right", grown_by_one),
    ("repaint only footprints of color 8", color_eight_only),
    ("repaint every cell of a footprint color, anywhere in the grid", global_recolor),
    ("footprint rows and columns swapped (transposed placement)", transposed_regions),
    ("output is the largest footprint cropped and painted", crop_largest),
    ("input returned unchanged", unchanged),
]


def _valid(g):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    w = len(g[0])
    return w > 0 and all(
        len(r) == w and all(isinstance(v, int) and 0 <= v <= 9 for v in r) for r in g
    )


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/25094a63.json"
    task = json.load(open(path))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(_copy(p["input"]), _copy(p["output"]))
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
