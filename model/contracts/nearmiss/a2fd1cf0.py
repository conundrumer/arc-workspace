from pathlib import Path
import json, sys


def marks(inp):
    pos = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v:
                pos[v] = (r, c)
    return pos[2], pos[3]


def copy(g):
    return [row[:] for row in g]


def seg(g, a, b, color, skip_ends=True):
    """Paint cells strictly between a and b (same row or column)."""
    (r1, c1), (r2, c2) = a, b
    if r1 == r2:
        for c in range(min(c1, c2) + 1, max(c1, c2)):
            g[r1][c] = color
    else:
        for r in range(min(r1, r2) + 1, max(r1, r2)):
            g[r][c1] = color


def l_path(inp, corner_of_2_row=True, color=8, paint_corner=True, legs=(True, True),
           overwrite_marks=False):
    two, three = marks(inp)
    g = copy(inp)
    corner = (two[0], three[1]) if corner_of_2_row else (three[0], two[1])
    if legs[0]:
        seg(g, two, corner, color)
    if legs[1]:
        seg(g, corner, three, color)
    if paint_corner and corner not in (two, three):
        g[corner[0]][corner[1]] = color
    if overwrite_marks:
        g[two[0]][two[1]] = color
        g[three[0]][three[1]] = color
    return g


def other_corner(inp, out):
    return l_path(inp, corner_of_2_row=False)


def wrong_color_2(inp, out):
    return l_path(inp, color=2)


def wrong_color_3(inp, out):
    return l_path(inp, color=3)


def overwrite(inp, out):
    return l_path(inp, overwrite_marks=True)


def only_leg_from_2(inp, out):
    return l_path(inp, legs=(True, False))


def only_leg_from_3(inp, out):
    return l_path(inp, legs=(False, True))


def no_corner(inp, out):
    return l_path(inp, paint_corner=False)


def both_corners(inp, out):
    g = l_path(inp)
    h = l_path(inp, corner_of_2_row=False)
    for r in range(len(g)):
        for c in range(len(g[0])):
            if h[r][c] == 8:
                g[r][c] = 8
    return g


def bbox_fill(inp, out):
    two, three = marks(inp)
    g = copy(inp)
    for r in range(min(two[0], three[0]), max(two[0], three[0]) + 1):
        for c in range(min(two[1], three[1]), max(two[1], three[1]) + 1):
            if g[r][c] == 0:
                g[r][c] = 8
    return g


def full_lines(inp, out):
    """Lines through both markers run to the grid edge."""
    two, three = marks(inp)
    g = copy(inp)
    H, W = len(g), len(g[0])
    for c in range(W):
        if g[two[0]][c] == 0:
            g[two[0]][c] = 8
    for r in range(H):
        if g[r][three[1]] == 0:
            g[r][three[1]] = 8
    return g


def diagonal_then_straight(inp, out):
    """Path leaves 2 diagonally toward 3, then runs straight."""
    two, three = marks(inp)
    g = copy(inp)
    r, c = two
    dr = 1 if three[0] > r else -1
    dc = 1 if three[1] > c else -1
    while (r + dr, c + dc) != three and r + dr != three[0] and c + dc != three[1]:
        r += dr
        c += dc
        g[r][c] = 8
    return g


def path_off_by_one(inp, out):
    """Corner is shifted one cell along the 2 row away from 3's column."""
    two, three = marks(inp)
    g = copy(inp)
    W = len(g[0])
    dc = 1 if three[1] > two[1] else -1
    cc = three[1] + dc
    if not 0 <= cc < W:
        cc = three[1] - dc
    corner = (two[0], cc)
    seg(g, two, corner, 8)
    g[corner[0]][corner[1]] = 8
    if corner[1] != three[1]:
        r1, r2 = sorted((corner[0], three[0]))
        for r in range(r1 + 1, r2 + 1):
            if g[r][cc] == 0:
                g[r][cc] = 8
    return g


ALTERNATIVES = [
    ("corner on the row of the 3 and column of the 2 (legs swapped)", other_corner),
    ("path painted in color 2 instead of 8", wrong_color_2),
    ("path painted in color 3 instead of 8", wrong_color_3),
    ("path also overwrites the two marker cells", overwrite),
    ("only the leg from the 2 to the corner is drawn", only_leg_from_2),
    ("only the leg from the 3 to the corner is drawn", only_leg_from_3),
    ("corner cell left unpainted", no_corner),
    ("both possible L paths drawn", both_corners),
    ("whole bounding rectangle of the two markers filled", bbox_fill),
    ("row of the 2 and column of the 3 drawn to the grid edges", full_lines),
    ("path leaves the 2 diagonally, then runs straight", diagonal_then_straight),
    ("vertical leg runs one column past the 3", path_off_by_one),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    path = str(Path(__file__).resolve().parents[3] / 'data/tasks/a2fd1cf0.json')
    train = json.load(open(path))["train"]
    print("task a2fd1cf0, readings", len(ALTERNATIVES), "pairs", len(train))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, repr(e))
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
