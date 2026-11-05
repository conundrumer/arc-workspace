import json
from collections import Counter, deque
from pathlib import Path

FILL = 3


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _largest_rect(inp, bg, blocked=None):
    """Largest-area all-background rectangle (r0, c0, r1, c1), inclusive."""
    h, w = len(inp), len(inp[0])
    ok = [[inp[r][c] == bg and not (blocked and blocked[0] <= r <= blocked[2] and blocked[1] <= c <= blocked[3])
           for c in range(w)] for r in range(h)]
    best, box = 0, None
    for r0 in range(h):
        colok = [True] * w
        for r1 in range(r0, h):
            for c in range(w):
                colok[c] = colok[c] and ok[r1][c]
            c = 0
            while c < w:
                if not colok[c]:
                    c += 1
                    continue
                s = c
                while c < w and colok[c]:
                    c += 1
                area = (r1 - r0 + 1) * (c - s)
                if area > best:
                    best, box = area, (r0, s, r1, c - 1)
    return box


def _green(box, h, w, mt=1, mb=1, ml=1, mr=1):
    """Cells of the box less a margin on each side that is not on the grid edge."""
    r0, c0, r1, c1 = box
    t = r0 + (mt if r0 > 0 else 0)
    b = r1 - (mb if r1 < h - 1 else 0)
    l = c0 + (ml if c0 > 0 else 0)
    r = c1 - (mr if c1 < w - 1 else 0)
    return {(i, j) for i in range(t, b + 1) for j in range(l, r + 1)}


def _apply(base, cells, color=FILL):
    g = [row[:] for row in base]
    for i, j in cells:
        g[i][j] = color
    return g


def _box_cells(box):
    r0, c0, r1, c1 = box
    return {(i, j) for i in range(r0, r1 + 1) for j in range(c0, c1 + 1)}


def _band(inp):
    return _largest_rect(inp, _bg(inp))


def ink_color(inp, out):
    bg = _bg(inp)
    ink = Counter(v for r in inp for v in r if v != bg).most_common(1)[0][0]
    return [[ink if v == FILL else v for v in r] for r in out]


def no_margin(inp, out):
    return _apply(out, _box_cells(_band(inp)))


def margin_two(inp, out):
    h, w = len(inp), len(inp[0])
    box = _band(inp)
    ring = _box_cells(box) - _green(box, h, w, 2, 2, 2, 2)
    g = [row[:] for row in out]
    for i, j in ring:
        g[i][j] = inp[i][j]
    return g


def margin_on_grid_edge(inp, out):
    h, w = len(inp), len(inp[0])
    box = _band(inp)
    r0, c0, r1, c1 = box
    inner = {(i, j) for i in range(r0 + 1, r1) for j in range(c0 + 1, c1)}
    g = [row[:] for row in out]
    for i, j in _box_cells(box) - inner:
        g[i][j] = inp[i][j]
    return g


def band_only(inp, out):
    h, w = len(inp), len(inp[0])
    return _apply(inp, _green(_band(inp), h, w))


def channels_only(inp, out):
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in out]
    for i, j in _green(_band(inp), h, w):
        g[i][j] = inp[i][j]
    return g


def right_channels_only(inp, out):
    box = _band(inp)
    g = [row[:] for row in out]
    for i in range(len(g)):
        for j in range(box[1]):
            g[i][j] = inp[i][j]
    return g


def second_rectangle(inp, out):
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    box = _band(inp)
    other = _largest_rect(inp, bg, blocked=box)
    if other is None:
        return None
    return _apply(inp, _green(other, h, w))


def flood_from_band(inp, out):
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    cells = _green(_band(inp), h, w)
    seen = set(cells)
    dq = deque(cells)
    while dq:
        i, j = dq.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, j + dj
            if 0 <= a < h and 0 <= b < w and (a, b) not in seen and inp[a][b] == bg:
                seen.add((a, b))
                dq.append((a, b))
    return _apply(inp, seen)


def crop_band(inp, out):
    r0, c0, r1, c1 = _band(inp)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def margin_one_side(inp, out):
    h, w = len(inp), len(inp[0])
    box = _band(inp)
    full = _green(box, h, w)
    # margin kept only on the top and left sides of the band
    wrong = _green(box, h, w, 1, 0, 1, 0)
    g = [row[:] for row in out]
    for i, j in wrong - full:
        g[i][j] = FILL
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("fill uses the noise color instead of the new color", ink_color),
    ("band filled to its full box, no margin kept at its sides", no_margin),
    ("margin is two cells wide along the band's sides", margin_two),
    ("margin also kept along the band sides on the grid edge", margin_on_grid_edge),
    ("only the band is filled, the channels to the edges are missed", band_only),
    ("only the channels are filled, the band itself is left empty", channels_only),
    ("channels are filled only on the right of the band, those on the left are missed", right_channels_only),
    ("the second-largest empty rectangle is filled instead of the band", second_rectangle),
    ("all background connected to the band is flooded", flood_from_band),
    ("output is only the crop of the band's box", crop_band),
    ("margin kept on the top and left sides only, bottom and right sides are filled to the edge", margin_one_side),
    ("output is the input unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/a64e4611.json'))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
