import json
from collections import Counter
from pathlib import Path


def parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    rows = [r for r in range(h) if all(v != bg for v in inp[r])]
    cols = [c for c in range(w) if all(inp[r][c] != bg for r in range(h))]
    if not rows or not cols:
        return None
    top = inp[rows[0]][cols[0]]
    hc = next(inp[rows[0]][c] for c in range(w) if c not in cols)
    vc = next(inp[r][cols[0]] for r in range(h) if r not in rows)
    return bg, rows, cols, top, hc, vc


def cross_cells(rows, cols):
    return [(r, c) for r in rows for c in cols]


def copy(g):
    return [list(r) for r in g]


def paint_cross(base, rows, cols, color):
    g = copy(base)
    for r, c in cross_cells(rows, cols):
        g[r][c] = color
    return g


def crossing_background(inp, out):
    bg, rows, cols, top, hc, vc = parse(inp)
    return paint_cross(out, rows, cols, bg)


def horizontal_on_top(inp, out):
    bg, rows, cols, top, hc, vc = parse(inp)
    return paint_cross(out, rows, cols, hc)


def vertical_on_top(inp, out):
    bg, rows, cols, top, hc, vc = parse(inp)
    return paint_cross(out, rows, cols, vc)


def unchanged(inp, out):
    return copy(inp)


def swap_band_colors(inp, out):
    bg, rows, cols, top, hc, vc = parse(inp)
    g = copy(out)
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if r in rows and c not in cols:
                g[r][c] = vc
            elif c in cols and r not in rows:
                g[r][c] = hc
    return g


def first_cell_only(inp, out):
    bg, rows, cols, top, hc, vc = parse(inp)
    g = copy(inp)
    g[rows[0]][cols[0]] = vc if top == hc else hc
    return g


def grown_crossing(inp, out):
    bg, rows, cols, top, hc, vc = parse(inp)
    under = vc if top == hc else hc
    g = copy(out)
    for r in range(rows[0] - 1, rows[-1] + 2):
        for c in range(cols[0] - 1, cols[-1] + 2):
            if 0 <= r < len(g) and 0 <= c < len(g[0]):
                g[r][c] = under
    return g


def top_band_recolored(inp, out):
    bg, rows, cols, top, hc, vc = parse(inp)
    under = vc if top == hc else hc
    g = copy(out)
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if inp[r][c] == top:
                g[r][c] = under
    return g


def crop_crossing(inp, out):
    bg, rows, cols, top, hc, vc = parse(inp)
    return [[out[r][c] for c in cols] for r in rows]


def remove_underneath(inp, out):
    bg, rows, cols, top, hc, vc = parse(inp)
    under_is_h = (top == vc)
    g = copy(out)
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if under_is_h and r in rows and c not in cols:
                g[r][c] = bg
            elif not under_is_h and c in cols and r not in rows:
                g[r][c] = bg
    return g


ALTERNATIVES = [
    ("crossing cells are painted background instead of the underneath band color", crossing_background),
    ("horizontal band is always taken as on top, so crossing gets the horizontal color", horizontal_on_top),
    ("vertical band is always taken as on top, so crossing gets the vertical color", vertical_on_top),
    ("no swap: output equals the input", unchanged),
    ("the two band colors are exchanged along the whole bands, not only at the crossing", swap_band_colors),
    ("only the first (top-left) crossing cell is swapped", first_cell_only),
    ("swap region is the crossing grown by one cell on every side", grown_crossing),
    ("the underneath band color is painted over the whole top band, not only the crossing", top_band_recolored),
    ("output is cropped to the crossing region only", crop_crossing),
    ("the underneath band is treated as occluded: its non-crossing cells become background", remove_underneath),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/ba97ae07.json'))
    train = task["train"]
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
