import json
from pathlib import Path


def _fv(g):
    return [list(r) for r in g[::-1]]


def _fh(g):
    return [list(r[::-1]) for r in g]


def _cp(g):
    return [list(r) for r in g]


def _swap_colors(g, rows):
    cols = sorted({c for r in g for c in r})
    if len(cols) != 2:
        return None
    a, b = cols
    m = {a: b, b: a}
    return [[m[c] for c in r] if i in rows else list(r) for i, r in enumerate(g)]


def flipped_below(inp, out):
    return _cp(inp) + _fv(inp)


def hflip_on_top(inp, out):
    return _fh(inp) + _cp(inp)


def rot180_on_top(inp, out):
    return _fh(_fv(inp)) + _cp(inp)


def plain_tiling(inp, out):
    return _cp(inp) + _cp(inp)


def flipped_twice(inp, out):
    return _fv(inp) + _fv(inp)


def shared_row_dropped(inp, out):
    return _fv(inp) + _cp(inp)[1:]


def three_copies(inp, out):
    return _fv(inp) + _cp(inp) + _fv(inp)


def side_by_side_mirror(inp, out):
    return [list(r) + list(r[::-1]) for r in inp]


def top_half_colors_swapped(inp, out):
    return _swap_colors(out, set(range(len(out) // 2)))


def bottom_half_colors_swapped(inp, out):
    return _swap_colors(out, set(range(len(out) // 2, len(out))))


def top_half_hflipped(inp, out):
    h = len(out) // 2
    return [list(r[::-1]) for r in out[:h]] + _cp(out[h:])


def last_row_missing(inp, out):
    return _cp(out[:-1])


ALTERNATIVES = [
    ("mirror copy placed below the input instead of above", flipped_below),
    ("mirror copy flipped left-right instead of top-bottom", hflip_on_top),
    ("mirror copy rotated 180 degrees instead of flipped top-bottom", rot180_on_top),
    ("plain repeat of the input with no reflection", plain_tiling),
    ("both halves are the flipped input", flipped_twice),
    ("shared boundary row dropped from the lower copy", shared_row_dropped),
    ("flipped, input, flipped: three stacked copies", three_copies),
    ("mirror placed to the right (width doubled) instead of stacked", side_by_side_mirror),
    ("colors swapped in the top half only", top_half_colors_swapped),
    ("colors swapped in the bottom half only", bottom_half_colors_swapped),
    ("top half also reversed left-right", top_half_hflipped),
    ("true output with the last row cut off", last_row_missing),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/4c4377d9.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
