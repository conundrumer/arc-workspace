"""Near-miss readings for ARC task 007bbfb7 (3x3 input -> 9x9 fractal tiling)."""
import json
from pathlib import Path

BG = 0


def _build(inp, block_fn, keep_fn):
    n = len(inp)
    m = len(inp[0])
    out = [[BG] * (n * m) for _ in range(n * m)]
    for i in range(n):
        for j in range(m):
            if keep_fn(inp, i, j):
                blk = block_fn(inp, i, j)
                for a in range(n):
                    for b in range(m):
                        out[i * n + a][j * m + b] = blk[a][b]
    return out


def _nonbg(inp, i, j):
    return inp[i][j] != BG


def _same(inp, i, j):
    return inp


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _color(inp):
    return next(v for r in inp for v in r if v != BG)


def inverted_mask(inp, out):
    return _build(inp, _same, lambda g, i, j: g[i][j] == BG)


def tile_everywhere(inp, out):
    return _build(inp, _same, lambda g, i, j: True)


def transposed_mask(inp, out):
    return _build(inp, _same, lambda g, i, j: g[j][i] != BG)


def transposed_block(inp, out):
    return _build(inp, lambda g, i, j: _transpose(g), _nonbg)


def mirrored_block(inp, out):
    return _build(inp, lambda g, i, j: [r[::-1] for r in g], _nonbg)


def flipped_block_vertical(inp, out):
    return _build(inp, lambda g, i, j: g[::-1], _nonbg)


def solid_blocks(inp, out):
    n, m = len(inp), len(inp[0])
    return _build(inp, lambda g, i, j: [[g[i][j]] * m for _ in range(n)], _nonbg)


def inverted_pattern(inp, out):
    c = _color(inp)
    return _build(inp, lambda g, i, j: [[c if v == BG else BG for v in r] for r in g], _nonbg)


def row_filled(inp, out):
    return _build(inp, _same, lambda g, i, j: any(v != BG for v in g[i]))


def first_block_unfilled(inp, out):
    g = [r[:] for r in out]
    n, m = len(inp), len(inp[0])
    for i in range(n):
        for j in range(m):
            if inp[i][j] != BG:
                for a in range(n):
                    for b in range(m):
                        g[i * n + a][j * m + b] = BG
                return g
    return None


def crop_one_short(inp, out):
    return [r[:-1] for r in out[:-1]]


def rotated_block(inp, out):
    return _build(inp, lambda g, i, j: [list(r) for r in zip(*g[::-1])], _nonbg)


ALTERNATIVES = [
    ("blocks placed where the input cell is background instead of non-background", inverted_mask),
    ("input copied into every block, no mask", tile_everywhere),
    ("block mask read from the transposed input", transposed_mask),
    ("blocks hold the transposed input", transposed_block),
    ("blocks hold the horizontally mirrored input", mirrored_block),
    ("blocks hold the vertically flipped input", flipped_block_vertical),
    ("blocks are solid color of their mask cell instead of the input pattern", solid_blocks),
    ("blocks hold the inverted pattern (color where input is background)", inverted_pattern),
    ("whole block-row filled when the row has any non-background cell", row_filled),
    ("true output with the first filled block left empty", first_block_unfilled),
    ("true output cropped by one row and one column", crop_one_short),
    ("blocks hold the input rotated 90 degrees", rotated_block),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/007bbfb7.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {fn.__name__}: {desc}")
