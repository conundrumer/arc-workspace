from pathlib import Path
import json
from collections import Counter

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/1e5d6875.json')


def bg_of(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def painted(inp, out):
    """Cells where the true output differs from the input: {(r, c): color}."""
    return {(r, c): out[r][c]
            for r in range(len(inp)) for c in range(len(inp[0]))
            if out[r][c] != inp[r][c]}


def render(inp, cells):
    """Input with the given painted cells laid on background cells only."""
    bg = bg_of(inp)
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for (r, c), col in cells.items():
        if 0 <= r < h and 0 <= c < w and inp[r][c] == bg:
            g[r][c] = col
    return g


def drop_color(color):
    def f(inp, out):
        p = painted(inp, out)
        return render(inp, {k: v for k, v in p.items() if v != color})
    return f


def drop_minority(inp, out):
    p = painted(inp, out)
    cnt = Counter(p.values())
    if len(cnt) < 2:
        return None
    least = min(cnt, key=lambda k: (cnt[k], k))
    return render(inp, {k: v for k, v in p.items() if v != least})


def drop_majority(inp, out):
    p = painted(inp, out)
    cnt = Counter(p.values())
    if len(cnt) < 2:
        return None
    most = max(cnt, key=lambda k: (cnt[k], k))
    return render(inp, {k: v for k, v in p.items() if v != most})


def swap_marks(inp, out):
    p = painted(inp, out)
    cols = sorted(set(p.values()))
    if len(cols) != 2:
        return None
    a, b = cols
    return render(inp, {k: (b if v == a else a) for k, v in p.items()})


def one_color(inp, out):
    p = painted(inp, out)
    return render(inp, {k: 4 for k in p})


def piece_color(inp, out):
    bg = bg_of(inp)
    cols = sorted(set(c for r in inp for c in r if c != bg))
    if not cols:
        return None
    p = painted(inp, out)
    return render(inp, {k: cols[0] for k in p})


def flip_lr(inp, out):
    w = len(inp[0])
    p = painted(inp, out)
    return render(inp, {(r, w - 1 - c): v for (r, c), v in p.items()})


def rot180(inp, out):
    h, w = len(inp), len(inp[0])
    p = painted(inp, out)
    return render(inp, {(h - 1 - r, w - 1 - c): v for (r, c), v in p.items()})


def transpose_layer(inp, out):
    if len(inp) != len(inp[0]):
        return None
    p = painted(inp, out)
    return render(inp, {(c, r): v for (r, c), v in p.items()})


def shift_down(inp, out):
    p = painted(inp, out)
    return render(inp, {(r + 1, c): v for (r, c), v in p.items()})


def clip_border(inp, out):
    h, w = len(inp), len(inp[0])
    p = painted(inp, out)
    return render(inp, {(r, c): v for (r, c), v in p.items()
                        if 0 < r < h - 1 and 0 < c < w - 1})


def crop_nonbg(inp, out):
    bg = bg_of(inp)
    cells = [(r, c) for r in range(len(out)) for c in range(len(out[0]))
             if out[r][c] != bg]
    if not cells:
        return None
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return [row[c0:c1 + 1] for row in out[r0:r1 + 1]]


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("only the lower-count marker color is left out of the copies", drop_minority),
    ("only the higher-count marker color is left out of the copies", drop_majority),
    ("marker colors 4 and 3 are exchanged", swap_marks),
    ("every copy cell gets one marker color, 4", one_color),
    ("copies take the piece color instead of the marker color", piece_color),
    ("copies land mirrored left to right", flip_lr),
    ("copies land rotated 180 degrees about the grid center", rot180),
    ("copies land transposed across the main diagonal", transpose_layer),
    ("copies land one row too low", shift_down),
    ("copy cells on the grid border are dropped", clip_border),
    ("output is cropped to the bounding box of the non-background cells", crop_nonbg),
    ("no copies are painted; input is returned", unchanged),
]


def valid(g):
    return (isinstance(g, list) and len(g) > 0
            and all(isinstance(r, list) for r in g)
            and len(set(len(r) for r in g)) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    train = json.load(open(TASK))["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in train:
            g = fn(pr["input"], pr["output"])
            if g is not None and valid(g) and g != pr["output"]:
                n += 1
        print(n, desc)
