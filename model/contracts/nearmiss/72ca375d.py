from pathlib import Path
import json
from collections import Counter

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/72ca375d.json')


def bg_of(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def components(g, diag=True):
    bg = bg_of(g)
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    nb = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if diag:
        nb += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for r in range(h):
        for c in range(w):
            if g[r][c] != bg and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy, dx in nb:
                        a, b = y + dy, x + dx
                        if 0 <= a < h and 0 <= b < w and g[a][b] != bg and (a, b) not in seen:
                            seen.add((a, b))
                            st.append((a, b))
                comps.append(sorted(cells))
    return comps


def bbox(cells):
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return min(ys), min(xs), max(ys), max(xs)


def crop(g, cells, pad=(0, 0, 0, 0)):
    y0, x0, y1, x1 = bbox(cells)
    return [row[x0:x1 + 1] for row in g[y0:y1 + 1]]


def true_comp(inp, out):
    h, w = len(out), len(out[0])
    for cells in components(inp):
        y0, x0, y1, x1 = bbox(cells)
        if (y1 - y0 + 1, x1 - x0 + 1) == (h, w) and crop(inp, cells) == out:
            return cells
    return None


def others(inp, out):
    t = true_comp(inp, out)
    return [c for c in components(inp) if c != t]


def area(cells):
    y0, x0, y1, x1 = bbox(cells)
    return (y1 - y0 + 1) * (x1 - x0 + 1)


def largest_cells(inp, out):
    return crop(inp, max(components(inp), key=lambda c: (len(c), -c[0][0])))


def smallest_cells(inp, out):
    return crop(inp, min(components(inp), key=lambda c: (len(c), c[0][0])))


def largest_bbox(inp, out):
    return crop(inp, max(components(inp), key=lambda c: (area(c), -c[0][0])))


def topmost(inp, out):
    return crop(inp, min(components(inp), key=lambda c: (bbox(c)[0], bbox(c)[1])))


def rightmost(inp, out):
    return crop(inp, max(components(inp), key=lambda c: (bbox(c)[3], bbox(c)[2])))


def bottommost(inp, out):
    return crop(inp, max(components(inp), key=lambda c: (bbox(c)[2], bbox(c)[3])))


def pad_one(inp, out):
    bg = bg_of(inp)
    w = len(out[0])
    return [[bg] * (w + 2)] + [[bg] + r + [bg] for r in out] + [[bg] * (w + 2)]


def drop_last_col(inp, out):
    return [r[:-1] for r in out]


def drop_first_row(inp, out):
    return out[1:]


def left_half(inp, out):
    return [r[:max(1, len(r) // 2)] for r in out]


def all_content(inp, out):
    bg = bg_of(inp)
    cells = [(y, x) for y, r in enumerate(inp) for x, v in enumerate(r) if v != bg]
    return crop(inp, cells)


def invert(inp, out):
    bg = bg_of(inp)
    col = [v for r in out for v in r if v != bg][0]
    return [[bg if v == col else col for v in r] for r in out]


def fill_rect(inp, out):
    bg = bg_of(inp)
    col = [v for r in out for v in r if v != bg][0]
    return [[col] * len(r) for r in out]


def recolor_other(inp, out):
    bg = bg_of(inp)
    t = true_comp(inp, out)
    oc = [c for c in components(inp) if c != t]
    col = inp[oc[0][0][0]][oc[0][0][1]]
    return [[col if v != bg else v for v in r] for r in out]


def four_conn_first_piece(inp, out):
    # 4-connectivity splits pieces; take the largest 4-connected piece anywhere
    comps = components(inp, diag=False)
    return crop(inp, max(comps, key=lambda c: (len(c), -c[0][0])))


def vflip_out(inp, out):
    return out[::-1]


def hflip_out(inp, out):
    return [r[::-1] for r in out]


def transpose_out(inp, out):
    return [list(r) for r in zip(*out)]


ALTERNATIVES = [
    ("crop the component with the most cells", largest_cells),
    ("crop the component with the fewest cells", smallest_cells),
    ("crop the component with the largest bounding box", largest_bbox),
    ("crop the topmost component", topmost),
    ("crop the rightmost component", rightmost),
    ("crop the bottommost component", bottommost),
    ("bounding box padded by one background cell on every side", pad_one),
    ("bounding box one column too narrow (last column dropped)", drop_last_col),
    ("bounding box one row too short (first row dropped)", drop_first_row),
    ("crop of all non-background content as one box", all_content),
    ("piece drawn inverted inside its bounding box", invert),
    ("piece recolored with the color of another piece", recolor_other),
    ("piece bounding box filled solid", fill_rect),
    ("only the left half of the symmetric piece", left_half),
    ("largest 4-connected piece instead of 8-connected", four_conn_first_piece),
    ("output transposed", transpose_out),
]
ALTERNATIVES = ALTERNATIVES[:12]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    train = json.load(open(TASK))["train"]
    print("pairs", len(train), "readings", len(ALTERNATIVES))
    for desc, f in ALTERNATIVES:
        n = 0
        per = []
        for p in train:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                g = None
                print("  error", desc, e)
            ok = g is not None and valid(g, p["output"])
            per.append(int(ok))
            n += ok
        print(n, per, desc)
