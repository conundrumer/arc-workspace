import json
from collections import Counter
from pathlib import Path


def parts(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(c for r in inp for c in r)
    bg = cnt.most_common(1)[0][0]
    boxes = {}
    for y in range(h):
        for x in range(w):
            c = inp[y][x]
            if c == bg:
                continue
            b = boxes.setdefault(c, [y, x, y, x])
            b[0] = min(b[0], y); b[1] = min(b[1], x)
            b[2] = max(b[2], y); b[3] = max(b[3], x)
    blank = None
    for c, (y0, x0, y1, x1) in boxes.items():
        if all(inp[y][x] == c for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)):
            blank = c
    ys = [y for y in range(h) for x in range(w) if inp[y][x] not in (bg, blank)]
    xs = [x for y in range(h) for x in range(w) if inp[y][x] not in (bg, blank)]
    block = (min(ys), min(xs), max(ys), max(xs))
    return bg, blank, boxes[blank], block


def crop(g, b):
    return [r[b[1]:b[3] + 1] for r in g[b[0]:b[2] + 1]]


def paste(g, b, sub):
    g = [r[:] for r in g]
    for i, row in enumerate(sub):
        for j, v in enumerate(row):
            y, x = b[0] + i, b[1] + j
            if 0 <= y <= b[2] and 0 <= x <= b[3] and y < len(g) and x < len(g[0]):
                g[y][x] = v
    return g


def fliplr(s): return [r[::-1] for r in s]
def flipud(s): return s[::-1]
def rot180(s): return [r[::-1] for r in s[::-1]]


def with_sub(inp, f):
    bg, blank, bb, kb = parts(inp)
    return paste(inp, bb, f(crop(inp, kb)))


def r_flipud(inp, out): return with_sub(inp, flipud)
def r_rot180(inp, out): return with_sub(inp, rot180)
def r_plain(inp, out): return with_sub(inp, lambda s: s)


def r_transpose(inp, out):
    bg, blank, bb, kb = parts(inp)
    s = crop(inp, kb)
    if len(s) != len(s[0]):
        return None
    return paste(inp, bb, [list(r) for r in zip(*s)])


def r_unfilled(inp, out):
    return [r[:] for r in inp]


def r_move(inp, out):
    bg, blank, bb, kb = parts(inp)
    g = [r[:] for r in out]
    for y in range(kb[0], kb[2] + 1):
        for x in range(kb[1], kb[3] + 1):
            g[y][x] = bg
    return g


def r_shift(inp, out):
    bg, blank, bb, kb = parts(inp)
    s = fliplr(crop(inp, kb))
    s = [[blank] + r[:-1] for r in s]
    return paste(inp, bb, s)


def r_solid_major(inp, out):
    bg, blank, bb, kb = parts(inp)
    s = crop(inp, kb)
    c = Counter(v for r in s for v in r).most_common(1)[0][0]
    return paste(inp, bb, [[c] * len(r) for r in s])


def r_solid_minor(inp, out):
    bg, blank, bb, kb = parts(inp)
    s = crop(inp, kb)
    c = Counter(v for r in s for v in r).most_common()[-1][0]
    return paste(inp, bb, [[c] * len(r) for r in s])


def r_both_flipped(inp, out):
    bg, blank, bb, kb = parts(inp)
    g = paste(out, kb, fliplr(crop(inp, kb)))
    return g


def r_major_only(inp, out):
    bg, blank, bb, kb = parts(inp)
    s = fliplr(crop(inp, kb))
    c = Counter(v for r in s for v in r).most_common(1)[0][0]
    return paste(inp, bb, [[v if v == c else blank for v in r] for r in s])


def r_swap(inp, out):
    bg, blank, bb, kb = parts(inp)
    s = fliplr(crop(inp, kb))
    cols = sorted({v for r in s for v in r})
    if len(cols) != 2:
        return None
    m = {cols[0]: cols[1], cols[1]: cols[0]}
    return paste(inp, bb, [[m[v] for v in r] for r in s])


def r_bg_mask(inp, out):
    bg, blank, bb, kb = parts(inp)
    s = fliplr(crop(inp, kb))
    c = Counter(v for r in s for v in r).most_common()[-1][0]
    return paste(inp, bb, [[bg if v == c else v for v in r] for r in s])


ALTERNATIVES = [
    ("copy the block into the blank flipped top-to-bottom instead of left-to-right", r_flipud),
    ("copy the block into the blank rotated 180 degrees", r_rot180),
    ("copy the block into the blank with no reflection", r_plain),
    ("copy the block into the blank transposed (square blocks only)", r_transpose),
    ("leave the blank rectangle unfilled (output equals input)", r_unfilled),
    ("move the block: fill the blank with the flipped block and erase the original to background", r_move),
    ("fill the blank with the flipped block shifted one column right, leaving the first column blank", r_shift),
    ("fill the blank solidly with the block's most common color", r_solid_major),
    ("fill the blank solidly with the block's least common color", r_solid_minor),
    ("flip the block in place as well as copying it (reflection applied to the source too)", r_both_flipped),
    ("copy only the block's most common color into the blank, leaving other cells blank", r_major_only),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/9f27f097.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings', len(pairs), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and valid(g) and g != p['output']:
                n += 1
        print(n, desc)
