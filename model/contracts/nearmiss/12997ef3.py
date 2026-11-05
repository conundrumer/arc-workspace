import json
from collections import Counter
from pathlib import Path


def parse(inp, out):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    out_colors = {v for r in out for v in r}
    stencil = [c for c in cnt if c not in out_colors and c != bg]
    st = stencil[0]
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == st]
    r0 = min(r for r, c in cells); r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells); c1 = max(c for r, c in cells)
    shape = [[inp[r][c] == st for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]
    marks = [(r, c, inp[r][c]) for r in range(h) for c in range(w)
             if inp[r][c] not in (bg, st)]
    horiz = len({m[0] for m in marks}) == 1
    return dict(bg=bg, st=st, shape=shape, marks=marks, horiz=horiz,
                box=(r0, r1, c0, c1), inp=inp)


def tile(shape, color, bg, invert=False):
    return [[color if (cell != invert) else bg for cell in row] for row in shape]


def stack(tiles, horiz, gap=0, bg=0):
    if not tiles:
        return None
    th, tw = len(tiles[0]), len(tiles[0][0])
    if horiz:
        rows = []
        for i in range(th):
            row = []
            for k, t in enumerate(tiles):
                if k and gap:
                    row += [bg] * gap
                row += t[i]
            rows.append(row)
        return rows
    rows = []
    for k, t in enumerate(tiles):
        if k and gap:
            rows += [[bg] * tw for _ in range(gap)]
        rows += [list(r) for r in t]
    return rows


def ordered(p, key=None, reverse=False):
    horiz = p['horiz']
    ms = sorted(p['marks'], key=key or (lambda m: m[1] if horiz else m[0]))
    return ms[::-1] if reverse else ms


def reversed_order(inp, out):
    p = parse(inp, out)
    ms = ordered(p, reverse=True)
    return stack([tile(p['shape'], m[2], p['bg']) for m in ms], p['horiz'], bg=p['bg'])


def swapped_axis(inp, out):
    p = parse(inp, out)
    ms = ordered(p)
    return stack([tile(p['shape'], m[2], p['bg']) for m in ms], not p['horiz'], bg=p['bg'])


def stencil_color(inp, out):
    p = parse(inp, out)
    ms = ordered(p)
    return stack([tile(p['shape'], p['st'], p['bg']) for m in ms], p['horiz'], bg=p['bg'])


def inverted_shape(inp, out):
    p = parse(inp, out)
    ms = ordered(p)
    return stack([tile(p['shape'], m[2], p['bg'], invert=True) for m in ms], p['horiz'], bg=p['bg'])


def mirrored_shape(inp, out):
    p = parse(inp, out)
    ms = ordered(p)
    sh = [row[::-1] for row in p['shape']]
    return stack([tile(sh, m[2], p['bg']) for m in ms], p['horiz'], bg=p['bg'])


def flipped_vertical(inp, out):
    p = parse(inp, out)
    ms = ordered(p)
    sh = p['shape'][::-1]
    return stack([tile(sh, m[2], p['bg']) for m in ms], p['horiz'], bg=p['bg'])


def transposed_shape(inp, out):
    p = parse(inp, out)
    ms = ordered(p)
    sh = [list(r) for r in zip(*p['shape'])]
    return stack([tile(sh, m[2], p['bg']) for m in ms], p['horiz'], bg=p['bg'])


def first_mark_only(inp, out):
    p = parse(inp, out)
    m = ordered(p)[0]
    return tile(p['shape'], m[2], p['bg'])


def drop_last_tile(inp, out):
    p = parse(inp, out)
    ms = ordered(p)[:-1]
    return stack([tile(p['shape'], m[2], p['bg']) for m in ms], p['horiz'], bg=p['bg'])


def extra_repeat_tile(inp, out):
    p = parse(inp, out)
    ms = ordered(p)
    ms = ms + [ms[-1]]
    return stack([tile(p['shape'], m[2], p['bg']) for m in ms], p['horiz'], bg=p['bg'])


def gap_between_tiles(inp, out):
    p = parse(inp, out)
    ms = ordered(p)
    return stack([tile(p['shape'], m[2], p['bg']) for m in ms], p['horiz'], gap=1, bg=p['bg'])


def sorted_by_color(inp, out):
    p = parse(inp, out)
    ms = ordered(p, key=lambda m: -m[2])
    return stack([tile(p['shape'], m[2], p['bg']) for m in ms], p['horiz'], bg=p['bg'])


def crop_one_column_short(inp, out):
    p = parse(inp, out)
    ms = ordered(p)
    sh = [row[:-1] for row in p['shape']]
    return stack([tile(sh, m[2], p['bg']) for m in ms], p['horiz'], bg=p['bg'])


def box_padded_by_one(inp, out):
    p = parse(inp, out)
    ms = ordered(p)
    sh = [[False] + row + [False] for row in p['shape']]
    sh = [[False] * len(sh[0])] + sh + [[False] * len(sh[0])]
    return stack([tile(sh, m[2], p['bg']) for m in ms], p['horiz'], bg=p['bg'])


def single_tile_all_marks_color_by_row(inp, out):
    # tiles arranged in a 2D grid by mark position order, as if layout used both axes
    p = parse(inp, out)
    ms = ordered(p)
    n = len(ms)
    ts = [tile(p['shape'], m[2], p['bg']) for m in ms]
    top = stack(ts[: (n + 1) // 2], True, bg=p['bg'])
    bot = stack(ts[(n + 1) // 2:], True, bg=p['bg'])
    if bot is None:
        return None
    if len(bot[0]) < len(top[0]):
        bot = [r + [p['bg']] * (len(top[0]) - len(r)) for r in bot]
    return top + bot


ALTERNATIVES = [
    ("tiles placed in reverse mark order", reversed_order),
    ("tiles stacked along the wrong axis (other than the one the marks lie on)", swapped_axis),
    ("tiles keep the stencil color instead of the mark color", stencil_color),
    ("tiles use the complement of the stencil shape", inverted_shape),
    ("stencil shape mirrored left-right in each tile", mirrored_shape),
    ("stencil shape flipped top-bottom in each tile", flipped_vertical),
    ("stencil shape transposed in each tile", transposed_shape),
    ("only the first mark produces a tile", first_mark_only),
    ("last mark is dropped, one tile too few", drop_last_tile),
    ("last mark's tile is repeated, one tile too many", extra_repeat_tile),
    ("one background gap line between tiles", gap_between_tiles),
    ("tiles ordered by mark color value instead of mark position", sorted_by_color),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/12997ef3.json'))
    pairs = task['train']
    print('pairs', len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in pairs:
            try:
                g = fn(pr['input'], pr['output'])
            except Exception as e:
                print('  ERROR', fn.__name__, e)
                g = None
            if g is not None and _valid(g) and g != pr['output']:
                n += 1
        print(n, desc)
