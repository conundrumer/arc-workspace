import json
from pathlib import Path


def _make(inp, f):
    return [[f(r, c) for c in range(len(inp[0]))] for r in range(len(inp))]


def dots_even_even(inp, out):
    # Dot lattice offset by one: dots at even rows and even columns.
    return _make(inp, lambda r, c: 0 if r % 2 == 0 and c % 2 == 0 else 1)


def checkerboard(inp, out):
    # Alternating cells everywhere instead of isolated dots.
    return _make(inp, lambda r, c: 0 if (r + c) % 2 == 1 else 1)


def row_stripes(inp, out):
    # Whole odd rows are dots.
    return _make(inp, lambda r, c: 0 if r % 2 == 1 else 1)


def col_stripes(inp, out):
    # Whole odd columns are dots.
    return _make(inp, lambda r, c: 0 if c % 2 == 1 else 1)


def period_three(inp, out):
    # Tile gap of 2: dots every third row and column starting at 1.
    return _make(inp, lambda r, c: 0 if r % 3 == 1 and c % 3 == 1 else 1)


def swapped_colors(inp, out):
    # Background and dot colors exchanged.
    return [[1 - v if v in (0, 1) else v for v in row] for row in out]


def background_wrong_color(inp, out):
    # Background takes color 2 instead of the fresh color 1.
    return [[2 if v == 1 else v for v in row] for row in out]


def cropped_border(inp, out):
    # Output is the interior only, with the outer ring removed.
    return [row[1:-1] for row in out[1:-1]]


def last_dot_row_missing(inp, out):
    # The last row of dots is left unfilled.
    n = len(out)
    return [[1 if r == n - 2 else v for v in row] for r, row in enumerate(out)]


def last_dot_col_missing(inp, out):
    # The last column of dots is left unfilled.
    m = len(out[0])
    return [[1 if c == m - 2 else v for c, v in enumerate(row)] for row in out]


def dots_odd_row_even_col(inp, out):
    # Dot lattice shifted horizontally by one.
    return _make(inp, lambda r, c: 0 if r % 2 == 1 and c % 2 == 0 else 1)


def unchanged_input(inp, out):
    # No pattern is drawn.
    return [list(row) for row in inp]


ALTERNATIVES = [
    ("dots at even rows and even columns (phase off by one)", dots_even_even),
    ("checkerboard of alternating cells", checkerboard),
    ("dots fill whole odd rows (horizontal stripes)", row_stripes),
    ("dots fill whole odd columns (vertical stripes)", col_stripes),
    ("tile gap 2: dots every third row and column", period_three),
    ("background and dot colors swapped", swapped_colors),
    ("background drawn in color 2 instead of 1", background_wrong_color),
    ("outer border ring cropped off", cropped_border),
    ("last row of dots left unfilled", last_dot_row_missing),
    ("last column of dots left unfilled", last_dot_col_missing),
    ("dots at odd rows and even columns (horizontal shift)", dots_odd_row_even_col),
    ("input returned unchanged", unchanged_input),
]


def _valid(g):
    return (
        isinstance(g, list) and len(g) > 0
        and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/332efdb3.json'))
    train = task["train"]
    print("pairs", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
