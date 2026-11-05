import json
from pathlib import Path

FIELD, MARK, CENTER, RIM = 5, 2, 4, 7


def _copy(g):
    return [r[:] for r in g]


def _centers(out):
    h, w = len(out), len(out[0])
    return [(r, c) for r in range(h) for c in range(w) if out[r][c] == CENTER]


def _window(r, c):
    return [(r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)]


def _inb(g, r, c):
    return 0 <= r < len(g) and 0 <= c < len(g[0])


def _candidates(inp):
    """All 3x3 windows with a field center, only field/mark cells, and at least one mark."""
    h, w = len(inp), len(inp[0])
    res = []
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if inp[r][c] != FIELD:
                continue
            cells = _window(r, c)
            vals = [inp[a][b] for a, b in cells]
            if all(v in (FIELD, MARK) for v in vals) and MARK in vals:
                res.append((r, c, vals.count(MARK)))
    return res


def _paint(g, r, c):
    for a, b in _window(r, c):
        if not _inb(g, a, b):
            continue
        if (a, b) == (r, c):
            if g[a][b] == FIELD:
                g[a][b] = CENTER
        elif g[a][b] == FIELD:
            g[a][b] = RIM


def center_as_rim(inp, out):
    return [[RIM if v == CENTER else v for v in row] for row in out]


def rim_as_center(inp, out):
    return [[CENTER if v == RIM else v for v in row] for row in out]


def colors_swapped(inp, out):
    sw = {CENTER: RIM, RIM: CENTER}
    return [[sw.get(v, v) for v in row] for row in out]


def center_only(inp, out):
    return [[FIELD if v == RIM else v for v in row] for row in out]


def rim_only(inp, out):
    return [[FIELD if v == CENTER else v for v in row] for row in out]


def marks_repainted(inp, out):
    g = _copy(out)
    for r, c in _centers(out):
        for a, b in _window(r, c):
            if inp[a][b] == MARK:
                g[a][b] = RIM
    return g


def corners_unpainted(inp, out):
    g = _copy(out)
    for r, c in _centers(out):
        for dr in (-1, 1):
            for dc in (-1, 1):
                if g[r + dr][c + dc] == RIM:
                    g[r + dr][c + dc] = FIELD
    return g


def last_square_missed(inp, out):
    cs = _centers(out)
    g = _copy(out)
    r, c = cs[-1]
    for a, b in _window(r, c):
        g[a][b] = inp[a][b]
    return g


def window_shifted_down(inp, out):
    g = _copy(inp)
    for r, c in _centers(out):
        _paint(g, r + 1, c)
    return g


def all_windows_painted(inp, out):
    g = _copy(inp)
    for r, c, _ in _candidates(inp):
        _paint(g, r, c)
    return g


def fewest_marks_wins(inp, out):
    cands = sorted(_candidates(inp), key=lambda t: (t[2], t[0], t[1]))
    used = set()
    g = _copy(inp)
    for r, c, _ in cands:
        cells = set(_window(r, c))
        if cells & used:
            continue
        used |= cells
        _paint(g, r, c)
    return g


def cropped_last_row_col(inp, out):
    return [row[:-1] for row in out[:-1]]


ALTERNATIVES = [
    ("square center painted with the rim color instead of its own color", center_as_rim),
    ("square rim painted with the center color instead of its own color", rim_as_center),
    ("center and rim colors swapped", colors_swapped),
    ("only the center painted, rim cells left as field", center_only),
    ("only the rim painted, center left as field", rim_only),
    ("marks inside squares repainted with the rim color", marks_repainted),
    ("only the four edge-adjacent rim cells painted, corners left", corners_unpainted),
    ("last square in scan order left unpainted", last_square_missed),
    ("each square painted one row too low", window_shifted_down),
    ("every candidate window painted, overlaps not resolved", all_windows_painted),
    ("among overlapping windows the one with fewest marks kept", fewest_marks_wins),
    ("output cropped by one row and one column", cropped_last_row_col),
]


def _valid(g, true):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if any(len(r) != len(g[0]) or len(r) == 0 for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != true


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/9caba7c3.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
