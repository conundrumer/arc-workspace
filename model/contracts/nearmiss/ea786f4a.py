import json
from collections import Counter
from pathlib import Path


def _info(inp):
    cnt = Counter(c for r in inp for c in r)
    ink = min(cnt, key=lambda k: cnt[k])
    bg = max(cnt, key=lambda k: cnt[k])
    pos = [(i, j) for i, r in enumerate(inp) for j, c in enumerate(r) if c == ink]
    return ink, bg, pos[0]


def _paint(inp, pred, on, off=None):
    """Cells where pred(i, j) holds get color `on`; others keep input or `off`."""
    return [[on if pred(i, j) else (c if off is None else off)
             for j, c in enumerate(r)] for i, r in enumerate(inp)]


def plus_not_x(inp, out):
    ink, bg, (a, b) = _info(inp)
    return _paint(inp, lambda i, j: i == a or j == b, ink)


def x_keeps_center(inp, out):
    ink, bg, (a, b) = _info(inp)
    g = [r[:] for r in out]
    g[a][b] = bg
    return g


def inverted(inp, out):
    ink, bg, (a, b) = _info(inp)
    return _paint(inp, lambda i, j: abs(i - a) != abs(j - b), ink)


def main_diag_only(inp, out):
    ink, bg, (a, b) = _info(inp)
    return _paint(inp, lambda i, j: i - j == a - b, ink)


def anti_diag_only(inp, out):
    ink, bg, (a, b) = _info(inp)
    return _paint(inp, lambda i, j: i + j == a + b, ink)


def upper_rays_only(inp, out):
    ink, bg, (a, b) = _info(inp)
    return _paint(inp, lambda i, j: i <= a and abs(i - a) == abs(j - b), ink)


def x_plus_plus(inp, out):
    ink, bg, (a, b) = _info(inp)
    return _paint(inp, lambda i, j: abs(i - a) == abs(j - b) or i == a or j == b, ink)


def x_shifted_down(inp, out):
    ink, bg, (a, b) = _info(inp)
    return _paint(inp, lambda i, j: abs(i - a - 1) == abs(j - b), ink)


def x_radius_one(inp, out):
    ink, bg, (a, b) = _info(inp)
    g = _paint(inp, lambda i, j: abs(i - a) == abs(j - b) and abs(i - a) <= 1, ink)
    return g if g != out else None


def x_wrong_color(inp, out):
    ink, bg, (a, b) = _info(inp)
    return _paint(inp, lambda i, j: abs(i - a) == abs(j - b), (bg + 1) % 10 or 1)


def x_ink_over_fill_dot_kept(inp, out):
    # X painted with the background color everywhere (X erased), dot removed.
    ink, bg, (a, b) = _info(inp)
    return _paint(inp, lambda i, j: (i, j) == (a, b), bg)


def unchanged(inp, out):
    return [r[:] for r in inp]


ALTERNATIVES = [
    ("Plus-shaped cross (row and column of the dot) instead of the X", plus_not_x),
    ("X is drawn but the dot cell itself keeps the background color", x_keeps_center),
    ("Colors swapped: X keeps background, all other cells become the dot color", inverted),
    ("Only the down-right/up-left diagonal is drawn", main_diag_only),
    ("Only the down-left/up-right diagonal is drawn", anti_diag_only),
    ("Only the two upward diagonal rays are drawn", upper_rays_only),
    ("X and plus both drawn", x_plus_plus),
    ("X centered one row below the dot", x_shifted_down),
    ("X rays stop after one step from the dot", x_radius_one),
    ("X drawn in a wrong color (not the dot color)", x_wrong_color),
    ("Only the dot is erased, no rays", x_ink_over_fill_dot_kept),
    ("Input returned unchanged", unchanged),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r) and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/ea786f4a.json'))
    train = task["train"]
    print("pairs", len(train))
    for desc, f in ALTERNATIVES:
        n = sum(1 for p in train if (g := f(p["input"], p["output"])) is not None and _valid(g, p["output"]))
        print(n, desc)
