import json
from collections import Counter
from pathlib import Path


def _is_cols(inp, out):
    """True when the input is tiled along columns (output narrower)."""
    return len(out[0]) < len(inp[0])


def _t(g):
    return [list(r) for r in zip(*g)]


def _along(inp, out, f):
    """Apply f (a function on a grid, acting on columns) along the tiling axis."""
    if _is_cols(inp, out):
        return f(out)
    return _t(f(_t(out)))


def _other_axis_half(inp, out):
    if _is_cols(inp, out):
        return [list(r) for r in inp[: len(inp) // 2]]
    return [list(r[: len(r) // 2]) for r in inp]


def _half_tile(inp, out):
    return _along(inp, out, lambda g: [list(r[: max(1, len(r) // 2)]) for r in g])


def _input_copy(inp, out):
    return [list(r) for r in inp]


def _three_copies(inp, out):
    return _along(inp, out, lambda g: [list(r) * 3 for r in g])


def _flip_axis(inp, out):
    return _along(inp, out, lambda g: [list(reversed(r)) for r in g])


def _flip_other(inp, out):
    return _along(inp, out, lambda g: [list(r) for r in reversed(g)])


def _shift_one(inp, out):
    def f(g):
        w = len(g[0])
        return [list((r * 2)[1 : 1 + w]) for r in g]
    return _along(inp, out, f)


def _drop_last(inp, out):
    return _along(inp, out, lambda g: [list(r[:-1]) for r in g])


def _first_line_repeated(inp, out):
    if _is_cols(inp, out):
        return [list(out[0]) for _ in out]
    return [[row[0]] * len(row) for row in out]


def _erase_dominant(inp, out):
    c = Counter(v for r in out for v in r)
    top = max(c.items(), key=lambda kv: (kv[1], -kv[0]))[0]
    return [[0 if v == top else v for v in r] for r in out]


def _extra_line(inp, out):
    return _along(inp, out, lambda g: [list(r) + [r[0]] for r in g])


ALTERNATIVES = [
    ("splits the input along the other axis, so the output is half the input in the wrong dimension", _other_axis_half),
    ("takes only half of the repeating tile", _half_tile),
    ("returns the input unchanged, never removing the repeat", _input_copy),
    ("repeats the tile three times instead of reducing to one copy", _three_copies),
    ("reverses the tile along the repeat axis", _flip_axis),
    ("reverses the tile along the axis across the repeat", _flip_other),
    ("crops one cell off the tile start, a cyclic offset of one", _shift_one),
    ("drops the last line of the tile (size one too small along repeat axis)", _drop_last),
    ("keeps only the tile's first line and repeats it over the tile", _first_line_repeated),
    ("erases the tile's most common color to 0", _erase_dominant),
    ("adds one extra line to the tile (size one too large along repeat axis)", _extra_line),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/7b7f7511.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
