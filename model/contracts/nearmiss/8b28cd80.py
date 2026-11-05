import json
from pathlib import Path


def _center(inp):
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v:
                return r, c, v
    return None


def _color(out):
    return max(v for row in out for v in row)


def invert(inp, out):
    col = _color(out)
    return [[0 if v else col for v in row] for row in out]


def recolor(inp, out):
    col = _color(out)
    new = col % 9 + 1
    return [[new if v else 0 for v in row] for row in out]


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def flip_lr(inp, out):
    return [row[::-1] for row in out]


def flip_ud(inp, out):
    return [list(row) for row in out[::-1]]


def rot90(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def tile_input(inp, out):
    return [[inp[r % 3][c % 3] for c in range(9)] for r in range(9)]


def crop_8(inp, out):
    return [row[:-1] for row in out[:-1]]


def corner_rings(inp, out):
    r, c, col = _center(inp)
    br, bc = 3 * r, 3 * c
    return [[col if max(abs(y - br), abs(x - bc)) % 2 == 0 else 0
             for x in range(9)] for y in range(9)]


def few_rings(inp, out):
    r, c, col = _center(inp)
    br, bc = 3 * r + 1, 3 * c + 1
    return [[v if max(abs(y - br), abs(x - bc)) <= 2 else 0
             for x, v in enumerate(row)] for y, row in enumerate(out)]


def unchanged(inp, out):
    return [list(row) for row in inp]


ALTERNATIVES = [
    ("rings and background colors swapped", invert),
    ("rings drawn in a wrong color", recolor),
    ("output transposed (wrong orientation)", transpose),
    ("output mirrored left-right (wrong winding sense)", flip_lr),
    ("output mirrored top-bottom (wrong winding sense)", flip_ud),
    ("output rotated a quarter turn", rot90),
    ("input tiled 3x3 instead of spread with gaps", tile_input),
    ("output one row and one column too small", crop_8),
    ("concentric rings centered on the block corner, no seam", corner_rings),
    ("only the rings within two cells of the center kept", few_rings),
    ("input returned unchanged", unchanged),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/8b28cd80.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
