import json
from pathlib import Path


def _bbox(inp):
    ms = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v]
    return (min(r for r, _ in ms), max(r for r, _ in ms),
            min(c for _, c in ms), max(c for _, c in ms))


def _lines(inp, k):
    """Rows and columns of the marks' bounding box with at least k marks."""
    r0, r1, c0, c1 = _bbox(inp)
    rows = [r for r in range(r0, r1 + 1)
            if sum(1 for c in range(c0, c1 + 1) if inp[r][c]) >= k]
    cols = [c for c in range(c0, c1 + 1)
            if sum(1 for r in range(r0, r1 + 1) if inp[r][c]) >= k]
    return rows, cols


def _paint(inp, rows, cols, color=2, hspan=None, vspan=None):
    r0, r1, c0, c1 = _bbox(inp)
    hs = hspan or (c0, c1)
    vs = vspan or (r0, r1)
    g = [row[:] for row in inp]
    for r in rows:
        for c in range(hs[0], hs[1] + 1):
            if inp[r][c] == 0:
                g[r][c] = color
    for c in cols:
        for r in range(vs[0], vs[1] + 1):
            if inp[r][c] == 0:
                g[r][c] = color
    return g


def threshold(k):
    def f(inp, out):
        rows, cols = _lines(inp, k)
        return _paint(inp, rows, cols)
    return f


def only_horizontal(inp, out):
    rows, _ = _lines(inp, 4)
    return _paint(inp, rows, [])


def only_vertical(inp, out):
    _, cols = _lines(inp, 4)
    return _paint(inp, [], cols)


def fill_with_mark_color(inp, out):
    rows, cols = _lines(inp, 4)
    return _paint(inp, rows, cols, color=1)


def extend_to_grid_edge(inp, out):
    rows, cols = _lines(inp, 4)
    W, H = len(inp[0]), len(inp)
    return _paint(inp, rows, cols, hspan=(0, W - 1), vspan=(0, H - 1))


def recolor_whole_line(inp, out):
    rows, cols = _lines(inp, 4)
    g = [row[:] for row in inp]
    r0, r1, c0, c1 = _bbox(inp)
    for r in rows:
        for c in range(c0, c1 + 1):
            g[r][c] = 2
    for c in cols:
        for r in range(r0, r1 + 1):
            g[r][c] = 2
    return g


def fill_bbox_interior(inp, out):
    r0, r1, c0, c1 = _bbox(inp)
    g = [row[:] for row in inp]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if g[r][c] == 0:
                g[r][c] = 2
    return g


def first_gap_only(inp, out):
    rows, cols = _lines(inp, 4)
    r0, r1, c0, c1 = _bbox(inp)
    g = [row[:] for row in inp]
    for r in rows:
        for c in range(c0, c1 + 1):
            if inp[r][c] == 0:
                g[r][c] = 2
                break
    for c in cols:
        for r in range(r0, r1 + 1):
            if inp[r][c] == 0:
                g[r][c] = 2
                break
    return g


def single_cell_gaps_only(inp, out):
    rows, cols = _lines(inp, 4)
    r0, r1, c0, c1 = _bbox(inp)
    g = [row[:] for row in inp]
    for r in rows:
        for c in range(c0 + 1, c1):
            if inp[r][c] == 0 and inp[r][c - 1] and inp[r][c + 1]:
                g[r][c] = 2
    for c in cols:
        for r in range(r0 + 1, r1):
            if inp[r][c] == 0 and inp[r - 1][c] and inp[r + 1][c]:
                g[r][c] = 2
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("a row or column is a line from 3 marks on (threshold too low)", threshold(3)),
    ("a row or column is a line from 2 marks on (threshold far too low)", threshold(2)),
    ("a row or column is a line only from 5 marks on (threshold too high)", threshold(5)),
    ("only horizontal lines are repaired", only_horizontal),
    ("only vertical lines are repaired", only_vertical),
    ("gaps are filled with the mark color 1 instead of a new color", fill_with_mark_color),
    ("repaired lines extend over the whole grid, not only the marks' bounding box", extend_to_grid_edge),
    ("the whole line is recolored 2, marks included", recolor_whole_line),
    ("every empty cell inside the bounding box is filled", fill_bbox_interior),
    ("only the first gap of each line is filled", first_gap_only),
    ("only gaps one cell wide between two marks are filled", single_cell_gaps_only),
    ("input returned unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/4612dd53.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
    ref = _paint(pairs[0]['input'], *_lines(pairs[0]['input'], 4))
    print('reference rule matches pair 0:', ref == pairs[0]['output'])
