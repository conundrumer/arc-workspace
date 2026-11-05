import json
from collections import Counter
from pathlib import Path


def bg_of(g):
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def comps(g, diag=True):
    bg = bg_of(g)
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    nb = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a or b) and (diag or not (a and b))]
    for i in range(h):
        for j in range(w):
            if g[i][j] == bg or (i, j) in seen:
                continue
            st = [(i, j)]
            seen.add((i, j))
            cells = []
            while st:
                y, x = st.pop()
                cells.append((y, x))
                for dy, dx in nb:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != bg and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        st.append((ny, nx))
            res.append(sorted(cells))
    return res


def copy(g):
    return [r[:] for r in g]


def swap_cells(g, cells):
    cols = sorted({g[y][x] for y, x in cells})
    if len(cols) != 2:
        return None
    a, b = cols
    return {(y, x): (b if g[y][x] == a else a) for y, x in cells}


def swap_all(inp, skip=None, only=None, rowfilter=None):
    g = copy(inp)
    cs = comps(inp)
    for k, cells in enumerate(cs):
        if skip is not None and k == skip(cs):
            continue
        if only is not None and k not in only(cs):
            continue
        m = swap_cells(inp, cells)
        if m is None:
            continue
        for (y, x), v in m.items():
            if rowfilter is None or rowfilter(cells, y):
                g[y][x] = v
    return g


def leave_largest(inp, out):
    return swap_all(inp, skip=lambda cs: max(range(len(cs)), key=lambda k: len(cs[k])))


def leave_last(inp, out):
    return swap_all(inp, skip=lambda cs: len(cs) - 1)


def only_first_or_none(inp, out):
    cs = comps(inp)
    if len(cs) < 2:
        return None
    return swap_all(inp, only=lambda cs: [0])


def top_half_only(inp, out):
    return swap_all(inp, rowfilter=lambda cells, y: y < (min(c[0] for c in cells) + max(c[0] for c in cells) + 1) / 2 )


def flip_objects(inp, out):
    g = copy(inp)
    for cells in comps(inp):
        x0 = min(x for _, x in cells)
        x1 = max(x for _, x in cells)
        for y, x in cells:
            g[y][x0 + x1 - x] = inp[y][x]
    return g


def flip_vertical(inp, out):
    g = copy(inp)
    for cells in comps(inp):
        y0 = min(y for y, _ in cells)
        y1 = max(y for y, _ in cells)
        for y, x in cells:
            g[y0 + y1 - y][x] = inp[y][x]
    return g


def erase_minority(inp, out):
    bg = bg_of(inp)
    g = copy(inp)
    for cells in comps(inp):
        cnt = Counter(inp[y][x] for y, x in cells)
        mn = min(cnt, key=lambda c: (cnt[c], c))
        for y, x in cells:
            if inp[y][x] == mn:
                g[y][x] = bg
    return g


def flatten_majority(inp, out):
    g = copy(inp)
    for cells in comps(inp):
        cnt = Counter(inp[y][x] for y, x in cells)
        mj = max(cnt, key=lambda c: (cnt[c], c))
        for y, x in cells:
            g[y][x] = mj
    return g


def global_swap_first(inp, out):
    cs = comps(inp)
    m = swap_cells(inp, cs[0])
    a, b = sorted({inp[y][x] for y, x in cs[0]})
    g = copy(inp)
    for y, r in enumerate(inp):
        for x, v in enumerate(r):
            if v == a:
                g[y][x] = b
            elif v == b:
                g[y][x] = a
    return g


def swap_with_background(inp, out):
    bg = bg_of(inp)
    cnt = Counter(c for r in inp for c in r if c != bg)
    mj = max(cnt, key=lambda c: (cnt[c], c))
    return [[mj if v == bg else (bg if v == mj else v) for v in r] for r in inp]


def crop_largest_swapped(inp, out):
    cs = comps(inp)
    cells = max(cs, key=len)
    g = swap_all(inp)
    y0 = min(y for y, _ in cells); y1 = max(y for y, _ in cells)
    x0 = min(x for _, x in cells); x1 = max(x for _, x in cells)
    return [r[x0:x1 + 1] for r in g[y0:y1 + 1]]


def row_stripe_swap(inp, out):
    # swap per row instead of per object: within each row of an object, swap its colors only if row has two colors
    g = copy(inp)
    for cells in comps(inp):
        rows = {}
        for y, x in cells:
            rows.setdefault(y, []).append(x)
        for y, xs in rows.items():
            cols = sorted({inp[y][x] for x in xs})
            if len(cols) == 2:
                a, b = cols
                for x in xs:
                    g[y][x] = b if inp[y][x] == a else a
    return g


ALTERNATIVES = [
    ("swap colors in every object except the largest", leave_largest),
    ("swap colors in every object except the last one in scan order", leave_last),
    ("swap colors only in the first object in scan order", only_first_or_none),
    ("swap colors only in the top half of each object", top_half_only),
    ("mirror each object left-right instead of swapping its colors", flip_objects),
    ("mirror each object top-bottom instead of swapping its colors", flip_vertical),
    ("erase the minority color of each object to background", erase_minority),
    ("fill each object with its majority color", flatten_majority),
    ("swap the first object's two colors across the whole grid", global_swap_first),
    ("swap background with the most common figure color", swap_with_background),
    ("output only the largest object, color-swapped, cropped", crop_largest_swapped),
    ("swap the two colors within each object row only where the row has both colors", row_stripe_swap),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/45737921.json'))
    pairs = task['train']
    print('pairs', len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(n, desc)
