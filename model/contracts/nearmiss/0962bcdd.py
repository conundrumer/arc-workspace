import json
from pathlib import Path

ORTH = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def markers(inp):
    h, w = len(inp), len(inp[0])
    found = []
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            cc = inp[r][c]
            if cc == 0:
                continue
            arms = [inp[r + dr][c + dc] for dr, dc in ORTH]
            if arms[0] != 0 and arms[0] != cc and all(a == arms[0] for a in arms):
                found.append((r, c, cc, arms[0]))
    return found


def render(inp, orth_r=2, diag_r=2, orth_col="arm", diag_col="center",
           orth_start=1, diag_start=1, ms=None, center_col=None):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    ms = markers(inp) if ms is None else ms
    for r, c, cc, ac in ms:
        col = {"arm": ac, "center": cc}
        for dirs, rad, start, which in ((ORTH, orth_r, orth_start, orth_col),
                                         (DIAG, diag_r, diag_start, diag_col)):
            for dr, dc in dirs:
                for k in range(start, rad + 1):
                    y, x = r + dr * k, c + dc * k
                    if 0 <= y < h and 0 <= x < w:
                        g[y][x] = col[which]
        if center_col is not None:
            g[r][c] = col[center_col]
    return g


def radius_one(inp, out):
    return render(inp, orth_r=1, diag_r=1)


def to_edge(inp, out):
    n = max(len(inp), len(inp[0]))
    return render(inp, orth_r=n)


def swapped(inp, out):
    return render(inp, orth_col="center", diag_col="arm")


def no_diag(inp, out):
    return render(inp, diag_r=0)


def diag_only(inp, out):
    return render(inp, orth_r=0)


def diag_radius_three(inp, out):
    return render(inp, diag_r=3)


def all_arm_color(inp, out):
    return render(inp, diag_col="arm")


def all_center_color(inp, out):
    return render(inp, orth_col="center")


def first_marker_only(inp, out):
    ms = markers(inp)
    if len(ms) < 2:
        return None
    return render(inp, ms=ms[:1])


def diag_far_only(inp, out):
    return render(inp, diag_start=2)


def orth_only_outer_diag_one(inp, out):
    return render(inp, orth_r=2, diag_r=1)


def center_recolored(inp, out):
    return render(inp, center_col="arm")


def diag_to_edge(inp, out):
    n = max(len(inp), len(inp[0]))
    return render(inp, diag_r=n)


ALTERNATIVES = [
    ("growth radius 1 instead of 2 in all directions", radius_one),
    ("orthogonal arms extend to the grid edge", to_edge),
    ("arm and center colors swapped in the growth", swapped),
    ("only the orthogonal arms are extended; no diagonals", no_diag),
    ("only the diagonals are drawn; arms not extended", diag_only),
    ("diagonals reach radius 3 instead of 2", diag_radius_three),
    ("all added cells use the arm color", all_arm_color),
    ("all added cells use the center color", all_center_color),
    ("only the first marker grows; the others stay as in the input", first_marker_only),
    ("diagonals skip the adjacent cell and start at distance 2", diag_far_only),
    ("diagonals reach only radius 1 while arms reach 2", orth_only_outer_diag_one),
    ("the marker center is repainted in the arm color", center_recolored),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/0962bcdd.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs), "readings", len(ALTERNATIVES))
    counts = []
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        counts.append(n)
        print(n, desc)
    print(counts)
