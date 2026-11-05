import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _diff(inp, out):
    return [(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] != out[r][c]]


def _roles(inp, out):
    d = _diff(inp, out)
    if not d:
        return None
    cc = Counter(out[r][c] for r, c in d).most_common(1)[0][0]
    dd = Counter(inp[r][c] for r, c in d).most_common(1)[0][0]
    return d, cc, dd


def _copy(g):
    return [row[:] for row in g]


def unchanged(inp, out):
    return _copy(inp)


def erase_overlap(inp, out):
    x = _roles(inp, out)
    if not x:
        return None
    g = _copy(out)
    b = _bg(inp)
    for r, c in x[0]:
        g[r][c] = b
    return g


def extend_rows(inp, out):
    x = _roles(inp, out)
    if not x:
        return None
    g = _copy(out)
    b = _bg(inp)
    for r in {r for r, _ in x[0]}:
        for c in range(len(g[0])):
            if g[r][c] == b:
                g[r][c] = x[1]
    return g


def extend_cols(inp, out):
    x = _roles(inp, out)
    if not x:
        return None
    g = _copy(out)
    b = _bg(inp)
    for c in {c for _, c in x[0]}:
        for r in range(len(g)):
            if g[r][c] == b:
                g[r][c] = x[1]
    return g


def erase_occluded_object(inp, out):
    x = _roles(inp, out)
    if not x:
        return None
    b = _bg(inp)
    return [[b if v == x[2] else v for v in row] for row in out]


def recolor_occluded_object(inp, out):
    x = _roles(inp, out)
    if not x:
        return None
    return [[x[1] if v == x[2] else v for v in row] for row in out]


def bbox_grown_by_one(inp, out):
    x = _roles(inp, out)
    if not x:
        return None
    c0 = x[1]
    b = _bg(inp)
    cells = [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v == c0]
    r0 = min(r for r, _ in cells) - 1
    r1 = max(r for r, _ in cells) + 1
    k0 = min(c for _, c in cells) - 1
    k1 = max(c for _, c in cells) + 1
    g = _copy(out)
    for r in range(max(r0, 0), min(r1, len(g) - 1) + 1):
        for c in range(max(k0, 0), min(k1, len(g[0]) - 1) + 1):
            if g[r][c] == b:
                g[r][c] = c0
    return g


def span_short_by_one(inp, out):
    x = _roles(inp, out)
    if not x:
        return None
    c0 = x[1]
    b = _bg(inp)
    k0 = min(c for row in out for c, v in enumerate(row) if v == c0)
    return [[b if (v == c0 and c == k0) else v for c, v in enumerate(row)] for row in out]


def crop_to_objects(inp, out):
    b = _bg(inp)
    cells = [(r, c) for r, row in enumerate(out) for c, v in enumerate(row) if v != b]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    k0 = min(c for _, c in cells)
    k1 = max(c for _, c in cells)
    return [row[k0:k1 + 1] for row in out[r0:r1 + 1]]


def crop_to_repaired_region(inp, out):
    d = _diff(inp, out)
    if not d:
        return None
    r0 = min(r for r, _ in d)
    r1 = max(r for r, _ in d)
    k0 = min(c for _, c in d)
    k1 = max(c for _, c in d)
    return [row[k0:k1 + 1] for row in out[r0:r1 + 1]]


ALTERNATIVES = [
    ("output equals the input; the hidden part of the occluded shape is not restored", unchanged),
    ("overlap cells are erased to background instead of restored to the hidden shape's color", erase_overlap),
    ("restored color is also drawn along the full grid rows of the overlap, over background", extend_rows),
    ("restored color is also drawn along the full grid columns of the overlap, over background", extend_cols),
    ("the occluded shape is removed entirely", erase_occluded_object),
    ("the occluded shape is recolored entirely to the other shape's color", recolor_occluded_object),
    ("restored shape's box is taken one cell larger on every side and filled over background", bbox_grown_by_one),
    ("restored shape's span is one cell short: its leftmost column is erased", span_short_by_one),
    ("output is cropped to the bounding box of all non-background cells", crop_to_objects),
    ("output is only the repaired region, cropped", crop_to_repaired_region),
]


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/52df9849.json').read_text())
    pairs = task['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p['input'], p['output'])
            except Exception as e:
                print('  error', fn.__name__, e)
                continue
            if (g is not None and g and all(len(r) == len(g[0]) for r in g)
                    and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                    and g != p['output']):
                n += 1
        print(f'{n}/{len(pairs)}  {desc}')
