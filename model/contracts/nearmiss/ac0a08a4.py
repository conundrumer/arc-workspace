import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _cells(inp):
    bg = _bg(inp)
    return [(i, j, v) for i, r in enumerate(inp) for j, v in enumerate(r) if v != bg]


def _upscale(grid, k):
    if k < 1:
        return None
    return [[v for v in row for _ in range(k)] for row in grid for _ in range(k)]


def block_minus_one(inp, out):
    return _upscale(inp, len(_cells(inp)) - 1)


def block_plus_one(inp, out):
    return _upscale(inp, len(_cells(inp)) + 1)


def block_by_background_count(inp, out):
    bg = _bg(inp)
    return _upscale(inp, sum(v == bg for r in inp for v in r))


def no_upscale(inp, out):
    return [r[:] for r in inp]


def transposed_layout(inp, out):
    return _upscale([list(c) for c in zip(*inp)], len(_cells(inp)))


def mirrored_horizontally(inp, out):
    return _upscale([r[::-1] for r in inp], len(_cells(inp)))


def mirrored_vertically(inp, out):
    return _upscale(inp[::-1], len(_cells(inp)))


def single_color(inp, out):
    cells = _cells(inp)
    c = cells[0][2]
    bg = _bg(inp)
    return _upscale([[c if v != bg else bg for v in r] for r in inp], len(cells))


def colors_shifted(inp, out):
    cells = _cells(inp)
    cols = [c[2] for c in cells]
    new = {(i, j): cols[(k + 1) % len(cols)] for k, (i, j, _) in enumerate(cells)}
    g = [[new.get((i, j), _bg(inp)) for j in range(len(inp[0]))] for i in range(len(inp))]
    return _upscale(g, len(cells))


def copies_of_input(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    res = [[bg] * (w * w) for _ in range(h * h)]
    for i in range(h):
        for j in range(w):
            if inp[i][j] != bg:
                for a in range(h):
                    for b in range(w):
                        res[i * h + a][j * w + b] = inp[a][b]
    return res


def last_block_unfilled(inp, out):
    cells = _cells(inp)
    n = len(cells)
    i, j, _ = cells[-1]
    bg = _bg(inp)
    res = [r[:] for r in out]
    for a in range(i * n, (i + 1) * n):
        for b in range(j * n, (j + 1) * n):
            res[a][b] = bg
    return res


ALTERNATIVES = [
    ("block side is one less than the count of non-background cells", block_minus_one),
    ("block side is one more than the count of non-background cells", block_plus_one),
    ("block side is the count of background cells", block_by_background_count),
    ("no enlargement: output is the input grid", no_upscale),
    ("block layout follows the transposed input", transposed_layout),
    ("block layout follows the input mirrored left to right", mirrored_horizontally),
    ("block layout follows the input mirrored top to bottom", mirrored_vertically),
    ("all blocks take the color of the first non-background cell", single_color),
    ("each block takes the color of the next non-background cell in reading order", colors_shifted),
    ("each non-background cell is replaced by a copy of the whole input", copies_of_input),
    ("last block in reading order is left unfilled", last_block_unfilled),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/ac0a08a4.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
