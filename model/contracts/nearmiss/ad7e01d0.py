import json
from collections import Counter
from pathlib import Path


def _stamp(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _second(inp):
    cnt = Counter(c for r in inp for c in r)
    s = _stamp(inp)
    rest = [(v, -k) for k, v in cnt.items() if k != s and k != 0]
    if not rest:
        return 0
    return -max(rest)[1]


def _build(inp, active, tile=None, bg=0, fill_inactive=None):
    n = len(inp)
    tile = tile or inp
    res = [[bg] * (n * n) for _ in range(n * n)]
    for i in range(n):
        for j in range(n):
            if active(i, j):
                for a in range(n):
                    for b in range(n):
                        res[i * n + a][j * n + b] = tile[a][b]
            elif fill_inactive is not None:
                for a in range(n):
                    for b in range(n):
                        res[i * n + a][j * n + b] = fill_inactive
    return res


def inverse_active(inp, out):
    s = _stamp(inp)
    return _build(inp, lambda i, j: inp[i][j] != s)


def second_color(inp, out):
    s = _second(inp)
    return _build(inp, lambda i, j: inp[i][j] == s)


def transposed_tile(inp, out):
    s = _stamp(inp)
    t = [list(r) for r in zip(*inp)]
    return _build(inp, lambda i, j: inp[i][j] == s, tile=t)


def flipped_tile(inp, out):
    s = _stamp(inp)
    t = [r[::-1] for r in inp]
    return _build(inp, lambda i, j: inp[i][j] == s, tile=t)


def inactive_filled_with_stamp(inp, out):
    s = _stamp(inp)
    return _build(inp, lambda i, j: inp[i][j] == s, fill_inactive=s)


def transposed_activity(inp, out):
    s = _stamp(inp)
    return _build(inp, lambda i, j: inp[j][i] == s)


def last_active_missing(inp, out):
    n = len(inp)
    s = _stamp(inp)
    cells = [(i, j) for i in range(n) for j in range(n) if inp[i][j] == s]
    li, lj = cells[-1]
    return _build(inp, lambda i, j: inp[i][j] == s and (i, j) != (li, lj))


def first_row_only(inp, out):
    s = _stamp(inp)
    return _build(inp, lambda i, j: inp[i][j] == s and i == 0)


def neighbor_expanded(inp, out):
    n = len(inp)
    s = _stamp(inp)

    def act(i, j):
        for di, dj in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, j + dj
            if 0 <= a < n and 0 <= b < n and inp[a][b] == s:
                return True
        return False
    return _build(inp, act)


def shifted_right_one_cell(inp, out):
    return [[0] + r[:-1] for r in out]


def zero_cells_active(inp, out):
    return _build(inp, lambda i, j: inp[i][j] == 0)


def single_tile(inp, out):
    n = len(inp)
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("stamp the tile on cells that are not the stamp color", inverse_active),
    ("stamp color taken as the second most common non-zero color", second_color),
    ("stamped tile is transposed", transposed_tile),
    ("stamped tile is mirrored left-right", flipped_tile),
    ("inactive blocks filled with the stamp color instead of background", inactive_filled_with_stamp),
    ("block activity read from the transposed input", transposed_activity),
    ("last active block left empty", last_active_missing),
    ("only the active blocks in the first block row are stamped", first_row_only),
    ("blocks also stamped where a 4-neighbour cell has the stamp color", neighbor_expanded),
    ("true output shifted right by one cell", shifted_right_one_cell),
    ("stamp on cells of color 0", zero_cells_active),
    ("input returned as a single untiled copy", single_tile),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/ad7e01d0.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(ok, desc)
