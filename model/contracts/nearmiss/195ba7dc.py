import json
from pathlib import Path

W = 6  # tile width; separator column at index 6


def _tiles(inp):
    return [r[:W] for r in inp], [r[W + 1:] for r in inp]


def _combine(a, b, f, fill=1):
    return [[fill if f(x != 0, y != 0) else 0 for x, y in zip(ra, rb)]
            for ra, rb in zip(a, b)]


def and_instead_of_or(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: x and y)


def xor_instead_of_or(inp, out):
    a, b = _tiles(inp)
    return _combine(a, b, lambda x, y: x != y)


def left_tile_only(inp, out):
    a, b = _tiles(inp)
    return _combine(a, a, lambda x, y: x)


def right_tile_only(inp, out):
    a, b = _tiles(inp)
    return _combine(b, b, lambda x, y: x)


def inverted_output(inp, out):
    return [[1 - v for v in r] for r in out]


def fill_with_seven(inp, out):
    return [[7 if v else 0 for v in r] for r in out]


def fill_with_separator_color(inp, out):
    return [[2 if v else 0 for v in r] for r in out]


def mirrored_right_tile(inp, out):
    a, b = _tiles(inp)
    b = [r[::-1] for r in b]
    return _combine(a, b, lambda x, y: x or y)


def tiles_include_separator(inp, out):
    # off-by-one tile width: tiles are cols 0-6 and 6-12 (overlap on separator)
    a = [r[:W + 1] for r in inp]
    b = [r[W:] for r in inp]
    return _combine(a, b, lambda x, y: x or y)


def right_tile_shifted_left(inp, out):
    # right tile read one column early (includes the separator, drops last column)
    a = [r[:W] for r in inp]
    b = [r[W:2 * W] for r in inp]
    return _combine(a, b, lambda x, y: x or y)


def top_row_left_unfilled(inp, out):
    return [[0] * len(out[0])] + [list(r) for r in out[1:]]


def vertical_flip_of_output(inp, out):
    return [list(r) for r in out[::-1]]


ALTERNATIVES = [
    ("combine tiles with AND (filled only where both tiles are non-zero)", and_instead_of_or),
    ("combine tiles with XOR (filled where exactly one tile is non-zero)", xor_instead_of_or),
    ("use only the left tile", left_tile_only),
    ("use only the right tile", right_tile_only),
    ("swap output colours: filled cells 0, empty cells 1", inverted_output),
    ("fill with the tile colour 7 instead of 1", fill_with_seven),
    ("fill with the separator colour 2 instead of 1", fill_with_separator_color),
    ("mirror the right tile horizontally before overlaying", mirrored_right_tile),
    ("tiles of width 7 that include the separator column", tiles_include_separator),
    ("right tile read one column early, starting at the separator", right_tile_shifted_left),
    ("top output row left unfilled", top_row_left_unfilled),
    ("vertical flip of the correct output", vertical_flip_of_output),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not isinstance(g[0], list):
        return False
    w = len(g[0])
    if any(not isinstance(r, list) or len(r) != w for r in g):
        return False
    if any(not isinstance(v, int) or not 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / 'data/tasks/195ba7dc.json'
    train = json.load(open(path))['train']
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(n, desc)
