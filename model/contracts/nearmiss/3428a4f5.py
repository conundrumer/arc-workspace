"""Near-miss readings for ARC task 3428a4f5.

True rule: the input is two 6x5 panels split by a row of 4s. The output is
6x5 and holds 3 where exactly one of the two panels is nonzero, else 0.
"""
import json
from pathlib import Path


def _panels(inp):
    h = len(inp) // 2
    return inp[:h], inp[h + 1:]


def _combine(top, bot, f, color=3):
    return [[color if f(a != 0, b != 0) else 0 for a, b in zip(r1, r2)]
            for r1, r2 in zip(top, bot)]


def _or(inp, out):
    t, b = _panels(inp)
    return _combine(t, b, lambda x, y: x or y)


def _and(inp, out):
    t, b = _panels(inp)
    return _combine(t, b, lambda x, y: x and y)


def _xnor(inp, out):
    t, b = _panels(inp)
    return _combine(t, b, lambda x, y: x == y)


def _wrong_color(inp, out):
    return [[2 if v else 0 for v in r] for r in out]


def _flip_vertical(inp, out):
    t, b = _panels(inp)
    return _combine(t, b[::-1], lambda x, y: x != y)


def _mirror_horizontal(inp, out):
    t, b = _panels(inp)
    return _combine(t, [r[::-1] for r in b], lambda x, y: x != y)


def _shift_row(inp, out):
    t, b = _panels(inp)
    return _combine(t, b[1:] + b[:1], lambda x, y: x != y)


def _drop_last_row(inp, out):
    return [r[:] for r in out[:-1]]


def _keep_separator(inp, out):
    h = len(out)
    return [r[:] for r in out] + [[4] * len(out[0])] + [[0] * len(out[0]) for _ in range(h)]


def _top_only(inp, out):
    t, _ = _panels(inp)
    return [[3 if v else 0 for v in r] for r in t]


def _bottom_only(inp, out):
    _, b = _panels(inp)
    return [[3 if v else 0 for v in r] for r in b]


def _transposed(inp, out):
    return [list(r) for r in zip(*out)]


def _last_row_unfilled(inp, out):
    return [r[:] for r in out[:-1]] + [[0] * len(out[0])]


ALTERNATIVES = [
    ("OR of the two panels instead of XOR", _or),
    ("AND of the two panels instead of XOR", _and),
    ("inverted XOR: fill where the panels agree", _xnor),
    ("correct XOR cells painted with the input color 2 instead of 3", _wrong_color),
    ("bottom panel flipped upside down before the XOR", _flip_vertical),
    ("bottom panel mirrored left-right before the XOR", _mirror_horizontal),
    ("bottom panel offset by one row before the XOR", _shift_row),
    ("output one row short: last row dropped", _drop_last_row),
    ("output keeps the separator row and an empty second panel", _keep_separator),
    ("only the top panel recolored to 3", _top_only),
    ("only the bottom panel recolored to 3", _bottom_only),
    ("correct XOR output transposed", _transposed),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/3428a4f5.json").read_text())
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                  and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
                  and g != p["output"])
            n += ok
        print(f"{n}/{len(pairs)}  {desc}")
