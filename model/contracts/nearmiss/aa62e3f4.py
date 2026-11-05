from collections import Counter
from pathlib import Path

D4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
D8 = D4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def bg_of(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def counts(inp):
    bg = bg_of(inp)
    return Counter(v for r in inp for v in r if v != bg)


def rare(inp):
    c = counts(inp)
    return min(c, key=lambda k: c[k])


def halo_cells(inp, dirs, rounds=1):
    bg = bg_of(inp)
    h, w = len(inp), len(inp[0])
    mask = {(i, j) for i in range(h) for j in range(w) if inp[i][j] != bg}
    cur = set(mask)
    for _ in range(rounds):
        new = set()
        for (i, j) in cur:
            for di, dj in dirs:
                a, b = i + di, j + dj
                if 0 <= a < h and 0 <= b < w and (a, b) not in mask:
                    new.add((a, b))
        cur = cur | new
    return cur - mask, mask


def build(inp, halo, color, mask_color=None, keep=None):
    bg = bg_of(inp)
    g = [[bg if inp[i][j] != bg else inp[i][j] for j in range(len(inp[0]))] for i in range(len(inp))]
    if keep:
        for (i, j) in keep:
            g[i][j] = inp[i][j]
    if mask_color is not None:
        for i in range(len(inp)):
            for j in range(len(inp[0])):
                if inp[i][j] != bg:
                    g[i][j] = mask_color
    for (i, j) in halo:
        g[i][j] = color
    return g


def most_common_color(inp, out):
    c = counts(inp)
    h, _ = halo_cells(inp, D4)
    return build(inp, h, max(c, key=lambda k: c[k]))


def median_color(inp, out):
    c = counts(inp)
    if len(c) < 3:
        return None
    order = sorted(c, key=lambda k: c[k])
    h, _ = halo_cells(inp, D4)
    return build(inp, h, order[1])


def diag_halo(inp, out):
    h, _ = halo_cells(inp, D8)
    return build(inp, h, rare(inp))


def keep_object(inp, out):
    h, m = halo_cells(inp, D4)
    return build(inp, h, rare(inp), keep=m)


def two_rings(inp, out):
    h, _ = halo_cells(inp, D4, 2)
    return build(inp, h, rare(inp))


def filled_silhouette(inp, out):
    h, _ = halo_cells(inp, D4)
    r = rare(inp)
    return build(inp, h, r, mask_color=r)


def adjacent_color(inp, out):
    bg = bg_of(inp)
    g = [[bg if v != bg else v for v in row] for row in inp]
    hh, ww = len(inp), len(inp[0])
    for i in range(hh):
        for j in range(ww):
            if inp[i][j] == bg:
                for di, dj in D4:
                    a, b = i + di, j + dj
                    if 0 <= a < hh and 0 <= b < ww and inp[a][b] != bg:
                        g[i][j] = inp[a][b]
                        break
    return g


def keep_rare_cells(inp, out):
    h, m = halo_cells(inp, D4)
    r = rare(inp)
    return build(inp, h, r, keep={(i, j) for (i, j) in m if inp[i][j] == r})


def first_cell_color(inp, out):
    bg = bg_of(inp)
    col = next(v for row in inp for v in row if v != bg)
    h, _ = halo_cells(inp, D4)
    return build(inp, h, col)


def crop_halo_box(inp, out):
    bg = bg_of(out)
    cells = [(i, j) for i, r in enumerate(out) for j, v in enumerate(r) if v != bg]
    if not cells:
        return None
    i0 = min(i for i, _ in cells); i1 = max(i for i, _ in cells)
    j0 = min(j for _, j in cells); j1 = max(j for _, j in cells)
    return [r[j0:j1 + 1] for r in out[i0:i1 + 1]]


def mirrored(inp, out):
    return [r[::-1] for r in out]


ALTERNATIVES = [
    ("halo takes the object's most frequent color", most_common_color),
    ("halo takes the middle-frequency color instead of the rarest", median_color),
    ("halo includes diagonal neighbours (8-adjacent)", diag_halo),
    ("object stays in place and the halo is added around it", keep_object),
    ("halo is two cells thick", two_rings),
    ("object silhouette is also filled with the rare color", filled_silhouette),
    ("each halo cell copies the color of its adjacent object cell", adjacent_color),
    ("only the rare-colored cells stay; the rest of the object is erased", keep_rare_cells),
    ("halo takes the color of the first object cell in reading order", first_cell_color),
    ("output is cropped to the bounding box of the halo", crop_halo_box),
    ("halo is placed mirrored left to right", mirrored),
]


def valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    w = len(g[0])
    if any(not isinstance(r, list) or len(r) != w for r in g):
        return False
    if any(not isinstance(v, int) or not 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    import json
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/aa62e3f4.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
