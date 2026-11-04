from pathlib import Path
import json
from collections import Counter

N = 3


def counts(inp):
    return Counter(c for r in inp for c in r)


def most(inp):
    cn = counts(inp)
    m = max(cn.values())
    return min(c for c in cn if cn[c] == m)


def least(inp):
    cn = counts(inp)
    m = min(cn.values())
    return min(c for c in cn if cn[c] == m)


def second(inp):
    cn = counts(inp)
    order = sorted(cn, key=lambda c: (-cn[c], c))
    return order[1] if len(order) > 1 else order[0]


def build(inp, mask, tile=None, fill=0):
    n = len(inp)
    tile = tile or inp
    out = [[fill] * (n * n) for _ in range(n * n)]
    for i in range(n):
        for j in range(n):
            if mask(i, j):
                for a in range(n):
                    for b in range(n):
                        out[i * n + a][j * n + b] = tile[a][b]
    return out


def least_color(inp, out):
    k = least(inp)
    return build(inp, lambda i, j: inp[i][j] == k)


def inverted_mask(inp, out):
    k = most(inp)
    return build(inp, lambda i, j: inp[i][j] != k)


def transposed_mask(inp, out):
    k = most(inp)
    return build(inp, lambda i, j: inp[j][i] == k)


def solid_tiles(inp, out):
    k = most(inp)
    return build(inp, lambda i, j: inp[i][j] == k, tile=[[k] * 3 for _ in range(3)])


def full_tiling(inp, out):
    return build(inp, lambda i, j: True)


def fill_with_commonest(inp, out):
    k = most(inp)
    return build(inp, lambda i, j: inp[i][j] == k, fill=k)


def second_commonest(inp, out):
    k = second(inp)
    return build(inp, lambda i, j: inp[i][j] == k)


def mirrored_mask(inp, out):
    k = most(inp)
    return build(inp, lambda i, j: inp[i][N - 1 - j] == k)


def flipped_tiles(inp, out):
    k = most(inp)
    t = [r[::-1] for r in inp]
    return build(inp, lambda i, j: inp[i][j] == k, tile=t)


def crop_8(inp, out):
    return [r[:-1] for r in out[:-1]]


def corner_color(inp, out):
    k = inp[0][0]
    return build(inp, lambda i, j: inp[i][j] == k)


def unchanged(inp, out):
    return [r[:] for r in inp]


ALTERNATIVES = [
    ("mask uses the least common input color", least_color),
    ("tiles go where the cell is not the commonest color", inverted_mask),
    ("mask is read transposed (row and column swapped)", transposed_mask),
    ("tiles are solid blocks of the commonest color", solid_tiles),
    ("tile is placed at every cell, none left empty", full_tiling),
    ("empty area is filled with the commonest color, not 0", fill_with_commonest),
    ("mask uses the second most common color", second_commonest),
    ("mask is read mirrored left to right", mirrored_mask),
    ("each placed tile is mirrored left to right", flipped_tiles),
    ("output is cropped one cell short (8x8)", crop_8),
    ("mask uses the color of the top-left cell", corner_color),
    ("output is the input unchanged", unchanged),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/27f8ce4f.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for d, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, d)
