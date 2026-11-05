import json
from pathlib import Path


def _copy(g):
    return [list(r) for r in g]


def _holes(inp, out):
    """Connected components (4-neighbour) of cells the true output changes."""
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != out[r][c] and (r, c) not in seen:
                stack = [(r, c)]
                seen.add((r, c))
                cells = []
                while stack:
                    y, x = stack.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen
                                and inp[ny][nx] != out[ny][nx]):
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                comps.append(sorted(cells))
    return comps


def _ink(inp, cells):
    y, x = cells[0]
    return inp[y - 1][x]


def _box(inp, cells):
    """Bounding box (r0, c0, r1, c1) of the outline around a hole."""
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return min(ys) - 1, min(xs) - 1, max(ys) + 1, max(xs) + 1


def _paint(inp, out, colour_of):
    g = _copy(inp)
    for cells in _holes(inp, out):
        col = colour_of(cells)
        if col is None:
            continue
        for y, x in cells:
            g[y][x] = col
    return g


def no_fill(inp, out):
    return _copy(inp)


def swap_colours(inp, out):
    m = {5: 7, 7: 5}
    return [[m.get(v, v) for v in r] for r in out]


def all_five(inp, out):
    return _paint(inp, out, lambda cells: 5)


def all_seven(inp, out):
    return _paint(inp, out, lambda cells: 7)


def only_single_cell(inp, out):
    return _paint(inp, out, lambda cells: 5 if len(cells) == 1 else None)


def only_multi_cell(inp, out):
    return _paint(inp, out, lambda cells: 7 if len(cells) > 1 else None)


def ink_colour_fill(inp, out):
    return _paint(inp, out, lambda cells: _ink(inp, cells))


def colour_by_ink(inp, out):
    return _paint(inp, out, lambda cells: 7 if _ink(inp, cells) == 3 else 5)


def colour_by_width(inp, out):
    def f(cells):
        width = max(x for _, x in cells) - min(x for _, x in cells) + 1
        return 5 if width == 1 else 7
    return _paint(inp, out, f)


def ring_filled(inp, out):
    g = _copy(out)
    h, w = len(inp), len(inp[0])
    for cells in _holes(inp, out):
        r0, c0, r1, c1 = _box(inp, cells)
        col = out[cells[0][0]][cells[0][1]]
        for y in range(r0 - 1, r1 + 2):
            for x in range(c0 - 1, c1 + 2):
                if 0 <= y < h and 0 <= x < w and inp[y][x] == 0:
                    g[y][x] = col
    return g


def whole_box_filled(inp, out):
    g = _copy(out)
    for cells in _holes(inp, out):
        r0, c0, r1, c1 = _box(inp, cells)
        col = out[cells[0][0]][cells[0][1]]
        for y in range(r0, r1 + 1):
            for x in range(c0, c1 + 1):
                g[y][x] = col
    return g


def crop_first_rectangle(inp, out):
    holes = _holes(inp, out)
    r0, c0, r1, c1 = _box(inp, holes[0])
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("rectangles left unfilled (input returned)", no_fill),
    ("fill colours swapped: size 1 gets 7, size 2 gets 5", swap_colours),
    ("every hole filled with 5 regardless of size", all_five),
    ("every hole filled with 7 regardless of size", all_seven),
    ("only single-cell holes filled; larger holes left empty", only_single_cell),
    ("only multi-cell holes filled; single-cell holes left empty", only_multi_cell),
    ("hole filled with the rectangle's own outline colour", ink_colour_fill),
    ("fill colour chosen by outline colour (3 gets 7, others 5)", colour_by_ink),
    ("fill colour chosen by hole width (width 1 gets 5, else 7)", colour_by_width),
    ("fill spills into the background ring around each rectangle", ring_filled),
    ("whole rectangle box, outline included, painted in fill colour", whole_box_filled),
    ("output cropped to the first rectangle's box", crop_first_rectangle),
]

def _differing(fn):
    def wrapped(inp, out):
        g = fn(inp, out)
        return None if g == out else g
    return wrapped


ALTERNATIVES = [(d, _differing(f)) for d, f in ALTERNATIVES]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/84f2aca1.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, '/', len(pairs), desc)
