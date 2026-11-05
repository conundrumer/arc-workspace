import json
from collections import Counter
from pathlib import Path


def _depth(inp):
    return sum(1 for r in inp if any(r))


def _slab(inp):
    d = _depth(inp)
    return [r[:] for r in inp[len(inp) - d:]]


def _mirror_tail(inp, rows):
    """Input with the slab rows placed at the bottom and `rows` on the top."""
    h = len(inp)
    w = len(inp[0])
    top = [r[:] for r in rows]
    mid = [[0] * w for _ in range(h - len(top) - _depth(inp))]
    return top + mid + _slab(inp)


def rot180_top(inp, out):
    s = _slab(inp)
    return _mirror_tail(inp, [r[::-1] for r in reversed(s)])


def translate_top(inp, out):
    s = _slab(inp)
    return _mirror_tail(inp, s)


def shifted_mirror(inp, out):
    s = _slab(inp)
    m = list(reversed(s))
    h, w = len(inp), len(inp[0])
    top = [[0] * w] + [r[:] for r in m]
    mid = [[0] * w for _ in range(h - len(top) - len(s))]
    return top + mid + s


def short_mirror(inp, out):
    g = [r[:] for r in out]
    d = _depth(inp)
    g[d - 1] = [0] * len(g[0])
    return g


def full_symmetric(inp, out):
    g = [r[:] for r in out]
    for r in g:
        for j in range(len(r)):
            if r[j] == 0:
                r[j] = r[len(r) - 1 - j]
    return g


def side_by_side(inp, out):
    return [r + r[::-1] for r in inp]


def single_color_mirror(inp, out):
    s = _slab(inp)
    cnt = Counter(c for r in s for c in r if c)
    keep = cnt.most_common(1)[0][0]
    top = [[c if c == keep else 0 for c in r] for r in reversed(s)]
    return _mirror_tail(inp, top)


def slab_only(inp, out):
    return _slab(inp)


def mirror_with_full_input_flip(inp, out):
    # flips whole input and overlays, but keeps the slab rows only once,
    # leaving the slab depth rows doubled in the middle
    s = _slab(inp)
    h, w = len(inp), len(inp[0])
    top = [r[:] for r in reversed(s)]
    pad = [[0] * w for _ in range(h - len(s))]
    return top + pad


def mirror_columns_instead(inp, out):
    # mirrors the slab's column order within the slab, no vertical flip of rows
    s = _slab(inp)
    return _mirror_tail(inp, [r[::-1] for r in s])


ALTERNATIVES = [
    ("mirror is a 180-degree rotation of the slab instead of a vertical flip", rot180_top),
    ("mirror is the slab copied unflipped (translation) onto the empty side", translate_top),
    ("mirror is offset by one row, leaving a gap row next to the slab and one too few rows reaching the edge", shifted_mirror),
    ("slab depth is one too small, so the row next to the slab is not mirrored", short_mirror),
    ("output is also made left-right symmetric by filling empty cells from their horizontal mirror", full_symmetric),
    ("mirror is placed to the side (output is twice as wide) instead of the empty vertical side", side_by_side),
    ("only the most common ink color of the slab is mirrored", single_color_mirror),
    ("output is only the slab cropped, with no mirror", slab_only),
    ("mirror is the slab with each row reversed left-right but row order kept", mirror_columns_instead),
    ("mirror is made but the slab itself is dropped from the output (empty rows left in the middle)", mirror_with_full_input_flip),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/f25ffba3.json"))
    pairs = task["train"]

    def valid(g, out):
        if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
            return False
        if len({len(r) for r in g}) != 1 or not g[0]:
            return False
        if not all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r):
            return False
        return g != out

    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {fn.__name__}: {desc}")
