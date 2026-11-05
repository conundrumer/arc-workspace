import json
from pathlib import Path


def cells(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def blank(inp):
    return [[0] * len(inp[0]) for _ in inp]


def moved(inp, dr, dc, color, keep_old=False, clip=True):
    g = blank(inp)
    h, w = len(inp), len(inp[0])
    if keep_old:
        for r, c, v in cells(inp):
            g[r][c] = v
    for r, c, v in cells(inp):
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w:
            g[nr][nc] = color if color is not None else v
    return g


def up(inp, out):
    return moved(inp, -1, 0, 2)


def down2(inp, out):
    return moved(inp, 2, 0, 2)


def left(inp, out):
    return moved(inp, 0, -1, 2)


def right(inp, out):
    return moved(inp, 0, 1, 2)


def diag(inp, out):
    return moved(inp, 1, 1, 2)


def keep_color(inp, out):
    return moved(inp, 1, 0, None)


def in_place(inp, out):
    return moved(inp, 0, 0, 2)


def copy_not_move(inp, out):
    return moved(inp, 1, 0, 2, keep_old=True)


def shift_by_height(inp, out):
    cs = cells(inp)
    h = max(r for r, _, _ in cs) - min(r for r, _, _ in cs) + 1
    g = moved(inp, h, 0, 2)
    return g if g != out else None


def to_bottom(inp, out):
    cs = cells(inp)
    d = len(inp) - 1 - max(r for r, _, _ in cs)
    return moved(inp, d, 0, 2)


def top_row_only(inp, out):
    cs = cells(inp)
    top = min(r for r, _, _ in cs)
    g = blank(inp)
    for r, c, v in cs:
        if r == top:
            g[r + 1][c] = 2
    return g if g != out else None


def crop_shifted(inp, out):
    cs = cells(inp)
    h = max(r for r, _, _ in cs) - min(r for r, _, _ in cs) + 1
    w = max(c for _, c, _ in cs) - min(c for _, c, _ in cs) + 1
    return [[2] * w for _ in range(h)]


def background_recolor(inp, out):
    # swap roles: background becomes 2 where the object was, object cells stay 8 moved down
    g = moved(inp, 1, 0, 2)
    for r, c, v in cells(inp):
        if g[r][c] == 0:
            g[r][c] = 8
    return g


ALTERNATIVES = [
    ("object shifts up by 1 instead of down", up),
    ("object shifts down by 2 instead of 1", down2),
    ("object shifts left by 1 instead of down", left),
    ("object shifts right by 1 instead of down", right),
    ("object shifts diagonally down-right by 1", diag),
    ("object shifts down by 1 but keeps its input color", keep_color),
    ("object recolored to 2 but not shifted", in_place),
    ("object is copied down by 1, original left in place", copy_not_move),
    ("object shifts down by its own height", shift_by_height),
    ("object falls to the bottom edge", to_bottom),
    ("only the top row of the object is shifted and recolored", top_row_only),
    ("output is the object's bounding box cropped, filled with 2", crop_shifted),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/a79310a0.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
