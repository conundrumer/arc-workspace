"""Near-miss readings for task 1f642eb9.

True rule: each marker cell (not background, not the block color) shoots a
ray in the four directions; where a ray first reaches the solid block, that
block cell takes the marker color.
"""
import json
from collections import Counter
from pathlib import Path

DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _copy(g):
    return [row[:] for row in g]


def _block_color(inp):
    c = Counter(v for row in inp for v in row if v != 0)
    return c.most_common(1)[0][0]


def _markers(inp):
    b = _block_color(inp)
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row)
            if v != 0 and v != b]


def _trace(inp, r, c, d):
    """Return (before, first, last) along the ray, or None if it misses.
    before: last cell before the block; first: first block cell;
    last: last block cell in the line."""
    b = _block_color(inp)
    h, w = len(inp), len(inp[0])
    dr, dc = d
    rr, cc = r + dr, c + dc
    while 0 <= rr < h and 0 <= cc < w:
        if inp[rr][cc] == b:
            first = (rr, cc)
            before = (rr - dr, cc - dc)
            while 0 <= rr + dr < h and 0 <= cc + dc < w and inp[rr + dr][cc + dc] == b:
                rr += dr
                cc += dc
            return before, first, (rr, cc)
        rr += dr
        cc += dc
    return None


def _paint(inp, pick, dirs=DIRS, erase_marker=False):
    g = _copy(inp)
    for r, c, v in _markers(inp):
        for d in dirs:
            t = _trace(inp, r, c, d)
            if t is None:
                continue
            for (pr, pc) in pick(t, (r, c), d):
                g[pr][pc] = v
        if erase_marker:
            g[r][c] = 0
    return g


def _path(t, m, d):
    # all cells strictly between marker and block
    before, first, last = t
    cells = []
    r, c = m[0] + d[0], m[1] + d[1]
    while (r, c) != first:
        cells.append((r, c))
        r += d[0]
        c += d[1]
    return cells


def far_edge(inp, out):
    return _paint(inp, lambda t, m, d: [t[2]])


def cell_before(inp, out):
    return _paint(inp, lambda t, m, d: [t[0]])


def fill_path(inp, out):
    return _paint(inp, lambda t, m, d: _path(t, m, d))


def fill_path_and_hit(inp, out):
    return _paint(inp, lambda t, m, d: _path(t, m, d) + [t[1]])


def through_block(inp, out):
    def pick(t, m, d):
        cells = []
        r, c = t[1]
        while (r, c) != (t[2][0] + d[0], t[2][1] + d[1]):
            cells.append((r, c))
            r += d[0]
            c += d[1]
        return cells
    return _paint(inp, pick)


def vertical_only(inp, out):
    return _paint(inp, lambda t, m, d: [t[1]], dirs=[(-1, 0), (1, 0)])


def horizontal_only(inp, out):
    return _paint(inp, lambda t, m, d: [t[1]], dirs=[(0, -1), (0, 1)])


def marker_moved(inp, out):
    return _paint(inp, lambda t, m, d: [t[1]], erase_marker=True)


def shifted_along_edge(inp, out):
    def pick(t, m, d):
        r, c = t[1]
        # shift one cell perpendicular to the ray, staying inside the grid
        pr, pc = (0, 1) if d[0] != 0 else (1, 0)
        r2, c2 = r + pr, c + pc
        if r2 >= len(inp) or c2 >= len(inp[0]):
            r2, c2 = r - pr, c - pc
        return [(r2, c2)]
    return _paint(inp, pick)


def first_and_last(inp, out):
    return _paint(inp, lambda t, m, d: [t[1], t[2]])


def whole_edge(inp, out):
    # the full edge of the block facing the marker takes the marker color
    def pick(t, m, d):
        first = t[1]
        cells = []
        if d[0] != 0:
            c = first[1]
            r = first[0]
            while c - 1 >= 0 and inp[r][c - 1] == inp[first[0]][first[1]]:
                c -= 1
            while c < len(inp[0]) and inp[r][c] == inp[first[0]][first[1]]:
                cells.append((r, c))
                c += 1
        else:
            r = first[0]
            c = first[1]
            while r - 1 >= 0 and inp[r - 1][c] == inp[first[0]][first[1]]:
                r -= 1
            while r < len(inp) and inp[r][c] == inp[first[0]][first[1]]:
                cells.append((r, c))
                r += 1
        return cells
    return _paint(inp, pick)


def first_marker_only(inp, out):
    g = _copy(inp)
    ms = _markers(inp)
    if not ms:
        return None
    r, c, v = ms[0]
    for d in DIRS:
        t = _trace(inp, r, c, d)
        if t:
            g[t[1][0]][t[1][1]] = v
    # other markers' hits are left as in the true output only when absent
    return g


def input_unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("paint the far edge of the block (where the ray exits) instead of the first block cell", far_edge),
    ("paint the empty cell just before the block instead of the block cell", cell_before),
    ("fill the empty cells between marker and block with the marker color, leave the block cell", fill_path),
    ("fill the path between marker and block and the first block cell", fill_path_and_hit),
    ("ray passes through the block and paints every block cell in line", through_block),
    ("only vertical rays are cast; horizontal markers are ignored", vertical_only),
    ("only horizontal rays are cast; vertical markers are ignored", horizontal_only),
    ("marker color moves onto the block, the marker cell is erased", marker_moved),
    ("hit cell is offset one cell sideways along the block edge", shifted_along_edge),
    ("both the first and the last block cell in line take the marker color", first_and_last),
    ("the whole block edge facing the marker takes the marker color", whole_edge),
    ("only the first marker in reading order casts rays", first_marker_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/1f642eb9.json').read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
