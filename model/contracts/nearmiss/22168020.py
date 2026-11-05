import json
from pathlib import Path


def _bg(g):
    from collections import Counter
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _row_spans(inp):
    """(row, color, c0, c1) for each row and color with cells at both ends of a span."""
    bg = _bg(inp)
    res = []
    for r, row in enumerate(inp):
        for col in set(row) - {bg}:
            cs = [c for c, v in enumerate(row) if v == col]
            if len(cs) >= 2:
                res.append((r, col, cs[0], cs[-1]))
    return res


def _col_spans(inp):
    t = [list(x) for x in zip(*inp)]
    return [(c, col, r0, r1) for c, col, r0, r1 in _row_spans(t)]


def _copy(g):
    return [list(r) for r in g]


def _components(inp):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != bg and (r, c) not in seen:
                col = inp[r][c]
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] == col:
                                seen.add((ny, nx))
                                stack.append((ny, nx))
                comps.append((col, cells))
    return comps


def vertical_fill(inp, out):
    g = _copy(inp)
    for c, col, r0, r1 in _col_spans(inp):
        for r in range(r0, r1 + 1):
            g[r][c] = col
    return g


def top_row_only(inp, out):
    g = _copy(inp)
    first = {}
    for r, col, c0, c1 in _row_spans(inp):
        if col not in first:
            first[col] = (r, c0, c1)
    for col, (r, c0, c1) in first.items():
        for c in range(c0, c1 + 1):
            g[r][c] = col
    return g


def trim_one_each_side(inp, out):
    g = _copy(inp)
    for r, col, c0, c1 in _row_spans(inp):
        for c in range(c0 + 2, c1 - 1):
            g[r][c] = col
        g[r][c0] = g[r][c1] = col
    return g


def extend_to_edges(inp, out):
    g = _copy(inp)
    w = len(inp[0])
    for r, col, c0, c1 in _row_spans(inp):
        for c in range(w):
            g[r][c] = col
    return g


def left_half_only(inp, out):
    g = _copy(inp)
    for r, col, c0, c1 in _row_spans(inp):
        for c in range(c0, (c0 + c1) // 2 + 1):
            g[r][c] = col
    return g


def bbox_fill(inp, out):
    g = _copy(inp)
    for col, cells in _components(inp):
        rs = [y for y, _ in cells]
        cs = [x for _, x in cells]
        for r in range(min(rs), max(rs) + 1):
            for c in range(min(cs), max(cs) + 1):
                g[r][c] = col
    return g


def wrong_fill_color(inp, out):
    g = _copy(out)
    for r in range(len(out)):
        for c in range(len(out[0])):
            if inp[r][c] != out[r][c]:
                g[r][c] = out[r][c] % 9 + 1
    return g


def clear_arms(inp, out):
    g = _copy(out)
    for r, col, c0, c1 in _row_spans(inp):
        if c1 - c0 >= 3:
            g[r][c0] = g[r][c1] = _bg(inp)
    return g


def diagonal_ray_fill(inp, out):
    # diagonal arms are extended along their diagonal to the grid edge instead of filled across
    g = _copy(inp)
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    for r, col, c0, c1 in _row_spans(inp):
        if c1 - c0 < 2:
            continue
        for c, dc in ((c0, -1), (c1, 1)):
            y, x = r - 1, c + dc
            while 0 <= y < h and 0 <= x < w:
                if g[y][x] == bg:
                    g[y][x] = col
                y -= 1
                x += dc
    return g


def first_color_only(inp, out):
    cols = []
    for r, col, c0, c1 in _row_spans(inp):
        if col not in cols:
            cols.append(col)
    if len(cols) < 2:
        return None
    g = _copy(out)
    for r in range(len(out)):
        for c in range(len(out[0])):
            if out[r][c] != inp[r][c] and out[r][c] != cols[0]:
                g[r][c] = inp[r][c]
    return g


def upper_half_rows_only(inp, out):
    # fills only rows in the top half of the grid
    g = _copy(out)
    h = len(out)
    for r in range(h // 2, h):
        g[r] = list(inp[r])
    return g


ALTERNATIVES = [
    ("fill between same-colored cells along columns instead of rows", vertical_fill),
    ("fill only the first spanning row of each color", top_row_only),
    ("fill leaves one extra cell empty next to each end of the span", trim_one_each_side),
    ("fill runs from the span out to both grid edges", extend_to_edges),
    ("fill covers only the left half of each span", left_half_only),
    ("fill the bounding box of each object", bbox_fill),
    ("fill uses a wrong color", wrong_fill_color),
    ("fill is right but the end cells of wide spans are erased", clear_arms),
    ("arms extended diagonally upward instead of filled across", diagonal_ray_fill),
    ("only the first color found is filled", first_color_only),
    ("only rows in the top half of the grid are filled", upper_half_rows_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/22168020.json'))
    pairs = task['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, '/', len(pairs), desc)
