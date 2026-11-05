import json
from collections import Counter
from pathlib import Path


def parts(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    ink = {(r, c) for r in range(h) for c in range(w) if inp[r][c] != bg}
    block = {(r, c) for (r, c) in ink
             if any((r + dr, c + dc) in ink for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    markers = sorted(ink - block)
    rs = [r for r, _ in block]
    cs = [c for _, c in block]
    return bg, block, markers, (min(rs), max(rs), min(cs), max(cs))


def draw(inp, mode):
    """Generic renderer: mode picks the variant of the line rule."""
    h, w = len(inp), len(inp[0])
    bg, block, markers, (r0, r1, c0, c1) = parts(inp)
    g = [row[:] for row in inp]
    bcol = inp[r0][c0]
    jobs = []
    for (r, c) in markers:
        col = inp[r][c]
        if r0 <= r <= r1:
            d = (0, 1) if c < c0 else (0, -1)
            jobs.append(((r, c), col, d, 'h'))
        elif c0 <= c <= c1:
            d = (1, 0) if r < r0 else (-1, 0)
            jobs.append(((r, c), col, d, 'v'))
        elif mode == 'all':
            if min(abs(r - r0), abs(r - r1)) < min(abs(c - c0), abs(c - c1)) if (r < r0 or r > r1) and (c < c0 or c > c1) else (r < r0 or r > r1):
                d = (1, 0) if r < r0 else (-1, 0)
                jobs.append(((r, c), col, d, 'v'))
            else:
                d = (0, 1) if c < c0 else (0, -1)
                jobs.append(((r, c), col, d, 'h'))
    if mode == 'nearest' and jobs:
        def dist(j):
            (r, c), _, d, _ = j
            return abs(r - (r0 if d[0] > 0 else r1)) + abs(c - (c0 if d[1] > 0 else c1))
        jobs = [min(jobs, key=dist)]
    if mode == 'first' and jobs:
        jobs = jobs[:1]
    if mode == 'vertical':
        jobs = [j for j in jobs if j[3] == 'v']
    if mode == 'horizontal':
        jobs = [j for j in jobs if j[3] == 'h']
    for (r, c), col, d, kind in jobs:
        if mode == 'away':
            d = (-d[0], -d[1])
        paint = col if mode != 'blockcolor' else bcol
        y, x = r, c
        while True:
            y += d[0]
            x += d[1]
            if not (0 <= y < h and 0 <= x < w):
                break
            if (y, x) in block:
                if mode == 'through':
                    g[y][x] = paint
                    continue
                break
            g[y][x] = paint
        if mode == 'short':
            # leave the cell next to the block unpainted
            ty, tx = y - d[0], x - d[1]
            if (ty, tx) != (r, c) and 0 <= ty < h and 0 <= tx < w:
                g[ty][tx] = bg
        if mode == 'erase':
            g[r][c] = bg
        if mode == 'thick':
            lo, hi = (c0, c1) if kind == 'v' else (r0, r1)
            y, x = r, c
            while True:
                y += d[0]
                x += d[1]
                if not (0 <= y < h and 0 <= x < w) or (y, x) in block:
                    break
                for k in range(lo, hi + 1):
                    yy, xx = (y, k) if kind == 'v' else (k, x)
                    if inp[yy][xx] == bg:
                        g[yy][xx] = col
    return g


def crop(inp, out):
    bg, block, markers, (r0, r1, c0, c1) = parts(inp)
    g = draw(inp, 'plain')
    ys = [r for r in range(len(g)) for c in range(len(g[0])) if g[r][c] != bg]
    xs = [c for r in range(len(g)) for c in range(len(g[0])) if g[r][c] != bg]
    return [row[min(xs):max(xs) + 1] for row in g[min(ys):max(ys) + 1]]


def keep_unaligned_only(inp, out):
    # lines painted for markers, but the block itself is erased
    bg, block, markers, _ = parts(inp)
    g = [row[:] for row in out]
    for (r, c) in block:
        g[r][c] = bg
    return g


def unfilled_longest(inp, out):
    # true output with the longest painted line left unpainted
    bg, block, markers, _ = parts(inp)
    h, w = len(inp), len(inp[0])
    diff = {(r, c) for r in range(h) for c in range(w) if inp[r][c] != out[r][c]}
    if not diff:
        return None
    best = []
    for (r, c) in markers:
        line = {p for p in diff if p[0] == r or p[1] == c}
        # lines of this marker: cells in the same row or column that differ
        if len(line) > len(best):
            best = list(line)
    g = [row[:] for row in out]
    for (r, c) in best:
        g[r][c] = bg
    return g


def mk(mode):
    return lambda inp, out: draw(inp, mode)


ALTERNATIVES = [
    ("Input returned unchanged: no line is drawn", lambda inp, out: [r[:] for r in inp]),
    ("Lines are drawn toward the block for every marker, aligned or not, along the nearer axis", mk('all')),
    ("Lines run from each marker away from the block, to the grid edge", mk('away')),
    ("Lines pass through the block and out its far side", mk('through')),
    ("Lines stop one cell short of the block", mk('short')),
    ("Lines are drawn in the block color instead of the marker color", mk('blockcolor')),
    ("Marker cell is erased to background after its line is drawn", mk('erase')),
    ("Only markers above or below the block (same columns) are extended", mk('vertical')),
    ("Only markers beside the block (same rows) are extended", mk('horizontal')),
    ("Only the marker nearest the block is extended", mk('nearest')),
    ("Each aligned marker paints a band as wide as the block, not a single line", mk('thick')),
    ("Output is cropped to the bounding box of everything non-background", crop),
]


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/2c608aff.json'))
    pairs = task['train']

    def valid(g, out):
        return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != out)

    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
