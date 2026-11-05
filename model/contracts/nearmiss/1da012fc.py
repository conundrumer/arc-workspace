import json
from pathlib import Path


def _legend_box(inp):
    h, w = len(inp), len(inp[0])
    for c in range(1, 10):
        cells = [(r, k) for r in range(h) for k in range(w) if inp[r][k] == c]
        if not cells:
            continue
        r0 = min(r for r, _ in cells)
        r1 = max(r for r, _ in cells)
        c0 = min(k for _, k in cells)
        c1 = max(k for _, k in cells)
        if (r1 - r0 + 1) * (c1 - c0 + 1) < 6:
            continue
        if all(inp[r][k] != 0 for r in range(r0, r1 + 1) for k in range(c0, c1 + 1)):
            return c, (r0, r1, c0, c1)
    return None, None


def _components(inp, skip):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 or (r, c) in seen or skip(r, c):
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen
                                and inp[ny][nx] != 0 and not skip(ny, nx)):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
            comps.append(cells)
    return comps


def _parse(inp):
    leg, box = _legend_box(inp)
    if leg is None:
        return None
    r0, r1, c0, c1 = box
    inbox = lambda r, c: r0 <= r <= r1 and c0 <= c <= c1
    markers = _components(inp, lambda r, c: not inbox(r, c) or inp[r][c] == leg)
    shapes = _components(inp, lambda r, c: inbox(r, c))
    return leg, box, markers, shapes


def _mcolor(inp, m):
    return inp[m[0][0]][m[0][1]]


def _top(cells):
    return min(r for r, _ in cells)


def _left(cells):
    return min(c for _, c in cells)


def _paint(inp, shapes, colors):
    g = [row[:] for row in inp]
    for cells, col in zip(shapes, colors):
        for r, c in cells:
            g[r][c] = col
    return g


def _assign(inp, shape_key, marker_key, shift=0, rev=False):
    p = _parse(inp)
    if p is None:
        return None
    leg, box, markers, shapes = p
    shapes = sorted(shapes, key=shape_key)
    markers = sorted(markers, key=marker_key)
    if len(markers) != len(shapes):
        return None
    cols = [_mcolor(inp, m) for m in markers]
    if rev:
        cols = cols[::-1]
    cols = cols[shift:] + cols[:shift]
    return _paint(inp, shapes, cols)


def _row_major(cells):
    return (_top(cells), _left(cells))


def _col_major(cells):
    return (_left(cells), _top(cells))


def column_major(inp, out):
    return _assign(inp, _col_major, _col_major)


def reversed_rows(inp, out):
    return _assign(inp, _row_major, _row_major, rev=True)


def bottom_up_shapes(inp, out):
    # shapes read bottom-to-top, markers top-to-bottom
    return _assign(inp, lambda c: (-_top(c), _left(c)), _row_major)


def right_to_left_ties(inp, out):
    return _assign(inp, lambda c: (_top(c), -_left(c)), _row_major)


def off_by_one(inp, out):
    return _assign(inp, _row_major, _row_major, shift=1)


def marker_by_color_value(inp, out):
    return _assign(inp, _row_major, lambda c: _mcolor(inp, c))


def shape_by_size(inp, out):
    return _assign(inp, lambda c: (len(c), _top(c)), _row_major)


def shapes_column_major(inp, out):
    # shapes read column-major, markers read row-major
    return _assign(inp, _col_major, _row_major)


def all_first_marker(inp, out):
    p = _parse(inp)
    if p is None:
        return None
    leg, box, markers, shapes = p
    first = sorted(markers, key=_row_major)[0]
    return _paint(inp, shapes, [_mcolor(inp, first)] * len(shapes))


def legend_color_fill(inp, out):
    p = _parse(inp)
    if p is None:
        return None
    leg, box, markers, shapes = p
    return _paint(inp, shapes, [leg] * len(shapes))


def only_first_recolored(inp, out):
    p = _parse(inp)
    if p is None:
        return None
    leg, box, markers, shapes = p
    g = [row[:] for row in inp]
    s = sorted(shapes, key=_row_major)[0]
    ms = sorted(markers, key=_row_major)[0]
    for r, c in s:
        g[r][c] = _mcolor(inp, ms)
    return g


def last_shape_unrecolored(inp, out):
    p = _parse(inp)
    if p is None:
        return None
    leg, box, markers, shapes = p
    last = sorted(shapes, key=_row_major)[-1]
    g = [row[:] for row in out]
    for r, c in last:
        g[r][c] = inp[r][c]
    return g


def crop_box(inp, out):
    p = _parse(inp)
    if p is None:
        return None
    r0, r1, c0, c1 = p[1]
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def markers_erased(inp, out):
    p = _parse(inp)
    if p is None:
        return None
    leg, box, markers, shapes = p
    g = [row[:] for row in out]
    for m in markers:
        for r, c in m:
            g[r][c] = leg
    return g


ALTERNATIVES = [
    ("shapes and markers both read column-major (left to right, then top to bottom)", column_major),
    ("marker colors assigned in reverse reading order", reversed_rows),
    ("shapes read bottom-to-top while markers read top-to-bottom", bottom_up_shapes),
    ("shapes break row ties right-to-left while markers break them left-to-right", right_to_left_ties),
    ("each shape takes the color of the next marker (off by one place)", off_by_one),
    ("markers ordered by color value instead of position", marker_by_color_value),
    ("shapes ordered by size instead of position", shape_by_size),
    ("shapes read column-major while markers read row-major", shapes_column_major),
    ("every shape takes the color of the first marker", all_first_marker),
    ("shapes take the legend box color", legend_color_fill),
    ("only the first shape is recolored", only_first_recolored),
    ("the last shape is left uncolored in the output", last_shape_unrecolored),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1da012fc.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            ok = (g is not None and len(g) > 0 and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != p["output"])
            n += ok
        print(n, desc)
