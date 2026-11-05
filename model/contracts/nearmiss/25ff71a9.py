import json
from pathlib import Path


def _color(g):
    for r in g:
        for v in r:
            if v:
                return v
    return 0


def _rows_shift(g, k):
    n = len(g)
    return [list(g[(i - k) % n]) for i in range(n)]


def _cols_shift(g, k):
    return [[r[(j - k) % len(r)] for j in range(len(r))] for r in g]


def up1(inp, out):
    return _rows_shift(inp, -1)


def down2(inp, out):
    return _rows_shift(inp, 2)


def right1(inp, out):
    return _cols_shift(inp, 1)


def left1(inp, out):
    return _cols_shift(inp, -1)


def unchanged(inp, out):
    return [list(r) for r in inp]


def recolor(inp, out):
    c = _color(out)
    n = c % 9 + 1
    return [[n if v else 0 for v in r] for r in out]


def union_with_input(inp, out):
    return [[a or b for a, b in zip(ri, ro)] for ri, ro in zip(inp, out)]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def flip_rows(inp, out):
    return [list(r) for r in reversed(inp)]


def top_row_filled(inp, out):
    c = _color(inp)
    g = [list(r) for r in out]
    g[0] = [c] * len(g[0])
    return g


ALTERNATIVES = [
    ("shifts up by one row, wrapping, instead of down", up1),
    ("shifts down by two rows, wrapping", down2),
    ("shifts right by one column, wrapping (wrong axis)", right1),
    ("shifts left by one column, wrapping (wrong axis and direction)", left1),
    ("leaves the grid unchanged", unchanged),
    ("shifts correctly but recolors the object to another color", recolor),
    ("copies the object down but keeps the original too", union_with_input),
    ("transposes the correct result (swapped axes)", transposed),
    ("mirrors the rows top to bottom instead of shifting", flip_rows),
    ("shifts down but fills the vacated top row with the object color", top_row_filled),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/25ff71a9.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
