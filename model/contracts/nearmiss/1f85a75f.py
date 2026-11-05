import json
from collections import Counter
from pathlib import Path

D8 = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
D4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def bg_of(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def components(inp, dirs, same_color=False):
    bg = bg_of(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for y in range(h):
        for x in range(w):
            if inp[y][x] == bg or (y, x) in seen:
                continue
            seen.add((y, x))
            stack, comp = [(y, x)], []
            while stack:
                cy, cx = stack.pop()
                comp.append((cy, cx))
                for dy, dx in dirs:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] != bg:
                        if same_color and inp[ny][nx] != inp[cy][cx]:
                            continue
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append(comp)
    return comps


def crop_cells(inp, cells, keep_all=False, margin=0, fill_all=False):
    bg = bg_of(inp)
    h, w = len(inp), len(inp[0])
    y0 = max(0, min(y for y, _ in cells) - margin)
    y1 = min(h - 1, max(y for y, _ in cells) + margin)
    x0 = max(0, min(x for _, x in cells) - margin)
    x1 = min(w - 1, max(x for _, x in cells) + margin)
    s = set(cells)
    col = Counter(inp[y][x] for y, x in cells).most_common(1)[0][0]
    g = []
    for y in range(y0, y1 + 1):
        row = []
        for x in range(x0, x1 + 1):
            if fill_all:
                row.append(col)
            elif keep_all or (y, x) in s:
                row.append(inp[y][x])
            else:
                row.append(bg)
        g.append(row)
    return g


def true_shape(inp):
    return max(components(inp, D8), key=len)


def keep_all_colors(inp, out):
    return crop_cells(inp, true_shape(inp), keep_all=True, margin=1)


def second_largest(inp, out):
    comps = sorted(components(inp, D8), key=len, reverse=True)
    return crop_cells(inp, comps[1])


def shifted_box(inp, out):
    cells = true_shape(inp)
    h = len(inp)
    y0 = min(y for y, _ in cells) + 1
    y1 = max(y for y, _ in cells) + 1
    x0 = min(x for _, x in cells)
    x1 = max(x for _, x in cells)
    if y1 >= h:
        return None
    s = set(cells)
    bg = bg_of(inp)
    col = Counter(inp[y][x] for y, x in cells).most_common(1)[0][0]
    return [[col if (y, x) in s else bg for x in range(x0, x1 + 1)] for y in range(y0, y1 + 1)]


def smallest_component(inp, out):
    return crop_cells(inp, min(components(inp, D8), key=len))


def margin_one(inp, out):
    return crop_cells(inp, true_shape(inp), margin=1)


def drop_last_row(inp, out):
    return [r[:] for r in out[:-1]]


def drop_first_col(inp, out):
    return [r[1:] for r in out]


def filled_box(inp, out):
    return crop_cells(inp, true_shape(inp), fill_all=True)


def inverted(inp, out):
    bg = bg_of(inp)
    col = next(c for r in out for c in r if c != bg)
    return [[bg if c != bg else col for c in r] for r in out]


def rotated(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def mirrored(inp, out):
    return [r[::-1] for r in out]


def commonest_color_all_cells(inp, out):
    bg = bg_of(inp)
    cnt = Counter(c for r in inp for c in r if c != bg)
    col = max(cnt, key=lambda c: (cnt[c], c))
    cells = [(y, x) for y, r in enumerate(inp) for x, c in enumerate(r) if c == col]
    return crop_cells(inp, cells)


ALTERNATIVES = [
    ("crop the shape's box plus a one-cell margin, keeping all input cells in it", keep_all_colors),
    ("take the second largest ink group instead of the largest", second_largest),
    ("pick the smallest ink group instead of the largest", smallest_component),
    ("box one cell larger on every side, padded with background", margin_one),
    ("box one row short at the bottom", drop_last_row),
    ("box one column short at the left", drop_first_col),
    ("box offset one row down", shifted_box),
    ("fill the whole box with the shape color", filled_box),
    ("swap shape cells and background cells", inverted),
    ("output rotated a quarter turn", rotated),
    ("output mirrored left to right", mirrored),
    ("crop around all cells of the commonest ink color", commonest_color_all_cells),
]


def valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/1f85a75f.json'))
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
