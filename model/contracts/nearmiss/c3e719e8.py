import json
from collections import Counter
from pathlib import Path


def _counts(inp):
    return Counter(c for r in inp for c in r)


def _build(inp, gate, tile=None, fill=0):
    n, m = len(inp), len(inp[0])
    tile = tile if tile is not None else inp
    out = [[fill] * (m * m) for _ in range(n * n)]
    for i in range(n):
        for j in range(m):
            if gate(i, j):
                for a in range(n):
                    for b in range(m):
                        out[i * n + a][j * m + b] = tile[a][b]
    return out


def _mode(inp):
    return _counts(inp).most_common(1)[0][0]


def least_common(inp, out):
    cnt = _counts(inp)
    lo = min(cnt.values())
    cols = [c for c, v in cnt.items() if v == lo]
    if len(cols) != 1:
        return None
    return _build(inp, lambda i, j: inp[i][j] == cols[0])


def second_common(inp, out):
    cnt = _counts(inp)
    vals = sorted(set(cnt.values()), reverse=True)
    if len(vals) < 2:
        return None
    cols = [c for c, v in cnt.items() if v == vals[1]]
    if len(cols) != 1:
        return None
    return _build(inp, lambda i, j: inp[i][j] == cols[0])


def inverted_gate(inp, out):
    mc = _mode(inp)
    return _build(inp, lambda i, j: inp[i][j] != mc)


def fill_with_mode(inp, out):
    mc = _mode(inp)
    return _build(inp, lambda i, j: inp[i][j] == mc, fill=mc)


def transposed_layout(inp, out):
    mc = _mode(inp)
    return _build(inp, lambda i, j: inp[j][i] == mc)


def mirrored_tile(inp, out):
    mc = _mode(inp)
    return _build(inp, lambda i, j: inp[i][j] == mc, tile=[r[::-1] for r in inp])


def transposed_tile(inp, out):
    mc = _mode(inp)
    n, m = len(inp), len(inp[0])
    tile = [[inp[b][a] for b in range(n)] for a in range(m)]
    return _build(inp, lambda i, j: inp[i][j] == mc, tile=tile)


def solid_blocks(inp, out):
    mc = _mode(inp)
    n, m = len(inp), len(inp[0])
    return _build(inp, lambda i, j: inp[i][j] == mc, tile=[[mc] * m for _ in range(n)])


def masked_copy(inp, out):
    mc = _mode(inp)
    tile = [[c if c == mc else 0 for c in r] for r in inp]
    return _build(inp, lambda i, j: inp[i][j] == mc, tile=tile)


def first_hit_only(inp, out):
    mc = _mode(inp)
    n, m = len(inp), len(inp[0])
    first = next((i, j) for i in range(n) for j in range(m) if inp[i][j] == mc)
    return _build(inp, lambda i, j: (i, j) == first)


def gate_on_row_zero(inp, out):
    mc = _mode(inp)
    return _build(inp, lambda i, j: i == 0 and inp[i][j] == mc)


def marker_grid(inp, out):
    mc = _mode(inp)
    return [[mc if c == mc else 0 for c in r] for r in inp]


ALTERNATIVES = [
    ("gate on the least common color instead of the most common", least_common),
    ("gate on the second most common color", second_common),
    ("copy the input where the cell is not the most common color", inverted_gate),
    ("blank blocks filled with the most common color instead of the background", fill_with_mode),
    ("block layout transposed: block (i, j) stands for input cell (j, i)", transposed_layout),
    ("each copied block is the input mirrored left to right", mirrored_tile),
    ("each copied block is the input transposed", transposed_tile),
    ("copied blocks are solid blocks of the most common color", solid_blocks),
    ("copied blocks keep only the most common color's cells", masked_copy),
    ("only the first block whose cell has the most common color is copied", first_hit_only),
    ("only blocks in the first block row are copied", gate_on_row_zero),
    ("output is the input-sized mask of the most common color, not expanded", marker_grid),
]


def _valid(g, out):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/c3e719e8.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, f in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                ok += 1
        print(ok, "-", desc)
