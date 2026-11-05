import json
from collections import Counter
from pathlib import Path


def tiles(inp):
    return [[list(r) for r in inp[i:i + 3]] for i in range(0, len(inp), 3)]


def transpose(g):
    return [list(r) for r in zip(*g)]


def d4(g):
    t = transpose(g)
    return [
        [r[::-1] for r in g],
        g[::-1],
        [r[::-1] for r in g[::-1]],
        t,
        [r[::-1] for r in t],
        t[::-1],
        [r[::-1] for r in t[::-1]],
    ]


def has_sym(g):
    return any(h == g for h in d4(g))


def odd_index(inp, out):
    ts = tiles(inp)
    return ts.index(out) if out in ts else 0


def next_tile(inp, out):
    ts = tiles(inp)
    return ts[(odd_index(inp, out) + 1) % len(ts)]


def prev_tile(inp, out):
    ts = tiles(inp)
    return ts[(odd_index(inp, out) - 1) % len(ts)]


def first_symmetric_tile(inp, out):
    for t in tiles(inp):
        if has_sym(t):
            return t
    return None


def transposed_out(inp, out):
    return transpose(out)


def mirrored_out(inp, out):
    return [r[::-1] for r in out]


def flipped_out(inp, out):
    return out[::-1]


def rotated_out(inp, out):
    return [r[::-1] for r in out[::-1]]


def swapped_colors(inp, out):
    cs = sorted({c for r in out for c in r})
    if len(cs) != 2:
        return None
    a, b = cs
    return [[b if c == a else a for c in r] for r in out]


def cropped_out(inp, out):
    return [r[:2] for r in out[:2]]


def cellwise_vote(inp, out):
    ts = tiles(inp)
    return [
        [Counter(t[i][j] for t in ts).most_common(1)[0][0] for j in range(3)]
        for i in range(3)
    ]


def odd_tile_first(inp, out):
    ts = tiles(inp)
    k = odd_index(inp, out)
    order = [ts[k]] + [t for i, t in enumerate(ts) if i != k]
    return [r for t in order for r in t]


def odd_tile_twice(inp, out):
    return out + out


def unchanged(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("outputs the tile after the odd one (cyclic order) instead of the odd tile", next_tile),
    ("outputs the tile before the odd one (cyclic order) instead of the odd tile", prev_tile),
    ("outputs the first tile that has a D4 symmetry, the opposite of the odd-tile test", first_symmetric_tile),
    ("outputs the odd tile transposed", transposed_out),
    ("outputs the odd tile mirrored left to right", mirrored_out),
    ("outputs the odd tile flipped top to bottom", flipped_out),
    ("outputs the odd tile rotated 180 degrees", rotated_out),
    ("outputs the odd tile with its two colors swapped", swapped_colors),
    ("outputs the top-left 2x2 crop of the odd tile (off-by-one size)", cropped_out),
    ("outputs the cell-wise majority vote of all tiles", cellwise_vote),
    ("outputs all tiles with the odd tile moved to the top (no selection)", odd_tile_first),
    ("outputs the odd tile stacked twice (wrong count)", odd_tile_twice),
]


def valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/662c240a.json").read_text())
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
