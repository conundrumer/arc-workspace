import json
from pathlib import Path

INK = 8


def parse(inp):
    h, w = len(inp), len(inp[0])
    bar_cols = [c for c in range(w)
                if len({inp[r][c] for r in range(h)}) == 1 and inp[0][c] not in (0, INK)]
    colors = [inp[0][c] for c in bar_cols]
    # shapes: maximal runs of neighboring columns that agree and hold ink
    bands = []
    c = 0
    while c < w:
        col = [inp[r][c] for r in range(h)]
        if INK in col and c not in bar_cols:
            d = c
            while d + 1 < w and [inp[r][d + 1] for r in range(h)] == col:
                d += 1
            bands.append((c, d))
            c = d + 1
        else:
            c += 1
    return h, w, bar_cols, colors, bands


def paint(inp, assign, keep_bars=False):
    h, w, bar_cols, colors, bands = parse(inp)
    g = [[0] * w for _ in range(h)]
    if keep_bars:
        for r in range(h):
            for c in bar_cols:
                g[r][c] = inp[r][c]
    for (a, b), col in assign:
        for r in range(h):
            for c in range(a, b + 1):
                if inp[r][c] == INK:
                    g[r][c] = col
    return g


def rule(inp, order=None, cols=None):
    h, w, bar_cols, colors, bands = parse(inp)
    if order is None:
        order = list(range(len(bands)))
    if cols is None:
        cols = colors
    return [(bands[i], cols[k]) for k, i in enumerate(order)]


def keep_bars(inp, out):
    return paint(inp, rule(inp), keep_bars=True)


def reversed_colors(inp, out):
    _, _, _, colors, _ = parse(inp)
    return paint(inp, rule(inp, cols=colors[::-1]))


def shapes_stay_ink(inp, out):
    h, w, bar_cols, colors, bands = parse(inp)
    return [[INK if v == INK else 0 for v in row] for row in inp]


def all_first(inp, out):
    _, _, _, colors, bands = parse(inp)
    return paint(inp, [(b, colors[0]) for b in bands])


def all_last(inp, out):
    _, _, _, colors, bands = parse(inp)
    return paint(inp, [(b, colors[-1]) for b in bands])


def cyclic_shift(inp, out):
    _, _, _, colors, bands = parse(inp)
    n = len(colors)
    return paint(inp, [(b, colors[(i + 1) % n]) for i, b in enumerate(bands)])


def top_row_order(inp, out):
    h, w, bar_cols, colors, bands = parse(inp)

    def top(b):
        return min(r for r in range(h) for c in range(b[0], b[1] + 1) if inp[r][c] == INK)
    order = sorted(range(len(bands)), key=lambda i: (top(bands[i]), bands[i][0]))
    # order[k] = shape that gets the k-th bar color
    return paint(inp, rule(inp, order=order))


def components(inp, out):
    h, w, bar_cols, colors, bands = parse(inp)
    seen = set()
    comps = []
    for c in range(w):
        for r in range(h):
            if inp[r][c] == INK and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == INK and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                comps.append(cells)
    g = [[0] * w for _ in range(h)]
    for k, cells in enumerate(comps):
        for y, x in cells:
            g[y][x] = colors[min(k, len(colors) - 1)]
    return g


def crop_bars(inp, out):
    h, w, bar_cols, colors, bands = parse(inp)
    left = max(bar_cols) + 1
    return [row[left:] for row in out]


def only_first_shape(inp, out):
    _, _, _, colors, bands = parse(inp)
    return paint(inp, [(bands[0], colors[0])])


ALTERNATIVES = [
    ("bars are left in place while the shapes are recolored", keep_bars),
    ("bar colors are assigned to the shapes from right to left", reversed_colors),
    ("bars are erased but the shapes keep the ink color", shapes_stay_ink),
    ("every shape takes the first bar's color", all_first),
    ("every shape takes the last bar's color", all_last),
    ("each shape takes the color of the next bar, wrapping around", cyclic_shift),
    ("shapes are ranked top to bottom by their top row instead of left to right", top_row_order),
    ("shapes are 4-connected ink components, so touching columns merge", components),
    ("the bar columns are cropped away from the correct output", crop_bars),
    ("only the leftmost shape is recolored and the others are erased", only_first_shape),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/9b365c51.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
