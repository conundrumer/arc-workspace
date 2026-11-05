import json
from pathlib import Path


def _color(inp):
    return max(v for r in inp for v in r)


def _swap(inp):
    c = _color(inp)
    return [[0 if v == c else c for v in r] for r in inp]


def _tile(g, a, b):
    return [list(r) * b for _ in range(a) for r in g]


def no_swap_tiled(inp, out):
    return _tile(inp, 2, 2)


def single_copy(inp, out):
    return _swap(inp)


def three_by_three(inp, out):
    return _tile(_swap(inp), 3, 3)


def horizontal_only(inp, out):
    return _tile(_swap(inp), 1, 2)


def vertical_only(inp, out):
    return _tile(_swap(inp), 2, 1)


def copies_equal_size(inp, out):
    n = len(inp)
    return _tile(_swap(inp), n, n)


def mirrored_copies(inp, out):
    s = _swap(inp)
    m = [r[::-1] for r in s]
    return [a + b for a, b in zip(s, m)] + [a + b for a, b in zip(m, s)]


def transposed_copies(inp, out):
    s = _swap(inp)
    t = [list(r) for r in zip(*s)]
    return [a + b for a, b in zip(s, t)] + [a + b for a, b in zip(t, s)]


def upscale_swapped(inp, out):
    s = _swap(inp)
    res = []
    for r in s:
        row = [v for v in r for _ in range(2)]
        res.append(row)
        res.append(list(row))
    return res


def fractal_mask(inp, out):
    s = _swap(inp)
    n = len(inp)
    res = []
    for i in range(n):
        for k in range(n):
            res.append([s[k][l] if inp[i][j] else 0 for j in range(n) for l in range(n)])
    return res


def only_first_copy_swapped(inp, out):
    n = len(inp)
    s = _swap(inp)
    res = _tile(inp, 2, 2)
    for i in range(n):
        for j in range(n):
            res[i][j] = s[i][j]
    return res


def last_copy_blank(inp, out):
    n = len(inp)
    res = [list(r) for r in out]
    for i in range(n, 2 * n):
        for j in range(n, 2 * n):
            res[i][j] = 0
    return res


ALTERNATIVES = [
    ("tile the input itself 2x2 without swapping the colors", no_swap_tiled),
    ("output only one swapped copy", single_copy),
    ("tile the swapped grid 3x3", three_by_three),
    ("tile the swapped grid only horizontally (1x2)", horizontal_only),
    ("tile the swapped grid only vertically (2x1)", vertical_only),
    ("number of copies per side equals the input side length", copies_equal_size),
    ("mirror alternate copies of the swapped grid left-right", mirrored_copies),
    ("transpose the off-diagonal copies of the swapped grid", transposed_copies),
    ("scale the swapped grid up by 2 instead of tiling it", upscale_swapped),
    ("place a swapped copy only at the nonzero cells of the input (fractal)", fractal_mask),
    ("swap the colors in the first copy only, the other copies stay as input", only_first_copy_swapped),
    ("true output with the last copy left blank", last_copy_blank),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/48131b3c.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
