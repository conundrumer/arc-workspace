import json
from pathlib import Path

VERT = 2


def points(inp):
    return [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v]


def render(inp, vert_colors, horiz_first=True, bg=0):
    """Draw lines: colors in vert_colors are columns, other colors are rows."""
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    pts = points(inp)
    verts = [p for p in pts if p[2] in vert_colors]
    hors = [p for p in pts if p[2] not in vert_colors]
    layers = [verts, hors] if horiz_first else [hors, verts]
    for layer in layers:
        for r, c, v in layer:
            if layer is verts:
                for i in range(h):
                    g[i][c] = v
            else:
                for j in range(w):
                    g[r][j] = v
    return g


def vertical_on_top(inp, out):
    return render(inp, {VERT}, horiz_first=False)  # horizontals drawn first, then 2 over them


def two_is_horizontal(inp, out):
    return render(inp, {1, 3}, horiz_first=False)


def swap_orientation(inp, out):
    return render(inp, {1, 3}, horiz_first=True)


def rows_only_to_the_right(inp, out):
    g = [row[:] for row in out]
    for r, c, v in points(inp):
        if v != VERT:
            for j in range(c):
                if out[r][j] == v:
                    g[r][j] = 0
    return g


def columns_only_downward(inp, out):
    g = [row[:] for row in out]
    for r, c, v in points(inp):
        if v == VERT:
            for i in range(r):
                if g[i][c] == v:
                    g[i][c] = 0
    return g


def only_first_row_color(inp, out):
    # Only the topmost horizontal-line point is drawn; other rows stay as the vertical lines only.
    pts = sorted(p for p in points(inp) if p[2] != VERT)
    h = [[0] * len(inp[0]) for _ in inp]
    for r, c, v in points(inp):
        if v == VERT:
            h[r][c] = v
    g = render(h, {VERT})
    r, c, v = pts[0]
    g[r] = [v] * len(g[r])
    return g


def lines_shifted_down(inp, out):
    g = [row[:] for row in out]
    h = len(out)
    for r, c, v in points(inp):
        if v != VERT:
            for j in range(len(out[0])):
                g[r][j] = out[r - 1][j] if r > 0 else out[r][j]
    return g


def crossings_background(inp, out):
    g = [row[:] for row in out]
    rows = {r for r, c, v in points(inp) if v != VERT}
    cols = {c for r, c, v in points(inp) if v == VERT}
    for r in rows:
        for c in cols:
            g[r][c] = 0
    return g


def swap_1_and_3(inp, out):
    m = {1: 3, 3: 1}
    return [[m.get(v, v) for v in row] for row in out]


def plus_radius_one(inp, out):
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for r, c, v in points(inp):
        for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                g[rr][cc] = v
    return g


def transposed_output(inp, out):
    return [list(col) for col in zip(*out)]


def vertical_line_one_column_right(inp, out):
    g = [row[:] for row in out]
    w = len(out[0])
    for r, c, v in points(inp):
        if v == VERT:
            for i in range(len(out)):
                if out[i][c] == v and c + 1 < w:
                    g[i][c] = 0
                    g[i][c + 1] = v
    return g


ALTERNATIVES = [
    ("vertical 2 lines drawn over the horizontal lines at crossings", vertical_on_top),
    ("color 2 treated as a horizontal line, 1 and 3 as vertical", two_is_horizontal),
    ("orientations swapped: 1 and 3 vertical, 2 horizontal, 2 on top", swap_orientation),
    ("horizontal lines extend only from their point to the right", rows_only_to_the_right),
    ("vertical line extends only from its point downward", columns_only_downward),
    ("only the topmost horizontal-line point is drawn", only_first_row_color),
    ("horizontal lines drawn one row too high", lines_shifted_down),
    ("crossing cells left as background", crossings_background),
    ("colors 1 and 3 swapped", swap_1_and_3),
    ("each point makes only a plus of radius one", plus_radius_one),
    ("true output transposed", transposed_output),
    ("vertical line drawn one column to the right", vertical_line_one_column_right),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/178fcbfb.json").read_text())
    train = task["train"]
    print("pairs", len(train), "readings", len(ALTERNATIVES))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            n += _valid(g, p["output"])
        print(f"{n}/{len(train)}  {desc}")
