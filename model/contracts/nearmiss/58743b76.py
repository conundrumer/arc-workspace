from pathlib import Path
import json
from collections import Counter


def parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(c for r in inp for c in r).most_common(1)[0][0]
    cells = [(i, j) for i in range(h) for j in range(w) if inp[i][j] == bg]
    r0 = min(i for i, j in cells); r1 = max(i for i, j in cells)
    c0 = min(j for i, j in cells); c1 = max(j for i, j in cells)
    outside = [(i, j) for i in range(h) for j in range(w)
               if not (r0 <= i <= r1 and c0 <= j <= c1)]
    filler = Counter(inp[i][j] for i, j in outside).most_common(1)[0][0]
    kc = [(i, j) for i, j in outside if inp[i][j] != filler]
    k0 = min(i for i, j in kc); k1 = max(i for i, j in kc)
    l0 = min(j for i, j in kc); l1 = max(j for i, j in kc)
    key = [[inp[i][j] for j in range(l0, l1 + 1)] for i in range(k0, k1 + 1)]
    return dict(h=h, w=w, bg=bg, box=(r0, r1, c0, c1), filler=filler,
                keybox=(k0, k1, l0, l1), key=key)


def recolor(inp, pick, box=None, key=None, clear_key=False, filler_to=None):
    p = parse(inp)
    r0, r1, c0, c1 = box or p['box']
    key = key or p['key']
    ch, cw = r1 - r0 + 1, c1 - c0 + 1
    g = [row[:] for row in inp]
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            if inp[i][j] != p['bg']:
                g[i][j] = pick(i - r0, j - c0, ch, cw, key, i, j, p)
    if clear_key:
        k0, k1, l0, l1 = p['keybox']
        for i in range(k0, k1 + 1):
            for j in range(l0, l1 + 1):
                g[i][j] = p['filler']
    return g


def std(a, b, ch, cw, key):
    kh, kw = len(key), len(key[0])
    return key[a * kh // ch][b * kw // cw]


def flip_h(k): return [r[::-1] for r in k]
def flip_v(k): return k[::-1]
def transpose(k): return [list(r) for r in zip(*k)]
def rot_cw(k): return [list(r) for r in zip(*k[::-1])]


def mirror_h(inp, out):
    return recolor(inp, lambda a, b, ch, cw, k, i, j, p: std(a, b, ch, cw, flip_h(k)))

def mirror_v(inp, out):
    return recolor(inp, lambda a, b, ch, cw, k, i, j, p: std(a, b, ch, cw, flip_v(k)))

def transposed(inp, out):
    return recolor(inp, lambda a, b, ch, cw, k, i, j, p: std(a, b, ch, cw, transpose(k)))

def rotated(inp, out):
    return recolor(inp, lambda a, b, ch, cw, k, i, j, p: std(a, b, ch, cw, rot_cw(k)))

def columns_only(inp, out):
    return recolor(inp, lambda a, b, ch, cw, k, i, j, p: k[0][b * len(k[0]) // cw])

def rows_only(inp, out):
    return recolor(inp, lambda a, b, ch, cw, k, i, j, p: k[a * len(k) // ch][0])

def split_late(inp, out):
    # boundary one cell too far: quadrant edge at ch//2 + 1
    def pick(a, b, ch, cw, k, i, j, p):
        return k[1 if a >= ch // 2 + 1 else 0][1 if b >= cw // 2 + 1 else 0]
    return recolor(inp, pick)

def split_whole_grid(inp, out):
    # quadrant taken from the position in the whole grid, not the canvas
    def pick(a, b, ch, cw, k, i, j, p):
        return k[1 if i >= p['h'] // 2 else 0][1 if j >= p['w'] // 2 else 0]
    return recolor(inp, pick)

def single_color(inp, out):
    return recolor(inp, lambda a, b, ch, cw, k, i, j, p: k[0][0])

def key_cleared(inp, out):
    return recolor(inp, lambda a, b, ch, cw, k, i, j, p: std(a, b, ch, cw, k), clear_key=True)

def canvas_crop(inp, out):
    r0, r1, c0, c1 = parse(inp)['box']
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]

def key_color_by_mark(inp, out):
    # the mark's own color picks the key cell by index instead of position
    def pick(a, b, ch, cw, k, i, j, p):
        flat = [c for r in k for c in r]
        return flat[inp[i][j] % len(flat)]
    return recolor(inp, pick)


ALTERNATIVES = [
    ("key mirrored left-right before use", mirror_h),
    ("key mirrored top-bottom before use", mirror_v),
    ("key transposed across its main diagonal", transposed),
    ("key rotated 90 degrees clockwise", rotated),
    ("only the horizontal half picks the color, using the key's top row", columns_only),
    ("only the vertical half picks the color, using the key's left column", rows_only),
    ("quadrant boundary one cell past the canvas midpoint", split_late),
    ("quadrant taken from the whole grid midpoint, not the canvas", split_whole_grid),
    ("every mark takes the key's top-left color", single_color),
    ("marks recolored correctly but the key is erased to filler", key_cleared),
    ("output is only the canvas region", canvas_crop),
    ("mark's own color indexes a key cell instead of its position", key_color_by_mark),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r) and g != out)


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/58743b76.json')))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in t['train']:
            g = f(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(n, len(t['train']), desc)
