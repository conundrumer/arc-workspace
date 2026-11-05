import json
from pathlib import Path


def hflip(g):
    return [r[::-1] for r in g]


def vflip(g):
    return [r[:] for r in g[::-1]]


def rot180(g):
    return [r[::-1] for r in g[::-1]]


def transpose(g):
    return [list(c) for c in zip(*g)]


def hcat(*gs):
    return [sum((g[i] for g in gs), []) for i in range(len(gs[0]))]


def vcat(*gs):
    return [r[:] for g in gs for r in g]


def same_tiles(inp, out):
    return [r[:] for r in inp]


def alt_no_flip(inp, out):
    return hcat(inp, inp, inp, inp)


def alt_phase(inp, out):
    return hcat(inp, hflip(inp), inp, hflip(inp))


def alt_two_tiles(inp, out):
    return hcat(hflip(inp), inp)


def alt_three_tiles(inp, out):
    return hcat(hflip(inp), inp, hflip(inp))


def alt_vflip(inp, out):
    v = vflip(inp)
    return hcat(v, inp, v, inp)


def alt_rot180(inp, out):
    r = rot180(inp)
    return hcat(r, inp, r, inp)


def alt_transpose(inp, out):
    t = transpose(inp)
    return hcat(t, inp, t, inp)


def alt_stack_vertical(inp, out):
    f = hflip(inp)
    return vcat(f, inp, f, inp)


def alt_anchor_only(inp, out):
    return hcat(hflip(inp), inp, inp, inp)


def alt_last_flipped(inp, out):
    f = hflip(inp)
    return hcat(f, inp, f, f)


def alt_square_2x2(inp, out):
    f = hflip(inp)
    row = hcat(f, inp)
    return vcat(row, row)


def alt_output_vflipped(inp, out):
    return vflip(out)


ALTERNATIVES = [
    ("input tiled four times with no mirroring", alt_no_flip),
    ("mirror phase swapped: input first, then mirrored, alternating", alt_phase),
    ("only two tiles: mirrored input then input", alt_two_tiles),
    ("three tiles instead of four", alt_three_tiles),
    ("tiles mirrored top-to-bottom instead of left-to-right", alt_vflip),
    ("tiles rotated 180 degrees instead of mirrored", alt_rot180),
    ("tiles transposed instead of mirrored", alt_transpose),
    ("same four tiles stacked vertically instead of side by side", alt_stack_vertical),
    ("only the first tile mirrored, the rest copies of the input", alt_anchor_only),
    ("last tile mirrored too, so two mirrored tiles are adjacent at the end", alt_last_flipped),
    ("2x2 tiling of the mirrored and plain pair", alt_square_2x2),
    ("correct output flipped top-to-bottom", alt_output_vflipped),
]


def valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/59341089.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
