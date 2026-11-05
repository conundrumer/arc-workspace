import json
from pathlib import Path


def blocks(inp):
    """Return {color: (r0, c0, r1, c1)} bounding boxes of non-background colors."""
    from collections import Counter
    bg = Counter(v for row in inp for v in row).most_common(1)[0][0]
    box = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == bg:
                continue
            if v not in box:
                box[v] = [r, c, r, c]
            else:
                b = box[v]
                b[0] = min(b[0], r); b[1] = min(b[1], c)
                b[2] = max(b[2], r); b[3] = max(b[3], c)
    return bg, box


def draw(inp, dirs, skip=0, limit=None, only=None, paint=None):
    """Draw a ray per block. dirs[color] = (dr, dc) direction; the ray leaves the
    block corner that faces that direction."""
    bg, box = blocks(inp)
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for col, (r0, c0, r1, c1) in box.items():
        if only is not None and col not in only:
            continue
        if col not in dirs:
            continue
        dr, dc = dirs[col]
        r = r0 if dr < 0 else r1
        c = c0 if dc < 0 else c1
        if dr == 0:
            r = r0
        if dc == 0:
            c = c0
        r += dr * (1 + skip)
        c += dc * (1 + skip)
        n = 0
        while 0 <= r < h and 0 <= c < w and (limit is None or n < limit):
            if g[r][c] == bg:
                g[r][c] = (paint or {}).get(col, col)
            r += dr
            c += dc
            n += 1
    return g


def ok(g, out):
    return g if g != out else None


TRUE = {1: (-1, -1), 2: (1, 1)}


def swapped(inp, out):
    return ok(draw(inp, {1: (1, 1), 2: (-1, -1)}), out)


def orthogonal(inp, out):
    return ok(draw(inp, {1: (0, -1), 2: (0, 1)}), out)


def anti_diag(inp, out):
    return ok(draw(inp, {1: (-1, 1), 2: (1, -1)}), out)


def gap_one(inp, out):
    return ok(draw(inp, TRUE, skip=1), out)


def limit_three(inp, out):
    return ok(draw(inp, TRUE, limit=3), out)


def only_one(inp, out):
    return ok(draw(inp, TRUE, only={1}), out)


def only_two(inp, out):
    return ok(draw(inp, TRUE, only={2}), out)


def wrong_color(inp, out):
    return ok(draw(inp, TRUE, paint={1: 2, 2: 1}), out)


def both_directions(inp, out):
    g = draw(inp, TRUE)
    bg, box = blocks(inp)
    h, w = len(g), len(g[0])
    for col, (r0, c0, r1, c1) in box.items():
        dr, dc = TRUE[col]
        r = (r1 if dr > 0 else r0) - dr  # opposite corner, going back
        r = r0 if dr > 0 else r1
        c = c0 if dc > 0 else c1
        r -= dr
        c -= dc
        while 0 <= r < h and 0 <= c < w:
            if g[r][c] == bg:
                g[r][c] = col
            r -= dr
            c -= dc
    return ok(g, out)


def both_up_left(inp, out):
    return ok(draw(inp, {1: (-1, -1), 2: (-1, -1)}), out)


def start_inside_row(inp, out):
    # Ray leaves from the block's edge row, going straight vertically
    return ok(draw(inp, {1: (-1, 0), 2: (1, 0)}), out)


def true_without_far_half(inp, out):
    # Right ray: cuts true output's rays at the grid's half size
    h, w = len(out), len(out[0])
    bg, _ = blocks(inp)
    g = [row[:] for row in out]
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg and g[r][c] != bg and (r + c) >= 0 and r >= h // 2 and c >= w // 2:
                g[r][c] = bg
    return ok(g, out)


ALTERNATIVES = [
    ("colors 1 and 2 swap diagonal directions", swapped),
    ("rays go horizontally instead of diagonally", orthogonal),
    ("rays go along the anti-diagonal (1 up-right, 2 down-left)", anti_diag),
    ("rays start one cell further from the block (gap)", gap_one),
    ("rays stop after 3 cells", limit_three),
    ("only color 1 casts a ray", only_one),
    ("only color 2 casts a ray", only_two),
    ("rays are drawn in the other block's color", wrong_color),
    ("each block casts rays in both diagonal directions", both_directions),
    ("both colors cast rays up-left", both_up_left),
    ("rays go vertically instead of diagonally", start_inside_row),
    ("rays are cut off in the lower-right quadrant", true_without_far_half),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/5c0a986e.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings', len(pairs), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(n, desc)
