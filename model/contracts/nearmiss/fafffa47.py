import json
from pathlib import Path


def tiles(inp):
    return inp[:3], inp[3:6]


def combine(inp, f, color=2, top=None, bot=None):
    a, b = tiles(inp)
    a = top(a) if top else a
    b = bot(b) if bot else b
    return [[color if f(a[r][c] != 0, b[r][c] != 0) else 0 for c in range(3)] for r in range(3)]


def nand(inp, out):
    return combine(inp, lambda x, y: not (x and y))


def xor(inp, out):
    return combine(inp, lambda x, y: x != y)


def both_filled(inp, out):
    return combine(inp, lambda x, y: x and y)


def or_filled(inp, out):
    return combine(inp, lambda x, y: x or y)


def top_empty_only(inp, out):
    return combine(inp, lambda x, y: not x)


def bottom_empty_only(inp, out):
    return combine(inp, lambda x, y: not y)


def wrong_color(inp, out):
    return [[8 if v else 0 for v in row] for row in out]


def keep_nine_on_filled(inp, out):
    return [[9 if v else 2 for v in row] for row in out]


def bottom_flipped_vertically(inp, out):
    return combine(inp, lambda x, y: not x and not y, bot=lambda t: t[::-1])


def bottom_mirrored_horizontally(inp, out):
    return combine(inp, lambda x, y: not x and not y, bot=lambda t: [r[::-1] for r in t])


def offset_split(inp, out):
    a = inp[0:3]
    b = inp[1:4]
    return [[2 if a[r][c] == 0 and b[r][c] == 0 else 0 for c in range(3)] for r in range(3)]


def transposed_output(inp, out):
    return [list(r) for r in zip(*out)]


def whole_grid_stacked(inp, out):
    # tiles not combined: output keeps tile height 6 with 2 on empty cells
    return [[2 if v == 0 else 0 for v in row] for row in inp]


ALTERNATIVES = [
    ("2 where not both tiles are filled (NAND)", nand),
    ("2 where exactly one tile is filled (XOR)", xor),
    ("2 where both tiles are filled", both_filled),
    ("2 where either tile is filled (OR)", or_filled),
    ("2 where only the top tile is empty", top_empty_only),
    ("2 where only the bottom tile is empty", bottom_empty_only),
    ("right pattern drawn in color 8", wrong_color),
    ("output inverted: 9 where the output is 2, 2 elsewhere", keep_nine_on_filled),
    ("bottom tile flipped vertically before combining", bottom_flipped_vertically),
    ("bottom tile mirrored horizontally before combining", bottom_mirrored_horizontally),
    ("second tile taken one row too early", offset_split),
    ("output transposed", transposed_output),
    ("no combining: 2 on each empty cell of the 6x3 input", whole_grid_stacked),
]
ALTERNATIVES = ALTERNATIVES[:12]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/fafffa47.json'))
    pairs = task['train']
    print('pairs', len(pairs))
    for p in pairs:
        assert combine(p['input'], lambda x, y: not x and not y) == p['output']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g) and g != p['output']:
                n += 1
        print(n, desc)
