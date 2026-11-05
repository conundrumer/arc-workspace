from pathlib import Path
import json
from collections import Counter

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/c6e1b8da.json')


def copy(g):
    return [r[:] for r in g]


def bg_of(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def find_rects(inp):
    """Per non-background color: body box, tail direction and tail length."""
    bg = bg_of(inp)
    cells = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != bg:
                cells.setdefault(v, set()).add((r, c))
    rects = []
    for col, cs in sorted(cells.items()):
        r0 = min(r for r, _ in cs)
        r1 = max(r for r, _ in cs)
        c0 = min(c for _, c in cs)
        c1 = max(c for _, c in cs)
        d = (0, 0)
        n = 0
        while True:
            w = c1 - c0 + 1
            h = r1 - r0 + 1
            def lone(pred, perp, lo, hi):
                xs = [perp(r, c) for r, c in cs if pred(r, c)]
                return len(xs) == 1 and lo < xs[0] < hi

            if h > 1 and lone(lambda r, c: r == r0, lambda r, c: c, c0, c1):
                r0 += 1; d = (-1, 0); n += 1
            elif h > 1 and lone(lambda r, c: r == r1, lambda r, c: c, c0, c1):
                r1 -= 1; d = (1, 0); n += 1
            elif w > 1 and lone(lambda r, c: c == c0, lambda r, c: r, r0, r1):
                c0 += 1; d = (0, -1); n += 1
            elif w > 1 and lone(lambda r, c: c == c1, lambda r, c: r, r0, r1):
                c1 -= 1; d = (0, 1); n += 1
            else:
                break
        rects.append(dict(col=col, box=(r0, r1, c0, c1), d=d, n=n, cells=cs))
    return bg, rects


def fill(g, box, col, dr=0, dc=0):
    r0, r1, c0, c1 = box
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            rr, cc = r + dr, c + dc
            if 0 <= rr < len(g) and 0 <= cc < len(g[0]):
                g[rr][cc] = col


def side(rect):
    r0, r1, c0, c1 = rect['box']
    return (r1 - r0 + 1) if rect['d'][0] else (c1 - c0 + 1)


def to_wall(rect, h, w):
    r0, r1, c0, c1 = rect['box']
    dr, dc = rect['d']
    if dr == 1:
        return h - 1 - r1
    if dr == -1:
        return r0
    if dc == 1:
        return w - 1 - c1
    return c0


def build(inp, dist=None, sign=1, restore=True, moved_on_top=True,
          keep_tail=False, keep_old=False, axes=(0, 1), only_longest=False,
          move_tail_too=False):
    bg, rects = find_rects(inp)
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    tailed = [r for r in rects if r['n'] > 0]
    movers = [r for r in tailed if (r['d'][0] != 0) == (0 in axes) or (r['d'][1] != 0) == (1 in axes)]
    movers = [r for r in tailed
              if (r['d'][0] != 0 and 0 in axes) or (r['d'][1] != 0 and 1 in axes)]
    if only_longest and tailed:
        best = max(r['n'] for r in tailed)
        movers = [r for r in movers if r['n'] == best]
    still = [r for r in rects if r not in movers]

    def draw_still():
        for r in still:
            if r['n'] == 0:
                if restore:
                    fill(g, r['box'], r['col'])
                else:
                    for (y, x) in r['cells']:
                        g[y][x] = r['col']
            else:
                # tailed rect that does not move stays with its input cells
                for (y, x) in r['cells']:
                    g[y][x] = r['col']

    def draw_moved():
        for r in movers:
            k = dist(r, h, w) if dist else r['n']
            dr, dc = r['d']
            if keep_old:
                fill(g, r['box'], r['col'])
            if move_tail_too:
                for (y, x) in r['cells']:
                    yy, xx = y + sign * dr * k, x + sign * dc * k
                    if 0 <= yy < h and 0 <= xx < w:
                        g[yy][xx] = r['col']
            else:
                fill(g, r['box'], r['col'], sign * dr * k, sign * dc * k)
            if keep_tail:
                for (y, x) in r['cells']:
                    if not (r['box'][0] <= y <= r['box'][1] and r['box'][2] <= x <= r['box'][3]):
                        g[y][x] = r['col']

    if moved_on_top:
        draw_still(); draw_moved()
    else:
        draw_moved(); draw_still()
    return g


def alt(**kw):
    def f(inp, out):
        g = build(inp, **kw)
        return None if g == out else g
    return f


def guard(f):
    def h(inp, out):
        g = f(inp, out)
        return None if g is None or g == out else g
    return h


def ignore_tail_input_stays(inp, out):
    # tails erased but nothing moves; rectangles redrawn whole in place
    bg, rects = find_rects(inp)
    g = [[bg] * len(inp[0]) for _ in inp]
    for r in rects:
        fill(g, r['box'], r['col'])
    return None if g == out else g


ALTERNATIVES = [
    ("moves each tailed rectangle by the tail length plus one cell",
     alt(dist=lambda r, h, w: r['n'] + 1)),
    ("moves each tailed rectangle by the tail length minus one cell",
     alt(dist=lambda r, h, w: r['n'] - 1)),
    ("moves each tailed rectangle away from its tail instead of toward its tip",
     alt(sign=-1)),
    ("moves each tailed rectangle by its own side length along the tail axis",
     alt(dist=lambda r, h, w: side(r))),
    ("slides each tailed rectangle in the tail direction until it reaches the grid edge",
     alt(dist=to_wall)),
    ("draws rectangles with no tail on top of moved ones",
     alt(moved_on_top=False)),
    ("does not restore cells of a tailless rectangle that a tailed rectangle hid",
     alt(restore=False)),
    ("moves the rectangle and leaves its tail drawn at the old place",
     alt(keep_tail=True)),
    ("copies the rectangle to the new place and keeps the old copy",
     alt(keep_old=True)),
    ("moves the rectangle together with its tail",
     alt(move_tail_too=True)),
    ("moves only rectangles whose tail is vertical",
     alt(axes=(0,))),
    ("erases tails and redraws every rectangle in place without moving",
     ignore_tail_input_stays),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(TASK))
    pairs = task['train']
    # sanity: the full model reproduces the true outputs
    ok = sum(build(p['input']) == p['output'] for p in pairs)
    print('reference model matches', ok, 'of', len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and valid(g) and g != p['output']:
                n += 1
        print(n, desc)
