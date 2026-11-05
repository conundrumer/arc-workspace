import json
from pathlib import Path


def _expand(inp, row_reps, col_reps):
    rows = []
    for r, rr in zip(inp, row_reps):
        line = []
        for v, cr in zip(r, col_reps):
            line += [v] * cr
        rows += [list(line) for _ in range(rr)]
    return rows


def _edges(n, k=2, which=(0, -1)):
    reps = [1] * n
    for w in which:
        reps[w] = k
    return reps


def cols_only(inp, out):
    return _expand(inp, [1] * len(inp), _edges(len(inp[0])))


def rows_only(inp, out):
    return _expand(inp, _edges(len(inp)), [1] * len(inp[0]))


def middle_doubled(inp, out):
    h, w = len(inp), len(inp[0])
    rr, cr = [1] * h, [1] * w
    for i in range(1, h - 1):
        rr[i] = 2
    for j in range(1, w - 1):
        cr[j] = 2
    return _expand(inp, rr, cr)


def first_only(inp, out):
    return _expand(inp, _edges(len(inp), 2, (0,)), _edges(len(inp[0]), 2, (0,)))


def last_only(inp, out):
    return _expand(inp, _edges(len(inp), 2, (-1,)), _edges(len(inp[0]), 2, (-1,)))


def triple_edges(inp, out):
    return _expand(inp, _edges(len(inp), 3), _edges(len(inp[0]), 3))


def upscale_all(inp, out):
    return _expand(inp, [2] * len(inp), [2] * len(inp[0]))


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def zero_border(inp, out):
    w = len(inp[0])
    return [[0] * (w + 2)] + [[0] + list(r) + [0] for r in inp] + [[0] * (w + 2)]


def corners_blank(inp, out):
    g = [list(r) for r in out]
    for i in (0, 1, len(g) - 2, len(g) - 1):
        for j in (0, 1, len(g[0]) - 2, len(g[0]) - 1):
            g[i][j] = 0
    return g


def edge_copy_shifted(inp, out):
    # duplicated line is the neighbour inside, not a copy of the edge line
    g = [list(r) for r in out]
    g[1] = list(out[2])
    g[-2] = list(out[-3])
    return g


def mirrored(inp, out):
    return [list(reversed(r)) for r in out]


ALTERNATIVES = [
    ("double only the edge columns, leave rows single", cols_only),
    ("double only the edge rows, leave columns single", rows_only),
    ("double the middle rows and columns instead of the edges", middle_doubled),
    ("double only the first row and column", first_only),
    ("double only the last row and column", last_only),
    ("repeat each edge line three times", triple_edges),
    ("double every row and column (2x upscale)", upscale_all),
    ("true output transposed (rows and columns swapped)", transposed),
    ("input framed with a one-cell border of 0", zero_border),
    ("edge-doubling done, but the four corner blocks left 0", corners_blank),
    ("second copy of each edge line taken from the neighbouring inner line", edge_copy_shifted),
    ("true output mirrored left to right", mirrored),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/e633a9e5.json"))
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
