from pathlib import Path
import json
from collections import Counter

AXES = {"\\": (1, 1), "/": (1, -1)}


def bg_of(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def marks_of(inp):
    bg = bg_of(inp)
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != bg]


def axes_of(inp, r, c):
    """Axes along which cell (r, c) has a mark neighbour."""
    bg = bg_of(inp)
    h, w = len(inp), len(inp[0])
    res = []
    for name, (dr, dc) in AXES.items():
        for s in (1, -1):
            rr, cc = r + s * dr, c + s * dc
            if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] != bg:
                res.append(name)
                break
    return res


def copy(g):
    return [row[:] for row in g]


def paint_colors(inp, out):
    """Paint colors used by the true output on mark cells, major first."""
    cnt = Counter(out[r][c] for r, c in marks_of(inp) if out[r][c] != inp[r][c])
    return [k for k, _ in cnt.most_common()]


def swap_colors(inp, out):
    cols = paint_colors(inp, out)
    if len(cols) < 2:
        return None
    a, b = cols[0], cols[1]
    return [[b if v == a else a if v == b else v for v in row] for row in out]


def all_major(inp, out):
    cols = paint_colors(inp, out)
    if not cols:
        return None
    g = copy(inp)
    for r, c in marks_of(inp):
        g[r][c] = cols[0]
    return g


def all_minor(inp, out):
    cols = paint_colors(inp, out)
    if len(cols) < 2:
        return None
    g = copy(inp)
    for r, c in marks_of(inp):
        g[r][c] = cols[1]
    return g


def leave_minor(inp, out):
    cols = paint_colors(inp, out)
    if len(cols) < 2:
        return None
    g = copy(out)
    for r, c in marks_of(inp):
        if out[r][c] == cols[1]:
            g[r][c] = inp[r][c]
    return g


def leave_major(inp, out):
    cols = paint_colors(inp, out)
    if not cols:
        return None
    g = copy(out)
    for r, c in marks_of(inp):
        if out[r][c] == cols[0]:
            g[r][c] = inp[r][c]
    return g


def fixed_axis(a_color, b_color):
    def f(inp, out):
        cols = paint_colors(inp, out)
        if len(cols) < 2:
            return None
        pal = {"\\": cols[a_color], "/": cols[b_color]}
        g = copy(inp)
        for r, c in marks_of(inp):
            ax = axes_of(inp, r, c)
            if ax:
                g[r][c] = pal[ax[0]]
        return g
    return f


def mirror_out(inp, out):
    return [row[::-1] for row in out]


def shift_down(inp, out):
    g = copy(inp)
    h = len(inp)
    for r, c in marks_of(inp):
        if r + 1 < h:
            g[r + 1][c] = out[r][c]
    return g


def extend_lines(inp, out):
    h, w = len(inp), len(inp[0])
    g = copy(out)
    for r, c in marks_of(inp):
        col = out[r][c]
        for ax in axes_of(inp, r, c):
            dr, dc = AXES[ax]
            for s in (1, -1):
                rr, cc = r, c
                while 0 <= rr < h and 0 <= cc < w:
                    if g[rr][cc] == inp[rr][cc] and inp[rr][cc] == bg_of(inp):
                        g[rr][cc] = col
                    rr += s * dr
                    cc += s * dc
    return g


def split_by_half(inp, out):
    cols = paint_colors(inp, out)
    if len(cols) < 2:
        return None
    g = copy(inp)
    h = len(inp)
    for r, c in marks_of(inp):
        g[r][c] = cols[0] if r < h // 2 else cols[1]
    return g


def unchanged(inp, out):
    return copy(inp)


def short_streaks_unpainted(inp, out):
    """Cells whose diagonal run is shorter than 4 stay unpainted."""
    bg = bg_of(inp)
    h, w = len(inp), len(inp[0])
    g = copy(out)
    for r, c in marks_of(inp):
        best = 0
        for ax in axes_of(inp, r, c):
            dr, dc = AXES[ax]
            n = 1
            for s in (1, -1):
                rr, cc = r + s * dr, c + s * dc
                while 0 <= rr < h and 0 <= cc < w and inp[rr][cc] != bg:
                    n += 1
                    rr += s * dr
                    cc += s * dc
            best = max(best, n)
        if best < 4:
            g[r][c] = inp[r][c]
    return g


ALTERNATIVES = [
    ("the two paint colors are exchanged between the axes", swap_colors),
    ("every mark gets the major-axis color", all_major),
    ("every mark gets the minor-axis color", all_minor),
    ("minor-axis marks are left unpainted", leave_minor),
    ("major-axis marks are left unpainted", leave_major),
    ("fixed axis colors: backslash gets major color, slash gets minor color", fixed_axis(0, 1)),
    ("fixed axis colors: backslash gets minor color, slash gets major color", fixed_axis(1, 0)),
    ("output is mirrored left to right", mirror_out),
    ("paint lands one row below each mark", shift_down),
    ("paint extends along the whole diagonal through each mark", extend_lines),
    ("color depends on grid half: top rows major, bottom rows minor", split_by_half),
    ("marks in diagonal runs shorter than 4 are left unpainted", short_streaks_unpainted),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/1d61978c.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
