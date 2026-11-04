from pathlib import Path
import json

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/eb281b96.json')


def zigzag(inp, n, start_flipped=False, dup=False):
    """Stack n tiles vertically, alternating plain and reversed.
    Adjacent tiles share their boundary row unless dup is True."""
    rows = []
    for k in range(n):
        tile = inp if (k % 2 == 0) != start_flipped else inp[::-1]
        if k > 0 and not dup:
            tile = tile[1:]
        rows += [list(r) for r in tile]
    return rows


def nz_color(g):
    for r in g:
        for v in r:
            if v:
                return v
    return 8


def plain_overlap(inp, out):
    h = len(inp)
    return [list(inp[r % (h - 1)]) for r in range(len(out))]


def plain_stack(inp, out):
    return [list(r) for _ in range(4) for r in inp]


def mirror_dup(inp, out):
    return zigzag(inp, 4, dup=True)


def two_tiles(inp, out):
    return zigzag(inp, 2)


def start_flipped(inp, out):
    return zigzag(inp, 4, start_flipped=True)


def horizontal_axis(inp, out):
    w = len(inp[0])
    return [[row[c] for c in zigzag_idx(w, 4)] for row in inp]


def zigzag_idx(w, n):
    idx = []
    for k in range(n):
        seq = list(range(w)) if k % 2 == 0 else list(range(w))[::-1]
        if k > 0:
            seq = seq[1:]
        idx += seq
    return idx


def wrong_color(inp, out):
    return [[5 if v else 0 for v in r] for r in out]


def odd_tiles_shifted(inp, out):
    h = len(inp)
    g = [list(r) for r in out]
    for t in range(1, 4, 2):
        for r in range(t * (h - 1), (t + 1) * (h - 1) + 1):
            if r < len(g):
                g[r] = g[r][1:] + g[r][:1]
    return g


def last_tile_unreflected(inp, out):
    h = len(inp)
    g = [list(r) for r in out]
    g[3 * (h - 1):] = [list(r) for r in inp]
    return g


def three_tiles(inp, out):
    return zigzag(inp, 3)


def five_tiles(inp, out):
    return zigzag(inp, 5)


def drop_last_row(inp, out):
    return [list(r) for r in out[:-1]]


def blank_second_tile(inp, out):
    h = len(inp)
    g = [list(r) for r in out]
    for r in range(h, 2 * (h - 1)):
        g[r] = [0] * len(g[r])
    return g


ALTERNATIVES = [
    ("tile the input with period h-1 and no reflection", plain_overlap),
    ("stack four plain copies of the input with no overlap", plain_stack),
    ("reflect alternate tiles but repeat the boundary row at each junction", mirror_dup),
    ("only two tiles, one reflection", two_tiles),
    ("zigzag starts with the reversed input", start_flipped),
    ("zigzag along the width instead of the height", horizontal_axis),
    ("true output recolored to color 5", wrong_color),
    ("odd tiles shifted one column left", odd_tiles_shifted),
    ("last tile is a plain copy instead of a reflection", last_tile_unreflected),
    ("three tiles instead of four", three_tiles),
    ("five tiles instead of four", five_tiles),
    ("true output with the last row cropped", drop_last_row),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    train = json.load(open(TASK))["train"]
    print("pairs", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
