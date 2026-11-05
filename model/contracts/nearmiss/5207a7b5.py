import json
from pathlib import Path

BAR = 5


def _bar(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v == BAR]
    c = cells[0][1]
    rows = [r for r, _ in cells]
    return c, min(rows), max(rows)


def _render(inp, left=8, right=6, lrise=2, rrise=2, loff=2, roff=-2,
            anchor_top=True, bar_color=BAR):
    """Left side grows from bar length + loff by lrise per column away from the bar;
    right side starts at bar length + roff and changes by -rrise per column."""
    h, w = len(inp), len(inp[0])
    bc, r0, r1 = _bar(inp)
    n = r1 - r0 + 1
    g = [[0] * w for _ in range(h)]
    for r in range(r0, r1 + 1):
        g[r][bc] = bar_color

    def fill(c, length, color):
        if length <= 0:
            return
        if anchor_top:
            rows = range(r0, min(h, r0 + length))
        else:
            rows = range(max(0, r1 - length + 1), r1 + 1)
        for r in rows:
            g[r][c] = color

    for c in range(bc):
        d = bc - c
        fill(c, n + loff + lrise * (d - 1), left)
    for c in range(bc + 1, w):
        d = c - bc
        fill(c, n + roff - rrise * (d - 1), right)
    return g


def _copy(g):
    return [row[:] for row in g]


def rise_one(inp, out):
    return _render(inp, lrise=1, rrise=1, loff=1, roff=-1)


def rise_three(inp, out):
    return _render(inp, lrise=3, rrise=3, loff=3, roff=-3)


def no_offset_left(inp, out):
    return _render(inp, loff=0)


def swapped_colors(inp, out):
    return _render(inp, left=6, right=8)


def right_grows(inp, out):
    return _render(inp, rrise=-2, roff=2)


def anchored_bottom(inp, out):
    return _render(inp, anchor_top=False)


def left_only(inp, out):
    g = _copy(out)
    for row in g:
        for c, v in enumerate(row):
            if v == 6:
                row[c] = 0
    return g


def right_only(inp, out):
    g = _copy(out)
    for row in g:
        for c, v in enumerate(row):
            if v == 8:
                row[c] = 0
    return g


def left_rectangle(inp, out):
    bc, r0, r1 = _bar(inp)
    g = _copy(out)
    for r in range(len(g)):
        for c in range(bc):
            g[r][c] = 8 if r0 <= r <= r1 else 0
    return g


def mixed_rise(inp, out):
    return _render(inp, lrise=2, rrise=1, loff=2, roff=-1)


def bar_overwritten(inp, out):
    g = _copy(out)
    for row in g:
        for c, v in enumerate(row):
            if v == BAR:
                row[c] = 8
    return g


def mirrored_slant(inp, out):
    # 8 side shrinks and 6 side grows: slant runs the other way
    g = _render(inp, left=6, right=8, lrise=2, rrise=-2, loff=-2, roff=2)
    return g


ALTERNATIVES = [
    ("slant rises 1 cell per column instead of 2", rise_one),
    ("slant rises 3 cells per column instead of 2", rise_three),
    ("8 side starts at bar length, missing the 2-cell extension beside the bar", no_offset_left),
    ("colors of the two sides swapped (6 left, 8 right)", swapped_colors),
    ("6 side grows away from the bar like the 8 side", right_grows),
    ("slant anchored at the bar's bottom end, growing upward", anchored_bottom),
    ("only the 8 side is drawn", left_only),
    ("only the 6 side is drawn", right_only),
    ("8 side is a plain rectangle the height of the bar", left_rectangle),
    ("6 side shrinks 1 per column while 8 side grows 2", mixed_rise),
    ("bar cells repainted as 8", bar_overwritten),
    ("slant direction mirrored: 6 grows on the left, 8 shrinks on the right", mirrored_slant),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/5207a7b5.json"))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
