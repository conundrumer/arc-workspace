import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    seen = set()
    comps = []  # (color, [cells])
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
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
    count = Counter(col for col, _ in comps)
    line_col = [col for col in count if count[col] == 1][0]
    line = [cells for col, cells in comps if col == line_col][0]
    copies = [cells for col, cells in comps if col != line_col]
    shape_col = [col for col in count if col != line_col][0]
    line = sorted(line)
    ends = [line[0], line[-1]]
    centers = []
    shapes = []
    for cells in copies:
        ys = [y for y, _ in cells]
        xs = [x for _, x in cells]
        cy = (min(ys) + max(ys)) // 2
        cx = (min(xs) + max(xs)) // 2
        centers.append((cy, cx))
        shapes.append([(y - cy, x - cx) for y, x in cells])
    return dict(h=h, w=w, bg=bg, line_col=line_col, shape_col=shape_col, line=line,
                ends=ends, centers=sorted(centers), shape=shapes[0], comps=comps)


def _between(a, b):
    dy, dx = b[0] - a[0], b[1] - a[1]
    if dy == 0 and dx == 0:
        return None
    if not (dy == 0 or dx == 0 or abs(dy) == abs(dx)):
        return None
    n = max(abs(dy), abs(dx))
    sy, sx = dy // n, dx // n
    return [(a[0] + sy * i, a[1] + sx * i) for i in range(n + 1)]


def _render(inp, pairs=None, ends=None, shape_fn=None, stamp_col=None, line_col=None,
            inclusive=True, lines_on_top=False, centers_override=None, stamp_shift=(0, 0)):
    p = _parse(inp)
    h, w, bg = p['h'], p['w'], p['bg']
    g = [[bg] * w for _ in range(h)]
    centers = centers_override if centers_override is not None else p['centers']
    lc = p['line_col'] if line_col is None else line_col
    sc = p['shape_col'] if stamp_col is None else stamp_col
    if pairs is None:
        pairs = [(a, b) for i, a in enumerate(centers) for b in centers[i + 1:]]
    ends = p['ends'] if ends is None else ends
    shape = p['shape'] if shape_fn is None else shape_fn(p['shape'])

    def draw_lines():
        for a, b in pairs:
            cells = _between(a, b)
            if cells is None:
                continue
            if not inclusive:
                cells = cells[1:-1]
            for y, x in cells:
                g[y][x] = lc

    def draw_stamps():
        for ey, ex in ends:
            for dy, dx in shape:
                y, x = ey + dy + stamp_shift[0], ex + dx + stamp_shift[1]
                if 0 <= y < h and 0 <= x < w:
                    g[y][x] = sc

    if lines_on_top:
        draw_stamps(); draw_lines()
    else:
        draw_lines(); draw_stamps()
    return g


def lines_extend_to_edges(inp, out):
    p = _parse(inp)
    g = _render(inp)
    c = p['centers']
    for i, a in enumerate(c):
        for b in c[i + 1:]:
            cells = _between(a, b)
            if cells is None:
                continue
            sy, sx = cells[1][0] - cells[0][0], cells[1][1] - cells[0][1]
            for (y, x), (dy, dx) in ((a, (-sy, -sx)), (b, (sy, sx))):
                y, x = y + dy, x + dx
                while 0 <= y < p['h'] and 0 <= x < p['w']:
                    if g[y][x] == p['bg']:
                        g[y][x] = p['line_col']
                    y, x = y + dy, x + dx
    return g


def only_first_end(inp, out):
    p = _parse(inp)
    return _render(inp, ends=[p['ends'][0]])


def swapped_colors(inp, out):
    p = _parse(inp)
    return _render(inp, stamp_col=p['line_col'], line_col=p['shape_col'])


def stamps_in_line_color(inp, out):
    p = _parse(inp)
    return _render(inp, stamp_col=p['line_col'])


def line_stays(inp, out):
    p = _parse(inp)
    g = [r[:] for r in out]
    for y, x in p['line']:
        if g[y][x] == p['bg']:
            g[y][x] = p['line_col']
    return g


def input_objects_stay(inp, out):
    p = _parse(inp)
    g = [r[:] for r in out]
    for col, cells in p['comps']:
        for y, x in cells:
            if g[y][x] == p['bg']:
                g[y][x] = col
    return g


def stamp_shifted_down_right(inp, out):
    return _render(inp, stamp_shift=(1, 1))


def no_joining_lines(inp, out):
    return _render(inp, pairs=[])


def lines_exclude_centers(inp, out):
    return _render(inp, inclusive=False)


def orthogonal_joins_only(inp, out):
    p = _parse(inp)
    c = p['centers']
    pairs = [(a, b) for i, a in enumerate(c) for b in c[i + 1:] if a[0] == b[0] or a[1] == b[1]]
    return _render(inp, pairs=pairs)


def chain_in_reading_order(inp, out):
    c = _parse(inp)['centers']
    return _render(inp, pairs=list(zip(c, c[1:])))


def stamp_center_cell_only(inp, out):
    return _render(inp, shape_fn=lambda s: [(0, 0)])


def line_ends_join_too(inp, out):
    p = _parse(inp)
    return _render(inp, centers_override=p['centers'] + p['ends'])


ALTERNATIVES = [
    ("joining lines run on to the grid edges past the centers", lines_extend_to_edges),
    ("shape stamped on only one end of the line", only_first_end),
    ("shape color and line color swapped", swapped_colors),
    ("stamps drawn in the line's color", stamps_in_line_color),
    ("input line is left in place", line_stays),
    ("all input objects are left in place", input_objects_stay),
    ("stamps placed one cell down and right of the line ends", stamp_shifted_down_right),
    ("no joining lines, only the stamps", no_joining_lines),
    ("joining lines stop short of the centers", lines_exclude_centers),
    ("only row and column joins, diagonals missed", orthogonal_joins_only),
    ("only consecutive centers in reading order are joined", chain_in_reading_order),
    ("only the center cell is stamped at the line ends", stamp_center_cell_only),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/c6141b15.json'))
    train = task['train']
    for pr in train:
        assert _render(pr['input']) == pr['output'], 'base render mismatch'
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in train:
            g = fn(pr['input'], pr['output'])
            if g is not None and _valid(g) and g != pr['output']:
                n += 1
        print(f'{n}/{len(train)}  {desc}')
