"""Near-miss rules for ARC task 9b30e358 (the ink unit repeats upward to the edge)."""
import json
from collections import Counter
from pathlib import Path


def _info(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != bg]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return h, w, bg, r0, r1, c0, c1


def _copy(g):
    return [list(r) for r in g]


def _tile_up(inp, unit, stride=None, phase_top=False):
    """Fill rows above the ink with copies of `unit` (list of rows)."""
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    k = len(unit)
    g = _copy(inp)
    for r in range(r0 - 1, -1, -1):
        g[r] = list(unit[(r - r0) % k])
    return g


def unit_of(inp):
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    return [list(r) for r in inp[r0:r1 + 1]]


def unchanged(inp, out):
    return _copy(inp)


def stop_one_line_short(inp, out):
    g = _copy(out)
    g[0] = list(inp[0])
    return g


def mirrored_copies(inp, out):
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    u = unit_of(inp)
    k = len(u)
    g = _copy(inp)
    for r in range(r0 - 1, -1, -1):
        g[r] = list(u[(r0 - 1 - r) % k])
    return g


def reflected_alternating(inp, out):
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    u = unit_of(inp)
    k = len(u)
    g = _copy(inp)
    for r in range(r0 - 1, -1, -1):
        j, i = divmod(r0 - 1 - r, k)
        g[r] = list(u[i] if j % 2 == 0 else u[k - 1 - i])
    return g


def unit_short_by_one(inp, out):
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    u = unit_of(inp)[:-1]
    k = len(u)
    g = _copy(inp)
    for r in range(r0 - 1, -1, -1):
        g[r] = list(u[(r - r0) % k])
    return g


def unit_long_by_one(inp, out):
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    u = [[bg] * w] + unit_of(inp)
    k = len(u)
    g = _copy(inp)
    for r in range(r0 - 1, -1, -1):
        g[r] = list(u[(r - r0 + 1) % k])
    return g


def gap_between_copies(inp, out):
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    u = unit_of(inp) + [[bg] * w]
    k = len(u)
    g = _copy(inp)
    for r in range(r0 - 1, -1, -1):
        g[r] = list(u[(r - r0) % k])
    return g


def swap_ink_colors_in_copies(inp, out):
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    cols = sorted({v for r in inp for v in r if v != bg})
    if len(cols) != 2:
        return None
    a, b = cols
    sw = {a: b, b: a, bg: bg}
    g = _copy(out)
    for r in range(r0):
        g[r] = [sw[v] for v in g[r]]
    return g


def top_row_stretched(inp, out):
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    g = _copy(inp)
    for r in range(r0):
        g[r] = list(inp[r0])
    return g


def repeat_rightward(inp, out):
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    k = c1 - c0 + 1
    g = _copy(inp)
    for r in range(r0, r1 + 1):
        for c in range(c1 + 1, w):
            g[r][c] = inp[r][c0 + (c - c0) % k]
    return g


def ink_only_unit_rows_full_width(inp, out):
    # unit taken as the rows of the ink but the copies repeat downward past the ink
    # (wrong direction): ink stays, copies are laid downward from the ink's bottom, clipped
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    u = unit_of(inp)
    k = len(u)
    g = _copy(inp)
    for r in range(r1 + 1, h):
        g[r] = list(u[(r - r0) % k])
    for r in range(r0 - 1, -1, -1):
        g[r] = [bg] * w
    return g


def bg_cells_left_unpainted_in_copies(inp, out):
    # copies paste only ink cells on the columns of the first copy, keeping original columns
    # outside the ink's first column: drop the first ink column from copies
    h, w, bg, r0, r1, c0, c1 = _info(inp)
    g = _copy(out)
    for r in range(r0):
        g[r][c0] = bg
    return g


ALTERNATIVES = [
    ("input returned unchanged", unchanged),
    ("copies stop one line short of the grid edge", stop_one_line_short),
    ("each copy is flipped vertically", mirrored_copies),
    ("copies alternate between the unit and its vertical reflection", reflected_alternating),
    ("unit is one line shorter than the ink extent (last line dropped)", unit_short_by_one),
    ("unit is one line longer than the ink extent (a background line added)", unit_long_by_one),
    ("copies are separated by one background line", gap_between_copies),
    ("ink colors swapped in the copies", swap_ink_colors_in_copies),
    ("every line above the ink repeats the ink's nearest line", top_row_stretched),
    ("unit repeats rightward along the columns, not toward the grid edge above", repeat_rightward),
    ("unit repeats away from the edge it touches (downward), the upper area is cleared", ink_only_unit_rows_full_width),
    ("first ink column left blank in the copies", bg_cells_left_unpainted_in_copies),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/9b30e358.json").read_text())
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
