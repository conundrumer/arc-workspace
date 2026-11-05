import json
from pathlib import Path


def dots(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != 0]


def render(inp, cell, only_first=False):
    """Copy inp, then for each dot set cells of its row via cell(r, c, c0, v, width)."""
    g = [row[:] for row in inp]
    w = len(inp[0])
    ds = dots(inp)
    if only_first:
        ds = ds[:1]
    for r, c0, v in ds:
        for c in range(w):
            x = cell(r, c, c0, v, w)
            if x is not None:
                g[r][c] = x
    return g


def right_alt(r, c, c0, v, w):
    if c > c0:
        return v if (c - c0) % 2 == 0 else 5
    return None


def ray_left(inp, out):
    return render(inp, lambda r, c, c0, v, w: (v if (c0 - c) % 2 == 0 else 5) if c < c0 else None)


def ray_both(inp, out):
    def f(r, c, c0, v, w):
        if c == c0:
            return None
        return v if abs(c - c0) % 2 == 0 else 5
    return render(inp, f)


def ray_down(inp, out):
    g = [row[:] for row in inp]
    h = len(inp)
    for r0, c, v in dots(inp):
        for r in range(r0 + 1, h):
            g[r][c] = v if (r - r0) % 2 == 0 else 5
    return g


def phase_swapped(inp, out):
    return render(inp, lambda r, c, c0, v, w: (5 if (c - c0) % 2 == 0 else v) if c > c0 else None)


def solid_dot_color(inp, out):
    return render(inp, lambda r, c, c0, v, w: v if c > c0 else None)


def solid_five(inp, out):
    return render(inp, lambda r, c, c0, v, w: 5 if c > c0 else None)


def stop_one_short(inp, out):
    return render(inp, lambda r, c, c0, v, w: right_alt(r, c, c0, v, w) if c < w - 1 else None)


def period_three(inp, out):
    return render(inp, lambda r, c, c0, v, w: (v if (c - c0) % 3 == 0 else 5) if c > c0 else None)


def only_first_dot(inp, out):
    g = render(inp, right_alt, only_first=True)
    return g


def gap_with_zero(inp, out):
    return render(inp, lambda r, c, c0, v, w: (v if (c - c0) % 2 == 0 else 0) if c > c0 else None)


def alt_color_8(inp, out):
    return render(inp, lambda r, c, c0, v, w: (v if (c - c0) % 2 == 0 else 8) if c > c0 else None)


def full_row_pattern(inp, out):
    return render(inp, lambda r, c, c0, v, w: (v if (c - c0) % 2 == 0 else 5) if c != c0 else None)


ALTERNATIVES = [
    ("rays go left from each dot instead of right", ray_left),
    ("rays go both left and right from each dot", ray_both),
    ("rays go down the dot's column instead of right along its row", ray_down),
    ("alternation phase is swapped: 5 first, then the dot color", phase_swapped),
    ("ray is solid in the dot's color, no 5s", solid_dot_color),
    ("ray is solid 5, no alternation", solid_five),
    ("ray stops one cell before the right edge", stop_one_short),
    ("ray repeats the dot color every third cell, 5 between", period_three),
    ("only the topmost-leftmost dot gets a ray", only_first_dot),
    ("ray alternates the dot color with background 0 instead of 5", gap_with_zero),
    ("ray alternates the dot color with 8 instead of 5", alt_color_8),
    ("alternating pattern fills the whole row on both sides of the dot", full_row_pattern),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(type(x) is int and 0 <= x <= 9 for r in g for x in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/97999447.json'))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
