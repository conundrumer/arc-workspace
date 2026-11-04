from pathlib import Path
import json
from collections import Counter

def ncol(inp):
    return len({c for r in inp for c in r})

def tile(g, n, m=None, tf=None):
    m = n if m is None else m
    h, w = len(g), len(g[0])
    res = []
    for ti in range(n):
        for a in range(h):
            row = []
            for tj in range(m):
                t = tf(g, ti, tj) if tf else g
                row.extend(t[a])
            res.append(row)
    return res

def fliph(g): return [r[::-1] for r in g]
def transpose(g): return [list(r) for r in zip(*g)]
def rot90(g): return [list(r) for r in zip(*g[::-1])]

def minus_one(inp, out): return tile(inp, ncol(inp) - 1)
def plus_one(inp, out): return tile(inp, ncol(inp) + 1)
def fixed3(inp, out): return tile(inp, 3)
def one_row(inp, out): return tile(inp, 1, ncol(inp))
def one_col(inp, out): return tile(inp, ncol(inp), 1)
def mirror_alt(inp, out):
    return tile(inp, ncol(inp), tf=lambda g, i, j: fliph(g) if (i + j) % 2 else g)
def transposed(inp, out): return tile(inp, ncol(inp), tf=lambda g, i, j: transpose(g))
def rotated(inp, out): return tile(inp, ncol(inp), tf=lambda g, i, j: rot90(g))
def diag_only(inp, out):
    n = ncol(inp); h = len(inp)
    def tf(g, i, j):
        return g if i == j else [[0] * len(g[0]) for _ in g]
    return tile(inp, n, tf=tf)
def drop_last(inp, out):
    n = ncol(inp)
    def tf(g, i, j):
        return [[0] * len(g[0]) for _ in g] if (i, j) == (n - 1, n - 1) else g
    return tile(inp, n, tf=tf)
def kron_common(inp, out):
    cnt = Counter(c for r in inp for c in r)
    top = cnt.most_common(1)[0][0]
    h, w = len(inp), len(inp[0])
    return [[inp[a][b] if inp[i][j] == top else 0
             for j in range(w) for b in range(w)]
            for i in range(h) for a in range(h)]
def count_cells_min(inp, out):
    cnt = Counter(c for r in inp for c in r)
    return tile(inp, min(cnt.values()) + 1)

ALTERNATIVES = [
    ("tile count is distinct colors minus one", minus_one),
    ("tile count is distinct colors plus one", plus_one),
    ("tile count is always 3 (the input side)", fixed3),
    ("tiles laid in one row only", one_row),
    ("tiles laid in one column only", one_col),
    ("alternate tiles are mirrored left-right", mirror_alt),
    ("each tile is the transposed input", transposed),
    ("each tile is the input rotated 90 degrees", rotated),
    ("only diagonal tiles hold the input, others are 0", diag_only),
    ("last tile is left blank", drop_last),
    ("fractal: tile placed only where input cell is the most common color", kron_common),
    ("tile count is least-frequent color's cell count plus one", count_cells_min),
]

def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r))

if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/a59b95c0.json')))["train"]
    print("pairs", len(t))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in t:
            g = f(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
