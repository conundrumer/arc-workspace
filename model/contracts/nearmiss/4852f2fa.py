import json
from pathlib import Path

INK, MARK = 8, 4


def _cells(g, c):
    return [(r, k) for r, row in enumerate(g) for k, v in enumerate(row) if v == c]


def _box(g, colors):
    cs = [p for c in colors for p in _cells(g, c)]
    r0 = min(r for r, _ in cs); r1 = max(r for r, _ in cs)
    c0 = min(k for _, k in cs); c1 = max(k for _, k in cs)
    return r0, r1, c0, c1


def _tile(g, colors=(INK,)):
    r0, r1, c0, c1 = _box(g, colors)
    return [row[c0:c1 + 1] for row in g[r0:r1 + 1]]


def _n(g):
    return len(_cells(g, MARK))


def _hrep(t, n):
    return [row * n for row in t]


def _vrep(t, n):
    return [list(row) for _ in range(n) for row in t]


def one_more(inp, out):
    return _hrep(_tile(inp), _n(inp) + 1)


def one_fewer(inp, out):
    n = _n(inp) - 1
    return _hrep(_tile(inp), n) if n >= 1 else None


def single_copy(inp, out):
    return _tile(inp) if _n(inp) > 1 else None


def vertical_stack(inp, out):
    return _vrep(_tile(inp), _n(inp))


def bbox_with_markers(inp, out):
    return _hrep(_tile(inp, (INK, MARK)), _n(inp))


def mirrored_tile(inp, out):
    return _hrep([row[::-1] for row in _tile(inp)], _n(inp))


def alternate_mirror(inp, out):
    t = _tile(inp)
    n = _n(inp)
    if n < 2:
        return None
    return [sum((row[::-1] if i % 2 else row for i in range(n)), []) for row in t]


def recolored_marker(inp, out):
    return [[MARK if v == INK else v for v in row] for row in out]


def transposed_tile(inp, out):
    t = _tile(inp)
    tt = [list(r) for r in zip(*t)]
    return _hrep(tt, _n(inp))


def rotated_180(inp, out):
    t = [row[::-1] for row in _tile(inp)[::-1]]
    return _hrep(t, _n(inp))


def inverted_tile(inp, out):
    t = [[0 if v == INK else INK for v in row] for row in _tile(inp)]
    return _hrep(t, _n(inp))


def crop_short(inp, out):
    t = [row[:-1] for row in _tile(inp)]
    return _hrep(t, _n(inp))


ALTERNATIVES = [
    ("one copy too many: marker count plus one", one_more),
    ("one copy too few: marker count minus one", one_fewer),
    ("only one copy of the shape, markers ignored", single_copy),
    ("copies stacked vertically instead of side by side", vertical_stack),
    ("shape crop box also covers the marker cells", bbox_with_markers),
    ("every copy mirrored left to right", mirrored_tile),
    ("copies alternate between original and mirrored", alternate_mirror),
    ("copies painted in the marker color", recolored_marker),
    ("copies use the transposed shape", transposed_tile),
    ("copies use the shape rotated 180 degrees", rotated_180),
    ("copies use the shape with fill and empty swapped", inverted_tile),
    ("shape crop loses its last column", crop_short),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/4852f2fa.json'))
    train = task['train']
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                ok += 1
        print(ok, '/', len(train), desc)
