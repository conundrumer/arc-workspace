import json
from pathlib import Path


def _period(g):
    w = len(g[0])
    for p in range(1, w + 1):
        if all(row[c] == row[c + p] for row in g for c in range(w - p)):
            return p
    return w


def _extend(g, width, step):
    """Each row continues to `width` cells, each new cell copying the cell `step` before."""
    res = []
    for row in g:
        r = list(row)
        while len(r) < width:
            r.append(r[len(r) - step])
        res.append(r[:width])
    return res


def tile_literal(inp, out):
    return [list(r) + list(r) for r in inp]


def triple_width(inp, out):
    return _extend(inp, 3 * len(inp[0]), _period(inp))


def new_half_blank(inp, out):
    w = len(inp[0])
    return [list(r) + [0] * w for r in inp]


def mirror(inp, out):
    return [list(r) + list(r)[::-1] for r in inp]


def stack_vertically(inp, out):
    return [list(r) for r in inp] + [list(r) for r in inp]


def anchored_right(inp, out):
    w, p = len(inp[0]), _period(inp)
    return [[r[w - 1 - ((2 * w - 1 - c) % p)] for c in range(2 * w)] for r in inp]


def crop_last_column(inp, out):
    return [list(r[:-1]) for r in out]


def period_too_long(inp, out):
    return _extend(inp, 2 * len(inp[0]), _period(inp) + 1)


def period_too_short(inp, out):
    p = _period(inp)
    if p < 2:
        return None
    return _extend(inp, 2 * len(inp[0]), p - 1)


def repeat_last_column(inp, out):
    return [list(r) + [r[-1]] * len(r) for r in inp]


def grow_leftward(inp, out):
    w, p = len(inp[0]), _period(inp)
    return [[r[(c - w) % p] if c < w else r[c - w] for c in range(2 * w)] for r in inp]


def shifted_one_column(inp, out):
    return [r[1:] + r[:1] for r in out]


ALTERNATIVES = [
    ("copy the input twice side by side without continuing the period", tile_literal),
    ("grow three times as wide instead of two", triple_width),
    ("keep the input and leave the new half background", new_half_blank),
    ("append the mirror image of the input", mirror),
    ("grow downward instead of rightward, stacking two copies", stack_vertically),
    ("continue the period with its phase anchored at the right edge", anchored_right),
    ("output one column narrower than twice the width", crop_last_column),
    ("use a period one cell too long when continuing", period_too_long),
    ("use a period one cell too short when continuing", period_too_short),
    ("fill the new half with the last input column repeated", repeat_last_column),
    ("grow leftward, input on the right and the period continued backward", grow_leftward),
    ("correct output shifted left by one column with wraparound", shifted_one_column),
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
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/963e52fc.json").read_text())
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in pairs:
            g = fn(pr["input"], pr["output"])
            if g is not None and _valid(g, pr["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
