import json
from pathlib import Path

N = 4


def quads(inp, dx=(0, 5), dy=(0, 5)):
    """Return [TL, TR, BL, BR] as 4x4 grids; dy/dx are start offsets."""
    res = []
    for r0 in dy:
        for c0 in dx:
            res.append([row[c0:c0 + N] for row in inp[r0:r0 + N]])
    return res


def overlay(qs, order):
    """order: quadrant indices, highest priority first. 0 is background."""
    g = [[0] * N for _ in range(N)]
    for i in range(N):
        for j in range(N):
            for q in order:
                if qs[q][i][j]:
                    g[i][j] = qs[q][i][j]
                    break
    return g


# Quadrant indices: 0 TL (7), 1 TR (4), 2 BL (8), 3 BR (6)
def true_order(inp, out):
    return (0, 1, 2, 3)


def swap_top(inp, out):
    return overlay(quads(inp), (1, 0, 2, 3))


def reverse_order(inp, out):
    return overlay(quads(inp), tuple(reversed(true_order(inp, out))))


def colmajor_scan(inp, out):
    return overlay(quads(inp), (0, 2, 1, 3))


def top_only(inp, out):
    return overlay(quads(inp), (0, 1))


def bottom_only(inp, out):
    return overlay(quads(inp), (2, 3))


def drop_last(inp, out):
    return overlay(quads(inp), true_order(inp, out)[:3])


def drop_first(inp, out):
    return overlay(quads(inp), true_order(inp, out)[1:])


def right_offset(inp, out):
    # right/bottom tiles start one cell early, so they include the separator
    return overlay(quads(inp, dx=(0, 4), dy=(0, 4)), true_order(inp, out))


def mirror_right(inp, out):
    qs = quads(inp)
    qs[1] = [r[::-1] for r in qs[1]]
    qs[3] = [r[::-1] for r in qs[3]]
    return overlay(qs, true_order(inp, out))


def overlap_cancels(inp, out):
    qs = quads(inp)
    g = overlay(qs, true_order(inp, out))
    for i in range(N):
        for j in range(N):
            if sum(1 for q in qs if q[i][j]) > 1:
                g[i][j] = 0
    return g


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def swap_bottom_tiles(inp, out):
    qs = quads(inp)
    qs[2], qs[3] = qs[3], qs[2]
    return overlay(qs, true_order(inp, out))


def lowest_wins_ink(inp, out):
    # overlap resolved by ink color value: larger color number wins
    qs = quads(inp)
    g = [[0] * N for _ in range(N)]
    for i in range(N):
        for j in range(N):
            g[i][j] = max(q[i][j] for q in qs)
    return g


ALTERNATIVES = [
    ("top-left and top-right tiles swap priority", swap_top),
    ("priority order reversed (lowest-priority ink wins)", reverse_order),
    ("tiles scanned column-major: TL, BL, TR, BR, first inked wins", colmajor_scan),
    ("only the top two tiles are overlaid", top_only),
    ("only the bottom two tiles are overlaid", bottom_only),
    ("lowest-priority tile is ignored", drop_last),
    ("highest-priority tile is ignored", drop_first),
    ("right and bottom tiles start one cell early, covering the separator", right_offset),
    ("right-hand tiles are mirrored horizontally before overlay", mirror_right),
    ("cells inked by more than one tile become background", overlap_cancels),
    ("output transposed", transposed),
    ("the two bottom tiles swap positions before overlay", swap_bottom_tiles),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not isinstance(g[0], list):
        return False
    w = len(g[0])
    if w == 0:
        return False
    for r in g:
        if not isinstance(r, list) or len(r) != w:
            return False
        for v in r:
            if type(v) is not int or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/a68b268e.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(f'{n}/{len(pairs)}  {desc}')
