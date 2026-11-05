import json
from collections import Counter
from pathlib import Path


def crop(g, r, c, h, w):
    return [row[c:c + w] for row in g[r:r + h]]


def top_right(inp, out):
    return crop(inp, 0, len(inp[0]) - 2, 2, 2)


def bottom_left(inp, out):
    return crop(inp, len(inp) - 2, 0, 2, 2)


def bottom_right(inp, out):
    return crop(inp, len(inp) - 2, len(inp[0]) - 2, 2, 2)


def crop3(inp, out):
    return crop(inp, 0, 0, 3, 3)


def crop1(inp, out):
    return crop(inp, 0, 0, 1, 1)


def offset_one(inp, out):
    return crop(inp, 1, 1, 2, 2)


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def mirrored(inp, out):
    return [row[::-1] for row in out]


def wide_window(inp, out):
    return crop(inp, 0, 0, 2, 3)


def center(inp, out):
    return crop(inp, len(inp) // 2 - 1, len(inp[0]) // 2 - 1, 2, 2)


def top_rows_full(inp, out):
    return [list(r) for r in inp[:2]]


def mode_fill(inp, out):
    c = Counter(v for r in inp for v in r).most_common(1)[0][0]
    return [[c, c], [c, c]]


ALTERNATIVES = [
    ("crop the top-right 2x2 corner", top_right),
    ("crop the bottom-left 2x2 corner", bottom_left),
    ("crop the bottom-right 2x2 corner", bottom_right),
    ("crop a 3x3 window at the top-left (window one too large)", crop3),
    ("crop only the top-left cell (window one too small)", crop1),
    ("crop the 2x2 window at offset (1,1)", offset_one),
    ("top-left 2x2 block, transposed", transposed),
    ("top-left 2x2 block, mirrored left-right", mirrored),
    ("crop a 2x3 window at the top-left (wrong width)", wide_window),
    ("crop the 2x2 window at the grid center", center),
    ("keep the first two input rows at full width", top_rows_full),
    ("fill a 2x2 grid with the most common input color", mode_fill),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/d10ecb37.json').read_text())
    train = task['train']
    print(len(ALTERNATIVES), 'readings,', len(train), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p['input'], p['output'])
            if g is not None and valid(g) and g != p['output']:
                n += 1
        print(n, desc)
