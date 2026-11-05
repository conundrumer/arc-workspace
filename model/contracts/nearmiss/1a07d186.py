import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _lines(g, bg):
    """Full uniform non-bg rows and columns: list of (axis, index, color); axis 'r' = row."""
    h, w = len(g), len(g[0])
    res = []
    for i in range(h):
        if g[i][0] != bg and all(v == g[i][0] for v in g[i]):
            res.append(('r', i, g[i][0]))
    for j in range(w):
        col = [g[i][j] for i in range(h)]
        if col[0] != bg and all(v == col[0] for v in col):
            res.append(('c', j, col[0]))
    return res


def _loose(g, bg, lines):
    cells = []
    for i, row in enumerate(g):
        for j, v in enumerate(row):
            if v == bg:
                continue
            if any((ax == 'r' and i == k) or (ax == 'c' and j == k) for ax, k, _ in lines):
                continue
            cells.append((i, j, v))
    return cells


def _pos(line, i, j):
    ax, k, _ = line
    return (i, j, j) if ax == 'c' else (i, j, i)  # row, col, coordinate across the line


def _land(line, i, j, side=None, gap=0):
    """Cell next to the line on the cell's own side (side=-1/+1 forces a side)."""
    ax, k, _ = line
    p = j if ax == 'c' else i
    s = (-1 if p < k else 1) if side is None else side
    q = k + s * (1 + gap)
    return (i, q) if ax == 'c' else (q, j)


def _dist(line, i, j):
    ax, k, _ = line
    return abs((j if ax == 'c' else i) - k)


def _render(inp, place, keep_lines=True, keep_loose=lambda c, m: False):
    """Rebuild the output. place(cell, lines, matches) -> list of (r, c, color) or None."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    lines = _lines(inp, bg)
    g = [[bg] * w for _ in range(h)]
    if keep_lines:
        for ax, k, c in lines:
            for t in range(w if ax == 'r' else h):
                if ax == 'r':
                    g[k][t] = c
                else:
                    g[t][k] = c
    for (i, j, c) in _loose(inp, bg, lines):
        matches = [l for l in lines if l[2] == c]
        if keep_loose((i, j, c), matches):
            g[i][j] = c
        for (r, cc, col) in place((i, j, c), lines, matches) or []:
            if 0 <= r < h and 0 <= cc < w:
                g[r][cc] = col
    return g


def _same_color(cell, lines, matches):
    i, j, c = cell
    if not matches:
        return []
    l = min(matches, key=lambda l: _dist(l, i, j))
    r, cc = _land(l, i, j)
    return [(r, cc, c)]


# 1. Loose cells that moved are also left at their old position.
def keep_old(inp, out):
    return _render(inp, _same_color, keep_loose=lambda c, m: bool(m))


# 2. Cell jumps across the line and lands on the far side.
def far_side(inp, out):
    def p(cell, lines, matches):
        i, j, c = cell
        if not matches:
            return []
        l = min(matches, key=lambda l: _dist(l, i, j))
        ax, k, _ = l
        pp = j if ax == 'c' else i
        r, cc = _land(l, i, j, side=(1 if pp < k else -1))
        return [(r, cc, c)]
    return _render(inp, p)


# 3. Cell stops one cell short of the line (gap of one).
def gap_one(inp, out):
    def p(cell, lines, matches):
        i, j, c = cell
        if not matches:
            return []
        l = min(matches, key=lambda l: _dist(l, i, j))
        r, cc = _land(l, i, j, gap=1)
        return [(r, cc, c)]
    return _render(inp, p)


# 4. Loose cells whose color has no line are kept in place instead of erased.
def unmatched_kept(inp, out):
    return _render(inp, _same_color, keep_loose=lambda c, m: not m)


# 5. Cell goes to the nearest line of any color, keeping its own color.
def nearest_any_line(inp, out):
    def p(cell, lines, matches):
        i, j, c = cell
        if not lines:
            return []
        l = min(lines, key=lambda l: _dist(l, i, j))
        r, cc = _land(l, i, j)
        return [(r, cc, c)]
    return _render(inp, p)


# 6. Cell is erased and nothing arrives at the line.
def no_arrival(inp, out):
    return _render(inp, lambda cell, lines, matches: [])


# 7. Only cells on the low side (left of a column, above a row) arrive; the rest are erased.
def low_side_only(inp, out):
    def p(cell, lines, matches):
        i, j, c = cell
        res = []
        for l in matches:
            ax, k, _ = l
            pp = j if ax == 'c' else i
            if pp < k:
                res.append(_land(l, i, j) + (c,))
        return res[:1]
    return _render(inp, p)


# 8. Cell slides along the line direction to the grid edge instead of toward the line.
def slide_to_edge(inp, out):
    h, w = len(inp), len(inp[0])

    def p(cell, lines, matches):
        i, j, c = cell
        if not matches:
            return []
        ax = matches[0][0]
        return [(0 if i * 2 < h else h - 1, j, c)] if ax == 'c' else [(i, 0 if j * 2 < w else w - 1, c)]
    return _render(inp, p)


# 9. Line is erased in the output (only the moved cells remain).
def line_removed(inp, out):
    return _render(inp, _same_color, keep_lines=False)


# 10. Cell lands mirrored along the line direction (position along the line reflected).
def mirrored_along_line(inp, out):
    h, w = len(inp), len(inp[0])

    def p(cell, lines, matches):
        i, j, c = cell
        if not matches:
            return []
        l = min(matches, key=lambda l: _dist(l, i, j))
        r, cc = _land(l, i, j)
        if l[0] == 'c':
            r = h - 1 - i
        else:
            cc = w - 1 - j
        return [(r, cc, c)]
    return _render(inp, p)


# 11. Cell lands on both sides of the line.
def both_sides(inp, out):
    def p(cell, lines, matches):
        i, j, c = cell
        if not matches:
            return []
        l = min(matches, key=lambda l: _dist(l, i, j))
        return [_land(l, i, j, side=-1) + (c,), _land(l, i, j, side=1) + (c,)]
    return _render(inp, p)


# 12. Cell takes the line's color only when it is the farthest cell; otherwise the true result
#     (a cell crossing mix-up: the nearest-to-line cell of each color is dropped).
def nearest_cell_dropped(inp, out):
    bg = _bg(inp)
    lines = _lines(inp, bg)
    best = {}
    for (i, j, c) in _loose(inp, bg, lines):
        ms = [l for l in lines if l[2] == c]
        if ms:
            d = min(_dist(l, i, j) for l in ms)
            if c not in best or d < best[c][0]:
                best[c] = (d, i, j)

    def p(cell, lines_, matches):
        i, j, c = cell
        if not matches or (c in best and best[c][1:] == (i, j)):
            return []
        return _same_color(cell, lines_, matches)
    return _render(inp, p)


ALTERNATIVES = [
    ("moved cells are also left at their old position", keep_old),
    ("cell jumps across the line and lands on the far side", far_side),
    ("cell stops one cell short of the line", gap_one),
    ("cells whose color has no line stay in place instead of vanishing", unmatched_kept),
    ("cell goes to the nearest line of any color, not the same-color line", nearest_any_line),
    ("loose cells vanish and nothing arrives at the line", no_arrival),
    ("only cells left of / above the line arrive; others vanish", low_side_only),
    ("cell slides along the line direction to the grid edge", slide_to_edge),
    ("line is erased, only the moved cells remain", line_removed),
    ("cell lands mirrored along the line direction", mirrored_along_line),
    ("cell lands on both sides of its line", both_sides),
    ("the cell nearest to the line of each color is dropped", nearest_cell_dropped),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/1a07d186.json'))
    pairs = task['train']
    for inp, out in [(p['input'], p['output']) for p in pairs]:
        assert _render(inp, _same_color) == out, "base reconstruction differs"
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
