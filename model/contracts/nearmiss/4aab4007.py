"""Near-miss rules for 4aab4007.

The input holds a diagonal-stripe pattern (constant along r+c) inside a border
(rows 0-2 and columns 0-2), with holes painted 0. The output fills each hole
with what the pattern or border has there.
"""
from pathlib import Path
import json
from collections import Counter

HOLE = 0


def copy(g):
    return [r[:] for r in g]


def holes(inp):
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == HOLE]


def in_pat(r, c):
    return r >= 3 and c >= 3


def components(cells):
    cells = set(cells)
    comps = []
    while cells:
        s = cells.pop()
        comp = [s]
        stack = [s]
        while stack:
            r, c = stack.pop()
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (r + d[0], c + d[1])
                if n in cells:
                    cells.remove(n)
                    comp.append(n)
                    stack.append(n)
        comps.append(comp)
    return comps


def unchanged(inp, out):
    return copy(inp)


def main_diagonal_copy(inp, out):
    """Stripes read as running along r-c instead of r+c."""
    h, w = len(inp), len(inp[0])
    g = copy(out)
    for r, c in holes(inp):
        if not in_pat(r, c):
            continue
        for k in range(1, max(h, w)):
            found = None
            for rr, cc in ((r - k, c - k), (r + k, c + k)):
                if 0 <= rr < h and 0 <= cc < w and in_pat(rr, cc) and inp[rr][cc] != HOLE:
                    found = inp[rr][cc]
                    break
            if found is not None:
                g[r][c] = found
                break
    return g


def column_stripes(inp, out):
    """Stripes read as vertical: hole takes the colour of the pattern's first row in that column."""
    g = copy(out)
    for r, c in holes(inp):
        if in_pat(r, c):
            g[r][c] = out[3][c]
    return g


def row_stripes(inp, out):
    """Stripes read as horizontal: hole takes the colour of the pattern's first column in that row."""
    g = copy(out)
    for r, c in holes(inp):
        if in_pat(r, c):
            g[r][c] = out[r][3]
    return g


def single_mode_colour(inp, out):
    """Every hole gets the commonest colour of the pattern area."""
    cnt = Counter(inp[r][c] for r in range(3, len(inp)) for c in range(3, len(inp[0]))
                  if inp[r][c] != HOLE)
    m = cnt.most_common(1)[0][0]
    g = copy(out)
    for r, c in holes(inp):
        g[r][c] = m
    return g


def leave_smallest_hole(inp, out):
    """Fill every hole region except the smallest."""
    comps = components(holes(inp))
    if len(comps) < 2:
        return None
    small = min(comps, key=len)
    g = copy(out)
    for r, c in small:
        g[r][c] = HOLE
    return g


def fill_largest_only(inp, out):
    """Fill only the largest hole region."""
    comps = components(holes(inp))
    if len(comps) < 2:
        return None
    big = max(comps, key=len)
    g = copy(inp)
    for r, c in big:
        g[r][c] = out[r][c]
    return g


def shifted_right(inp, out):
    """Fill is the correct pattern shifted one cell sideways."""
    w = len(inp[0])
    g = copy(out)
    for r, c in holes(inp):
        g[r][c] = out[r][c + 1] if c + 1 < w else out[r][c - 1]
    return g


def shifted_down(inp, out):
    """Fill is the correct pattern shifted one row."""
    h = len(inp)
    g = copy(out)
    for r, c in holes(inp):
        g[r][c] = out[r + 1][c] if r + 1 < h else out[r - 1][c]
    return g


def border_colour_fill(inp, out):
    """Holes are filled with the border line colour."""
    b = out[2][2]
    g = copy(out)
    for r, c in holes(inp):
        g[r][c] = b
    return g


def pattern_over_band(inp, out):
    """Holes in the border bands get the pattern colour instead of the band colour."""
    h, w = len(inp), len(inp[0])
    g = copy(out)
    changed = False
    for r, c in holes(inp):
        if in_pat(r, c):
            continue
        s = r + c
        for rr in range(3, h):
            cc = s - rr
            if 3 <= cc < w:
                g[r][c] = out[rr][cc]
                changed = True
                break
    return g if changed else None


ALTERNATIVES = [
    ("holes left as in the input (nothing filled)", unchanged),
    ("stripes read along r-c: hole copies nearest known cell on its main diagonal", main_diagonal_copy),
    ("stripes read as vertical: hole copies the pattern's first row in its column", column_stripes),
    ("stripes read as horizontal: hole copies the pattern's first column in its row", row_stripes),
    ("every hole filled with the pattern's commonest colour", single_mode_colour),
    ("all hole regions filled except the smallest", leave_smallest_hole),
    ("only the largest hole region filled", fill_largest_only),
    ("fill pattern shifted one column", shifted_right),
    ("fill pattern shifted one row", shifted_down),
    ("holes filled with the border line colour", border_colour_fill),
    ("holes in the border bands filled with pattern colours instead of band colours", pattern_over_band),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/4aab4007.json'))
    pairs = task['train']
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
