import json
from pathlib import Path


def _key(inp):
    return inp[0][0], inp[0][1], inp[1][0], inp[1][1]


def _in_key(r, c):
    return r < 2 and c < 2


def _apply(inp, mapping, recolor_key=False):
    return [[(mapping.get(v, v) if (recolor_key or not _in_key(r, c)) else v)
             for c, v in enumerate(row)] for r, row in enumerate(inp)]


def _pairs_map(pairs, both=True):
    m = {}
    for a, b in pairs:
        m[a] = b
        if both:
            m[b] = a
    return m


def vertical_pairs(inp, out):
    a, b, c, d = _key(inp)
    return _apply(inp, _pairs_map([(a, c), (b, d)]))


def diagonal_pairs(inp, out):
    a, b, c, d = _key(inp)
    return _apply(inp, _pairs_map([(a, d), (b, c)]))


def key_also_recolored(inp, out):
    a, b, c, d = _key(inp)
    return _apply(inp, _pairs_map([(a, b), (c, d)]), recolor_key=True)


def left_to_right_only(inp, out):
    a, b, c, d = _key(inp)
    return _apply(inp, _pairs_map([(a, b), (c, d)], both=False))


def right_to_left_only(inp, out):
    a, b, c, d = _key(inp)
    return _apply(inp, _pairs_map([(b, a), (d, c)], both=False))


def cycle_in_reading_order(inp, out):
    a, b, c, d = _key(inp)
    return _apply(inp, {a: b, b: c, c: d, d: a})


def top_row_pair_only(inp, out):
    a, b, c, d = _key(inp)
    return _apply(inp, _pairs_map([(a, b)]))


def bottom_row_pair_only(inp, out):
    a, b, c, d = _key(inp)
    return _apply(inp, _pairs_map([(c, d)]))


def key_cleared(inp, out):
    g = [row[:] for row in out]
    for r in range(2):
        for c in range(2):
            g[r][c] = 0
    return g


def crop_off_key(inp, out):
    return [row[2:] for row in out[2:]]


def below_row_six_unchanged(inp, out):
    g = [row[:] for row in out]
    for r in range(6, len(g)):
        g[r] = inp[r][:]
    return g


def shifted_right(inp, out):
    return [[0] + row[:-1] for row in out]


ALTERNATIVES = [
    ("key pairs colors down each column instead of across each row", vertical_pairs),
    ("key pairs colors on its diagonals", diagonal_pairs),
    ("swap is also applied to the key cells themselves", key_also_recolored),
    ("each key row maps left color to right color only, not back", left_to_right_only),
    ("each key row maps right color to left color only, not back", right_to_left_only),
    ("key read as a cycle in reading order: a->b->c->d->a", cycle_in_reading_order),
    ("only the top key row's swap is applied; the bottom row is missed", top_row_pair_only),
    ("only the bottom key row's swap is applied; the top row is missed", bottom_row_pair_only),
    ("correct recoloring but the key block is erased to 0", key_cleared),
    ("output cropped to exclude the two key rows and columns", crop_off_key),
    ("recoloring stops after row 5; lower rows stay as in the input", below_row_six_unchanged),
    ("correct recoloring but the whole grid is shifted one column right", shifted_right),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/0becf7df.json'))
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
