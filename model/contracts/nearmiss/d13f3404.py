import json
from pathlib import Path


def seeds(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def rays(inp, size, dr, dc, start=0, length=None, keep_seed=True, color=None):
    g = [[0] * size for _ in range(size)]
    for r, c, v in seeds(inp):
        col = v if color is None else color
        k = start
        while length is None or k < start + length:
            rr, cc = r + dr * k, c + dc * k
            if not (0 <= rr < size and 0 <= cc < size):
                break
            if k > 0 or keep_seed:
                g[rr][cc] = col
            k += 1
    return g


def crop_out(inp, out):
    return [row[:5] for row in out[:5]]


def anti_diagonal(inp, out):
    return rays(inp, 6, 1, -1)


def up_right(inp, out):
    return rays(inp, 6, -1, 1)


def horizontal(inp, out):
    return rays(inp, 6, 0, 1)


def both_directions(inp, out):
    g = rays(inp, 6, 1, 1)
    h = rays(inp, 6, 1, -1)
    return [[a or b for a, b in zip(r1, r2)] for r1, r2 in zip(g, h)]


def single_step(inp, out):
    return rays(inp, 6, 1, 1, length=2)


def seed_erased(inp, out):
    return rays(inp, 6, 1, 1, keep_seed=False)


def size_seven(inp, out):
    return rays(inp, 7, 1, 1)


def first_seed_color(inp, out):
    s = seeds(inp)
    return rays(inp, 6, 1, 1, color=s[0][2])


def tiled(inp, out):
    return [[inp[r % 3][c % 3] for c in range(6)] for r in range(6)]


def shift_one_row(inp, out):
    return [[0] * 6] + [list(r) for r in out[:5]]


ALTERNATIVES = [
    ("output is the 3x3 input unchanged", lambda inp, out: [list(r) for r in inp]),
    ("output cropped to 5x5 (off-by-one size)", crop_out),
    ("rays go down-left instead of down-right", anti_diagonal),
    ("rays go up-right instead of down-right", up_right),
    ("rays go right horizontally instead of diagonally", horizontal),
    ("rays go both down-right and down-left", both_directions),
    ("rays are one step long", single_step),
    ("original seed cells are erased, only rays remain", seed_erased),
    ("output is 7x7 instead of 6x6", size_seven),
    ("all rays use the color of the first seed", first_seed_color),
    ("input is tiled 2x2 instead of drawing rays", tiled),
    ("true output shifted down by one row", shift_one_row),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/d13f3404.json").read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
