import json
from pathlib import Path


def _blocks(out):
    """Split the output into square tiles along its long axis."""
    h, w = len(out), len(out[0])
    s = min(h, w)
    vertical = h > w
    n = max(h, w) // s
    res = []
    for i in range(n):
        if vertical:
            res.append([row[:] for row in out[i * s:(i + 1) * s]])
        else:
            res.append([row[i * s:(i + 1) * s] for row in out])
    return res, vertical


def _join(blocks, vertical):
    if vertical:
        return [row[:] for b in blocks for row in b]
    return [sum((b[r] for b in blocks), []) for r in range(len(blocks[0]))]


def _color(b):
    return max(v for row in b for v in row)


def _recolor(b, c):
    return [[c if v else 0 for v in row] for row in b]


def _bg_cell(inp):
    return 0


def rotate_colors(inp, out):
    bl, v = _blocks(out)
    cs = [_color(b) for b in bl]
    cs = cs[1:] + cs[:1]
    return _join([_recolor(b, c) for b, c in zip(bl, cs)], v)


def reverse_tile_order_keep_color_on_position(inp, out):
    # shapes stacked in the opposite order, colors stay in place
    bl, v = _blocks(out)
    cs = [_color(b) for b in bl]
    shapes = [_recolor(b, 1) for b in bl][::-1]
    return _join([_recolor(b, c) for b, c in zip(shapes, cs)], v)


def single_color(inp, out):
    bl, v = _blocks(out)
    c = _color(bl[0])
    return _join([_recolor(b, c) for b in bl], v)


def keep_input_color(inp, out):
    return [[6 if x else 0 for x in row] for row in out]


def transposed_stack(inp, out):
    return [list(r) for r in zip(*out)]


def only_first_shape(inp, out):
    bl, v = _blocks(out)
    return bl[0]


def crop_union_box(inp, out):
    cells = [(r, c) for r, row in enumerate(inp) for c, x in enumerate(row) if x == 6]
    r0 = min(r for r, c in cells); r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells); c1 = max(c for r, c in cells)
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def separator_between_tiles(inp, out):
    bl, v = _blocks(out)
    s = len(bl[0])
    res = []
    for i, b in enumerate(bl):
        res.append(b)
        if i < len(bl) - 1:
            res.append([[0] * s for _ in range(s)] if v else [[0] for _ in range(s)])
    return _join(res, v)


def fill_whole_box(inp, out):
    bl, v = _blocks(out)
    return _join([[[_color(b)] * len(b[0]) for _ in b] for b in bl], v)


def inverted_shape(inp, out):
    bl, v = _blocks(out)
    return _join([[[0 if x else _color(b) for x in row] for row in b] for b in bl], v)


def shrunk_tiles(inp, out):
    bl, v = _blocks(out)
    return _join([[row[:-1] for row in b[:-1]] for b in bl], v)


def unchanged_input(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("marker colors rotated by one tile along the stack", rotate_colors),
    ("tiles keep marker colors in place but shapes appear in reverse order", reverse_tile_order_keep_color_on_position),
    ("every shape takes the color of the first marker", single_color),
    ("shapes keep their input color 6 instead of marker color", keep_input_color),
    ("stack laid out along the wrong axis (transposed)", transposed_stack),
    ("only the first shape is output", only_first_shape),
    ("crop of the union bounding box of all shapes from the input", crop_union_box),
    ("an empty separator band inserted between tiles", separator_between_tiles),
    ("whole bounding box filled with the marker color, not just the shape", fill_whole_box),
    ("shape cells left empty, background colored with the marker color", inverted_shape),
    ("each tile cropped one row and column short", shrunk_tiles),
    ("input returned unchanged", unchanged_input),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(x) is int and 0 <= x <= 9 for r in g for x in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/50aad11f.json'))
    train = task['train']
    print(len(ALTERNATIVES), 'readings,', len(train), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
