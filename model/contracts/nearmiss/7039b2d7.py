"""Near-miss readings for ARC task 7039b2d7 (divider lines cut the grid into a
lattice of cells; output has one cell per lattice cell, filled with the
background color)."""
import json
from collections import Counter
from pathlib import Path


def _info(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(c for r in inp for c in r).most_common(1)[0][0]
    rdiv = [i for i in range(h) if len(set(inp[i])) == 1 and inp[i][0] != bg]
    cdiv = [j for j in range(w) if len({inp[i][j] for i in range(h)}) == 1 and inp[0][j] != bg]
    div = inp[rdiv[0]][0] if rdiv else inp[0][cdiv[0]]
    return h, w, bg, rdiv, cdiv, div


def _bands(n, divs):
    """Runs of non-divider lines, as (start, end) inclusive."""
    out, start = [], None
    for k in range(n):
        if k in divs:
            if start is not None:
                out.append((start, k - 1))
                start = None
        elif start is None:
            start = k
    if start is not None:
        out.append((start, n - 1))
    return out


def _fill(r, c, v):
    return [[v] * c for _ in range(r)]


def divider_count(inp, out):
    h, w, bg, rd, cd, div = _info(inp)
    return _fill(len(rd), len(cd), bg)


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def divider_color_fill(inp, out):
    h, w, bg, rd, cd, div = _info(inp)
    return _fill(len(out), len(out[0]), div)


def one_extra(inp, out):
    return _fill(len(out) + 1, len(out[0]) + 1, out[0][0])


def one_fewer(inp, out):
    return _fill(len(out) - 1, len(out[0]) - 1, out[0][0])


def single_row(inp, out):
    return _fill(1, len(out[0]), out[0][0])


def single_column(inp, out):
    return _fill(len(out), 1, out[0][0])


def zero_fill(inp, out):
    return _fill(len(out), len(out[0]), 0)


def first_cell_crop(inp, out):
    h, w, bg, rd, cd, div = _info(inp)
    r0, r1 = _bands(h, set(rd))[0]
    c0, c1 = _bands(w, set(cd))[0]
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def drop_thin_bands(inp, out):
    h, w, bg, rd, cd, div = _info(inp)
    rb = [b for b in _bands(h, set(rd)) if b[1] > b[0]]
    cb = [b for b in _bands(w, set(cd)) if b[1] > b[0]]
    return _fill(len(rb), len(cb), bg)


def last_cell_divider(inp, out):
    h, w, bg, rd, cd, div = _info(inp)
    g = [list(r) for r in out]
    g[-1][-1] = div
    return g


ALTERNATIVES = [
    ("count divider lines instead of cells between them", divider_count),
    ("rows and columns swapped in the output", transposed),
    ("cells filled with the divider color instead of the background", divider_color_fill),
    ("one extra cell row and column (dividers counted as cell boundaries)", one_extra),
    ("one fewer cell row and column", one_fewer),
    ("only the columns counted: output is a single row", single_row),
    ("only the rows counted: output is a single column", single_column),
    ("cells filled with 0 instead of the background color", zero_fill),
    ("output is the top-left cell cropped from the input", first_cell_crop),
    ("one-line-wide cells ignored when counting", drop_thin_bands),
    ("last cell takes the divider color", last_cell_divider),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/7039b2d7.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "-", desc)
