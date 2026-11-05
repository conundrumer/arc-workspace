import json
from collections import Counter
from pathlib import Path


def parse(inp):
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    frame = max((c for c in cnt if c != bg), key=lambda c: cnt[c])
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == frame]
    r0 = min(r for r, c in cells)
    r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells)
    c1 = max(c for r, c in cells)
    marks = sorted(
        ((r + c, inp[r][c]) for r, row in enumerate(inp) for c, v in enumerate(row)
         if v not in (bg, frame)))
    cols = [v for _, v in marks]
    return bg, frame, (r0, r1, c0, c1), cols


def paint(inp, box, colfn, include_frame=False, depthfn=None):
    r0, r1, c0, c1 = box
    g = [row[:] for row in inp]
    lo = 0 if include_frame else 1
    for r in range(r0 + lo, r1 - lo + 1):
        for c in range(c0 + lo, c1 - lo + 1):
            if depthfn:
                d = depthfn(r, c, box)
            else:
                d = min(r - r0, r1 - r, c - c0, c1 - c) - 1
            g[r][c] = colfn(d, box)
    return g


def pick(cols, d):
    return cols[min(max(d, 0), len(cols) - 1)]


def reversed_order(inp, out):
    bg, fr, box, cols = parse(inp)
    cols = cols[::-1]
    return paint(inp, box, lambda d, b: pick(cols, d))


def cycle(inp, out):
    bg, fr, box, cols = parse(inp)
    return paint(inp, box, lambda d, b: cols[d % len(cols)])


def innermost_empty(inp, out):
    bg, fr, box, cols = parse(inp)
    def col(d, b):
        r0, r1, c0, c1 = b
        maxd = (min(r1 - r0, c1 - c0) - 1) // 2 - 1
        return bg if d == maxd else pick(cols, d)
    return paint(inp, box, col)


def frame_recolored(inp, out):
    bg, fr, box, cols = parse(inp)
    return paint(inp, box, lambda d, b: pick(cols, d + 1), include_frame=True,
                 depthfn=lambda r, c, b: min(r - b[0], b[1] - r, c - b[2], b[3] - c) - 1)


def diamond(inp, out):
    bg, fr, box, cols = parse(inp)
    def dep(r, c, b):
        r0, r1, c0, c1 = b
        return min(r - r0, r1 - r) + min(c - c0, c1 - c) - 2
    return paint(inp, box, lambda d, b: pick(cols, d), depthfn=dep)


def uniform_first(inp, out):
    bg, fr, box, cols = parse(inp)
    return paint(inp, box, lambda d, b: cols[0])


def uniform_last(inp, out):
    bg, fr, box, cols = parse(inp)
    return paint(inp, box, lambda d, b: cols[-1])


def markers_erased(inp, out):
    bg, fr, box, cols = parse(inp)
    return [[bg if v not in (bg, fr) else v for v in row] for row in out]


def sorted_by_value(inp, out):
    bg, fr, box, cols = parse(inp)
    cols = sorted(cols)
    return paint(inp, box, lambda d, b: pick(cols, d))


def inside_out(inp, out):
    bg, fr, box, cols = parse(inp)
    def col(d, b):
        r0, r1, c0, c1 = b
        maxd = (min(r1 - r0, c1 - c0) - 1) // 2 - 1
        return pick(cols, maxd - d)
    return paint(inp, box, col)


def shrunk_by_one(inp, out):
    # rings start one cell inside the frame's inner edge
    bg, fr, box, cols = parse(inp)
    r0, r1, c0, c1 = box
    g = paint(inp, box, lambda d, b: pick(cols, d - 1))
    for r in range(r0 + 1, r1):
        for c in range(c0 + 1, c1):
            if min(r - r0, r1 - r, c - c0, c1 - c) == 1:
                g[r][c] = inp[r][c]
    return g


def outer_only_marker_ring(inp, out):
    # only the outer ring is painted, deeper cells stay empty
    bg, fr, box, cols = parse(inp)
    return paint(inp, box, lambda d, b: cols[0] if d == 0 else bg)


ALTERNATIVES = [
    ("marker order reversed: farthest from the corner paints the outer ring", reversed_order),
    ("ring colors cycle through the markers instead of the last marker filling the center", cycle),
    ("innermost ring left empty", innermost_empty),
    ("frame itself is recolored and rings shifted one marker", frame_recolored),
    ("rings measured by Manhattan distance (diamond) instead of square rings", diamond),
    ("whole interior filled with the first marker", uniform_first),
    ("whole interior filled with the last marker", uniform_last),
    ("rings drawn correctly but the diagonal markers erased", markers_erased),
    ("markers ordered by color value instead of distance from the corner", sorted_by_value),
    ("marker order applied from the center outward", inside_out),
    ("rings start one cell inside the frame, leaving a gap ring", shrunk_by_one),
    ("only the outermost interior ring is painted", outer_only_marker_ring),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/99306f82.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for name, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g) and g != p['output']:
                n += 1
        print(n, name)
