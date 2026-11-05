import json
from collections import Counter
from pathlib import Path


def occluders(inp):
    """Boxes (r0, r1, c0, c1) of colors whose cells fill their bounding box."""
    pos = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            pos.setdefault(v, []).append((r, c))
    boxes = []
    for col, cells in pos.items():
        r0 = min(r for r, _ in cells)
        r1 = max(r for r, _ in cells)
        c0 = min(c for _, c in cells)
        c1 = max(c for _, c in cells)
        area = (r1 - r0 + 1) * (c1 - c0 + 1)
        if area == len(cells) and area >= 2:
            boxes.append((r0, r1, c0, c1, col))
    return boxes


def wallpaper(inp):
    """The full wallpaper, recovered from the visible cells and their shortest periods."""
    h, w = len(inp), len(inp[0])
    occ = occluders(inp)
    hidden = set()
    for r0, r1, c0, c1, _ in occ:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                hidden.add((r, c))
    best = None
    for py in range(1, h + 1):
        for px in range(1, w + 1):
            if best and py * px >= best[0]:
                continue
            tile = {}
            ok = True
            for r in range(h):
                for c in range(w):
                    if (r, c) in hidden:
                        continue
                    k = (r % py, c % px)
                    if tile.setdefault(k, inp[r][c]) != inp[r][c]:
                        ok = False
                        break
                if not ok:
                    break
            if ok and len(tile) == py * px:
                best = (py * px, py, px, tile)
    _, py, px, tile = best
    return [[tile[(r % py, c % px)] for c in range(w)] for r in range(h)]


def crop(g, r0, r1, c0, c1):
    r0, c0 = max(r0, 0), max(c0, 0)
    sub = [row[c0:c1 + 1] for row in g[r0:r1 + 1]]
    if not sub or not sub[0]:
        return None
    return sub


def area(b):
    return (b[1] - b[0] + 1) * (b[3] - b[2] + 1)


def smallest(inp, out):
    wp = wallpaper(inp)
    b = min(occluders(inp), key=area)
    return crop(wp, b[0], b[1], b[2], b[3])


def topmost(inp, out):
    wp = wallpaper(inp)
    b = min(occluders(inp), key=lambda b: (b[0], b[2]))
    return crop(wp, b[0], b[1], b[2], b[3])


def raw_input_crop(inp, out):
    b = max(occluders(inp), key=area)
    return crop(inp, b[0], b[1], b[2], b[3])


def rotate(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def vflip(inp, out):
    return [list(r) for r in out[::-1]]


def hflip(inp, out):
    return [list(r[::-1]) for r in out]


def shifted(dr, dc, dr1=0, dc1=0):
    def f(inp, out):
        wp = wallpaper(inp)
        b = max(occluders(inp), key=area)
        return crop(wp, b[0] + dr, b[1] + dr + dr1, b[2] + dc, b[3] + dc + dc1)
    return f


def solid(inp, out):
    top = Counter(v for row in wallpaper(inp) for v in row).most_common(1)[0][0]
    return [[top] * len(out[0]) for _ in out]


def whole_wallpaper(inp, out):
    return wallpaper(inp)


ALTERNATIVES = [
    ("select the smallest occluder instead of the largest", smallest),
    ("select the topmost occluder instead of the largest", topmost),
    ("copy the largest occluder's cells from the input without recovering the wallpaper", raw_input_crop),
    ("the recovered wallpaper rotated a quarter turn", rotate),
    ("the recovered wallpaper flipped top to bottom", vflip),
    ("the recovered wallpaper flipped left to right", hflip),
    ("crop starts one row above the occluder", shifted(-1, 0)),
    ("crop starts one column left of the occluder", shifted(0, -1)),
    ("crop one row and one column larger than the occluder", shifted(0, 0, 1, 1)),
    ("crop one row and one column smaller than the occluder", shifted(0, 0, -1, -1)),
    ("hidden cells all take the most common wallpaper color", solid),
    ("output the whole recovered wallpaper instead of the occluder's crop", whole_wallpaper),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/abbfd121.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(n, desc)
