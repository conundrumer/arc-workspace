import json
from pathlib import Path


def hflip(g):
    return [r[::-1] for r in g]


def vflip(g):
    return [list(r) for r in g[::-1]]


def transpose(g):
    return [list(c) for c in zip(*g)]


def cat_h(a, b):
    return [list(x) + list(y) for x, y in zip(a, b)]


def repeat(inp, out):
    return cat_h(inp, inp)


def mirror_left(inp, out):
    return cat_h(hflip(inp), inp)


def stack_vertical(inp, out):
    return [list(r) for r in inp] + vflip(inp)


def vflip_right(inp, out):
    return cat_h(inp, vflip(inp))


def shared_column(inp, out):
    return [list(r) + list(r[::-1][1:]) for r in inp]


def transpose_right(inp, out):
    return cat_h(inp, transpose(inp))


def crop_last_column(inp, out):
    return [list(r[:-1]) for r in out]


def invert_right(inp, out):
    fg = max(v for r in inp for v in r)
    right = [[fg if v == 0 else 0 for v in r] for r in hflip(inp)]
    return cat_h(inp, right)


def roll_right(inp, out):
    right = [r[1:] + r[:1] for r in hflip(inp)]
    return cat_h(inp, right)


def quad(inp, out):
    top = cat_h(inp, hflip(inp))
    return top + vflip(top)


def symmetrize(inp, out):
    f = hflip(inp)
    u = [[a | b for a, b in zip(r, s)] for r, s in zip(inp, f)]
    return cat_h(u, u)


def unchanged(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("copy the input to the right half instead of mirroring it", repeat),
    ("mirror goes on the left, input on the right", mirror_left),
    ("flip is appended below, vertically, giving a 6x3 grid", stack_vertical),
    ("right half is the input flipped top to bottom instead of left to right", vflip_right),
    ("mirrored copy shares the boundary column (width 5)", shared_column),
    ("right half is the transpose of the input", transpose_right),
    ("output is cropped one column short (width 5)", crop_last_column),
    ("right half is the mirror with foreground and background swapped", invert_right),
    ("right half is the mirror cyclically shifted by one column", roll_right),
    ("output is tiled both ways with flips, 6x6", quad),
    ("both halves are the union of the input and its mirror", symmetrize),
    ("input returned unchanged", unchanged),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/c9e6f938.json').read_text())
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
