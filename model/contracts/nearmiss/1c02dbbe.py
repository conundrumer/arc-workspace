import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r if v)
    slab = cnt.most_common(1)[0][0]
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == slab]
    sr0 = min(r for r, c in cells)
    sr1 = max(r for r, c in cells)
    sc0 = min(c for r, c in cells)
    sc1 = max(c for r, c in cells)
    marks = {}
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v and v != slab:
                marks.setdefault(v, []).append((r, c))
    return h, w, slab, (sr0, sr1, sc0, sc1), marks


def _box(pts):
    return (min(r for r, c in pts), max(r for r, c in pts),
            min(c for r, c in pts), max(c for r, c in pts))


def _blank(inp, slab_box, slab):
    h, w = len(inp), len(inp[0])
    sr0, sr1, sc0, sc1 = slab_box
    g = [[0] * w for _ in range(h)]
    for r in range(sr0, sr1 + 1):
        for c in range(sc0, sc1 + 1):
            g[r][c] = slab
    return g


def _paint(g, box, color, slab_box=None):
    r0, r1, c0, c1 = box
    if slab_box:
        r0, r1 = max(r0, slab_box[0]), min(r1, slab_box[1])
        c0, c1 = max(c0, slab_box[2]), min(c1, slab_box[3])
    for r in range(max(r0, 0), min(r1, len(g) - 1) + 1):
        for c in range(max(c0, 0), min(c1, len(g[0]) - 1) + 1):
            g[r][c] = color


def _each_box(inp, fn, clip=True):
    h, w, slab, sb, marks = _parse(inp)
    g = _blank(inp, sb, slab)
    for col, pts in marks.items():
        b = fn(pts, sb)
        if b is None:
            return None
        _paint(g, b, col, sb if clip else None)
    return g


def unclipped_box(inp, out):
    return _each_box(inp, lambda p, sb: _box(p), clip=False)


def marks_left_in_place(inp, out):
    h, w, slab, sb, marks = _parse(inp)
    g = [row[:] for row in out]
    for pts in marks.values():
        for r, c in pts:
            g[r][c] = inp[r][c]
    return g


def hidden_corner_is_slab(inp, out):
    h, w, slab, sb, marks = _parse(inp)
    g = [row[:] for row in out]
    for pts in marks.values():
        for r, c in pts:
            if out[r][c] != 0:
                g[r][c] = slab
    return g


def two_marks_only(inp, out):
    def f(pts, sb):
        return _box(sorted(pts)[:2])
    return _each_box(inp, f)


def full_width_band(inp, out):
    def f(pts, sb):
        b = _box(pts)
        return (b[0], b[1], sb[2], sb[3])
    return _each_box(inp, f)


def full_height_band(inp, out):
    def f(pts, sb):
        b = _box(pts)
        return (sb[0], sb[1], b[2], b[3])
    return _each_box(inp, f)


def whole_slab_one_color(inp, out):
    h, w, slab, sb, marks = _parse(inp)
    col = inp[min(p for pts in marks.values() for p in pts)[0]][min(p for pts in marks.values() for p in pts)[1]]
    g = _blank(inp, sb, slab)
    _paint(g, sb, col)
    return g


def exclusive_far_edge(inp, out):
    def f(pts, sb):
        b = _box(pts)
        return (b[0], b[1] - 1, b[2], b[3] - 1)
    return _each_box(inp, f)


def grown_by_one(inp, out):
    def f(pts, sb):
        b = _box(pts)
        return (b[0] - 1, b[1] + 1, b[2] - 1, b[3] + 1)
    return _each_box(inp, f)


def only_painted_kept(inp, out):
    h, w, slab, sb, marks = _parse(inp)
    return [[v if v != slab else 0 for v in row] for row in out]


def crop_to_slab(inp, out):
    h, w, slab, sb, marks = _parse(inp)
    return [row[sb[2]:sb[3] + 1] for row in out[sb[0]:sb[1] + 1]]


def swapped_colors(inp, out):
    h, w, slab, sb, marks = _parse(inp)
    cols = sorted(marks)
    if len(cols) < 2:
        return None
    m = {cols[i]: cols[(i + 1) % len(cols)] for i in range(len(cols))}
    return [[m.get(v, v) for v in row] for row in out]


ALTERNATIVES = [
    ("Region is the mark bounding box without clipping to the slab, so paint spills onto background", unclipped_box),
    ("Marks are not removed from the output", marks_left_in_place),
    ("Slab cells hidden under corner marks are treated as plain slab, not painted", hidden_corner_is_slab),
    ("Region uses only the first two marks of each color", two_marks_only),
    ("Paint spans the full slab width over the marks' row range", full_width_band),
    ("Paint spans the full slab height over the marks' column range", full_height_band),
    ("Whole slab is painted with one mark's color", whole_slab_one_color),
    ("Region drops the last row and column of the mark bounding box (off by one)", exclusive_far_edge),
    ("Region is the mark bounding box grown by one cell on each side", grown_by_one),
    ("Unpainted slab cells are erased to background", only_painted_kept),
    ("Output is cropped to the slab bounding box", crop_to_slab),
    ("Mark colors are cyclically swapped between regions", swapped_colors),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/1c02dbbe.json').read_text())
    train = task['train']
    print(len(ALTERNATIVES), 'readings,', len(train), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(n, fn.__name__, '-', desc)
