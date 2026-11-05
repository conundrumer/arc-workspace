import json
from collections import Counter
from pathlib import Path


def _counts(inp):
    return Counter(v for row in inp for v in row)


def _place(inp, cells, tile=None, bg=0):
    n = len(inp)
    tile = tile if tile is not None else inp
    out = [[bg] * (n * n) for _ in range(n * n)]
    for (r, c) in cells:
        for i in range(n):
            for j in range(n):
                out[r * n + i][c * n + j] = tile[i][j]
    return out


def _cells(inp, pred):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if pred(v)]


def _rarest_cells(inp):
    cnt = _counts(inp)
    m = min(cnt.values())
    return _cells(inp, lambda v: cnt[v] == m)


def most_common_active(inp, out):
    cnt = _counts(inp)
    m = max(cnt.values())
    return _place(inp, _cells(inp, lambda v: cnt[v] == m))


def inverse_active(inp, out):
    act = set(_rarest_cells(inp))
    n = len(inp)
    return _place(inp, [(r, c) for r in range(n) for c in range(n) if (r, c) not in act])


def full_tiling(inp, out):
    n = len(inp)
    return _place(inp, [(r, c) for r in range(n) for c in range(n)])


def transposed_positions(inp, out):
    return _place(inp, [(c, r) for r, c in _rarest_cells(inp)])


def mirrored_tile(inp, out):
    return _place(inp, _rarest_cells(inp), tile=[row[::-1] for row in inp])


def second_rarest(inp, out):
    cnt = _counts(inp)
    vals = sorted(set(cnt.values()))
    if len(vals) < 2:
        return None
    m = vals[1]
    return _place(inp, _cells(inp, lambda v: cnt[v] == m))


def first_only(inp, out):
    cells = _rarest_cells(inp)
    return _place(inp, cells[:1])


def wrong_background(inp, out):
    cnt = _counts(inp)
    bg = cnt.most_common(1)[0][0]
    return [[bg if v == 0 else v for v in row] for row in out]


def non_majority_active(inp, out):
    cnt = _counts(inp)
    top = max(cnt.values())
    maj = [v for v in cnt if cnt[v] == top][0]
    return _place(inp, _cells(inp, lambda v: v != maj))


def rarest_color_only_tile(inp, out):
    cnt = _counts(inp)
    m = min(cnt.values())
    tile = [[v if cnt[v] == m else 0 for v in row] for row in inp]
    return _place(inp, _rarest_cells(inp), tile=tile)


def rotated_tile(inp, out):
    n = len(inp)
    tile = [[inp[n - 1 - j][i] for j in range(n)] for i in range(n)]
    return _place(inp, _rarest_cells(inp), tile=tile)


def cropped_output(inp, out):
    return [row[:-1] for row in out[:-1]]


ALTERNATIVES = [
    ("active blocks are the cells of the most common color, not the rarest", most_common_active),
    ("tile fills every block except the rarest-color positions", inverse_active),
    ("tile fills every block, no condition on position", full_tiling),
    ("block positions transposed (row and column swapped)", transposed_positions),
    ("tile copies are mirrored left to right", mirrored_tile),
    ("active blocks are the cells of the second rarest color", second_rarest),
    ("only the first rarest-color cell gets a tile copy", first_only),
    ("background filled with the most common input color instead of 0", wrong_background),
    ("every cell not of the majority color is active", non_majority_active),
    ("tile copies keep only the rarest color, other cells 0", rarest_color_only_tile),
    ("tile copies are rotated a quarter turn", rotated_tile),
    ("output cropped one row and one column short (8x8)", cropped_output),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/48f8583b.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(ok, desc)
