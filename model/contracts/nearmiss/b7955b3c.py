import json
from collections import Counter
from pathlib import Path


def _marks(inp, out):
    return [(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] != out[r][c]]


def _mark_color(inp, out):
    m = _marks(inp, out)
    return inp[m[0][0]][m[0][1]] if m else None


def _copy(g):
    return [row[:] for row in g]


def _centers(inp, mc):
    h, w = len(inp), len(inp[0])
    res = []
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if all(inp[r + dr][c + dc] == mc for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))):
                res.append((r, c))
    return res


def background_only(inp, out):
    mc = _mark_color(inp, out)
    bg = inp[0][0]
    g = _copy(inp)
    for r, c in _marks(inp, out):
        g[r][c] = bg
    return g


def keep_vertical_arms(inp, out):
    mc = _mark_color(inp, out)
    g = _copy(out)
    for r, c in _centers(inp, mc):
        g[r - 1][c] = mc
        g[r + 1][c] = mc
    return g


def keep_horizontal_arms(inp, out):
    mc = _mark_color(inp, out)
    g = _copy(out)
    for r, c in _centers(inp, mc):
        g[r][c - 1] = mc
        g[r][c + 1] = mc
    return g


def keep_centers(inp, out):
    mc = _mark_color(inp, out)
    g = _copy(out)
    for r, c in _centers(inp, mc):
        g[r][c] = mc
    return g


def _scan_fill(inp, out, dr, dc):
    mc = _mark_color(inp, out)
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c in _marks(inp, out):
        rr, cc = r, c
        while 0 <= rr < h and 0 <= cc < w and inp[rr][cc] == mc:
            rr += dr
            cc += dc
        if 0 <= rr < h and 0 <= cc < w:
            g[r][c] = inp[rr][cc]
        else:
            g[r][c] = inp[0][0]
    return g


def fill_from_left(inp, out):
    return _scan_fill(inp, out, 0, -1)


def fill_from_above(inp, out):
    return _scan_fill(inp, out, -1, 0)


def fill_from_right(inp, out):
    return _scan_fill(inp, out, 0, 1)


def plus_uniform_center(inp, out):
    mc = _mark_color(inp, out)
    g = _copy(out)
    for r, c in _centers(inp, mc):
        col = out[r][c]
        for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            g[r + dr][c + dc] = col
    return g


def most_common_color(inp, out):
    mc = _mark_color(inp, out)
    cnt = Counter(v for row in inp for v in row if v != mc)
    top = cnt.most_common(1)[0][0]
    g = _copy(inp)
    for r, c in _marks(inp, out):
        g[r][c] = top
    return g


def leave_marks_over_background(inp, out):
    mc = _mark_color(inp, out)
    bg = inp[0][0]
    g = _copy(out)
    for r, c in _marks(inp, out):
        if out[r][c] == bg:
            g[r][c] = mc
    return g


def _boxes(inp, mc):
    pos = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v != mc:
                pos.setdefault(v, []).append((r, c))
    boxes = {}
    for v, ps in pos.items():
        rs = [p[0] for p in ps]
        cs = [p[1] for p in ps]
        boxes[v] = (min(rs), max(rs), min(cs), max(cs))
    return boxes


def _by_box_area(inp, out, largest):
    mc = _mark_color(inp, out)
    boxes = _boxes(inp, mc)
    area = {v: (b[1] - b[0] + 1) * (b[3] - b[2] + 1) for v, b in boxes.items()}
    g = _copy(out)
    for r, c in _marks(inp, out):
        cands = [v for v, b in boxes.items() if b[0] <= r <= b[1] and b[2] <= c <= b[3]]
        if cands:
            g[r][c] = (max if largest else min)(cands, key=lambda v: area[v])
    return g


def smallest_box_wins(inp, out):
    return _by_box_area(inp, out, False)


def largest_box_wins(inp, out):
    return _by_box_area(inp, out, True)


def erase_plus_bounding_box(inp, out):
    """Mark treated as its 3x3 bounding square: corners also overwritten with the center's color."""
    mc = _mark_color(inp, out)
    g = _copy(out)
    for r, c in _centers(inp, mc):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                g[r + dr][c + dc] = out[r][c]
    return g


ALTERNATIVES = [
    ("every mark cell becomes the background color", background_only),
    ("only the centers of the plus marks are erased through; the vertical arms keep the mark color", keep_vertical_arms),
    ("the horizontal arms of each plus keep the mark color", keep_horizontal_arms),
    ("the center cell of each plus keeps the mark color", keep_centers),
    ("each mark cell takes the color of the first non-mark cell to its left", fill_from_left),
    ("each mark cell takes the color of the first non-mark cell above it", fill_from_above),
    ("each mark cell takes the color of the first non-mark cell to its right", fill_from_right),
    ("the whole plus takes the color found at its center", plus_uniform_center),
    ("every mark cell takes the commonest non-mark color of the input", most_common_color),
    ("marks lying over the background are left unerased", leave_marks_over_background),
    ("where several rectangles cover a mark cell, the one with the smallest box wins", smallest_box_wins),
    ("each plus is treated as a 3x3 square: its corners also take the center's color", erase_plus_bounding_box),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b7955b3c.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
