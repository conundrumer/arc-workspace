import json
from collections import Counter
from pathlib import Path


def _info(inp):
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    cols = [c for c in cnt if c != bg]
    H, W = len(inp), len(inp[0])

    def blocks2(c):
        return sum(1 for i in range(H - 1) for j in range(W - 1)
                   if inp[i][j] == inp[i + 1][j] == inp[i][j + 1] == inp[i + 1][j + 1] == c)

    fig = max(cols, key=blocks2)
    others = [c for c in cols if c != fig]
    speck = others[0] if others else None
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == fig]
    r0 = min(i for i, _ in cells)
    r1 = max(i for i, _ in cells)
    c0 = min(j for _, j in cells)
    c1 = max(j for _, j in cells)
    return bg, fig, speck, (r0, r1, c0, c1)


def _blocks(inp, n, box, bg, mark, empty, pred):
    """n x n grid of blocks over box; a block is marked when pred(block cells) holds."""
    r0, r1, c0, c1 = box
    h, w = r1 - r0 + 1, c1 - c0 + 1
    sh, sw = h / n, w / n
    res = []
    for a in range(n):
        row = []
        for b in range(n):
            ra, rb = r0 + round(a * sh), r0 + round((a + 1) * sh)
            ca, cb = c0 + round(b * sw), c0 + round((b + 1) * sw)
            cells = [inp[i][j] for i in range(ra, rb) for j in range(ca, cb)]
            row.append(mark if pred(cells) else empty)
        res.append(row)
    return res


def fig_as_fig_color(inp, out):
    # Filled cells take the figure color instead of the speck color.
    bg, fig, speck, _ = _info(inp)
    return [[fig if v == speck else v for v in r] for r in out]


def inverted(inp, out):
    # Filled and blank swapped.
    bg, fig, speck, _ = _info(inp)
    return [[bg if v == speck else speck for v in r] for r in out]


def colors_swapped(inp, out):
    # Figure color for filled cells, speck color for blank cells.
    bg, fig, speck, _ = _info(inp)
    return [[fig if v == speck else speck for v in r] for r in out]


def raw_crop(inp, out):
    # Crop to the figure box but do not shrink the pixels.
    bg, fig, speck, (r0, r1, c0, c1) = _info(inp)
    return [[speck if inp[i][j] == fig else bg for j in range(c0, c1 + 1)]
            for i in range(r0, r1 + 1)]


def pixel_one_smaller(inp, out):
    # Pixel size taken one cell too small, so the output has too many cells.
    bg, fig, speck, (r0, r1, c0, c1) = _info(inp)
    n = len(out)
    s = (r1 - r0 + 1) // n - 1
    if s < 1:
        return None
    rows = list(range(r0, r1 + 1, s))
    cols = list(range(c0, c1 + 1, s))
    return [[speck if inp[i][j] == fig else bg for j in cols] for i in rows]


def box_with_specks(inp, out):
    # Box taken over all ink, so stray specks stretch the box.
    bg, fig, speck, _ = _info(inp)
    ink = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v != bg]
    box = (min(i for i, _ in ink), max(i for i, _ in ink),
           min(j for _, j in ink), max(j for _, j in ink))
    return _blocks(inp, len(out), box, bg, speck, bg, lambda cs: fig in cs)


def transposed(inp, out):
    # Output read column-wise instead of row-wise.
    return [list(r) for r in zip(*out)]


def flipped_vertical(inp, out):
    # Output upside down.
    return [list(r) for r in reversed(out)]


def any_ink_fills(inp, out):
    # A block is filled when it holds any non-background cell, specks included.
    bg, fig, speck, box = _info(inp)
    return _blocks(inp, len(out), box, bg, speck, bg, lambda cs: any(v != bg for v in cs))


def box_shifted(inp, out):
    # Sampling one block too far down and right, from the next block's corner.
    bg, fig, speck, (r0, r1, c0, c1) = _info(inp)
    n = len(out)
    sh, sw = (r1 - r0 + 1) // n, (c1 - c0 + 1) // n
    res = []
    for a in range(n):
        row = []
        for b in range(n):
            i, j = r0 + (a + 1) * sh, c0 + (b + 1) * sw
            if i >= len(inp) or j >= len(inp[0]):
                return None
            row.append(speck if inp[i][j] == fig else bg)
        res.append(row)
    return res


def speck_box(inp, out):
    # Figure taken to be the speck color: its box over the whole picture, shrunk to the output size.
    bg, fig, speck, _ = _info(inp)
    if speck is None:
        return None
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == speck]
    box = (min(i for i, _ in cells), max(i for i, _ in cells),
           min(j for _, j in cells), max(j for _, j in cells))
    return _blocks(inp, len(out), box, bg, speck, bg, lambda cs: speck in cs)


ALTERNATIVES = [
    ("filled cells use the figure color instead of the speck color", fig_as_fig_color),
    ("filled and blank cells swapped", inverted),
    ("figure color for filled cells and speck color for blank cells", colors_swapped),
    ("figure box cropped without shrinking the pixels", raw_crop),
    ("pixel size one cell too small, giving too many cells", pixel_one_smaller),
    ("box taken over all ink so specks stretch it", box_with_specks),
    ("output transposed", transposed),
    ("output flipped top to bottom", flipped_vertical),
    ("a block is filled by any non-background cell, specks included", any_ink_fills),
    ("cells sampled one block too far down and right", box_shifted),
    ("speck color taken as the figure, box over the specks", speck_box),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/5ad4f10b.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
