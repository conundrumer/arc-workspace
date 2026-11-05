import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    col = max(range(w), key=lambda c: sum(1 for r in range(h) if inp[r][c] != inp[0][0] and inp[r][c] == 8))
    col = max(range(w), key=lambda c: Counter(inp[r][c] for r in range(h))[8])
    marks = {r: inp[r][0] for r in range(h) if inp[r][0] != bg}
    return h, w, bg, col, marks


def _field(h, marks, pick):
    """pick(rowindex, marks) -> color or None"""
    return {r: pick(r, marks) for r in range(h) if r not in marks}


def _build(inp, pick, cross=8, line_fill=1, div_fill=1, keep_mark_color=False,
           div_color_keep=False):
    h, w, bg, c, marks = _parse(inp)
    f = _field(h, marks, pick)
    g = []
    for r in range(h):
        row = []
        for x in range(w):
            if r in marks:
                if x == c:
                    v = cross
                else:
                    v = marks[r] if keep_mark_color else line_fill
            elif x == c:
                v = 8 if div_color_keep else (f[r] if div_fill is None else div_fill)
            else:
                v = f[r]
            row.append(v)
        g.append(row)
    return g


def _nearest(r, marks, side=None, far=False, tie="one", maxd=None):
    cands = []
    for m, col in marks.items():
        if side == "above" and m > r:
            continue
        if side == "below" and m < r:
            continue
        cands.append((abs(m - r), m, col))
    if not cands:
        return 7
    key = max if far else min
    d = key(c[0] for c in cands)
    if maxd is not None and d > maxd:
        return 7
    best = sorted(c for c in cands if c[0] == d)
    cols = {c[2] for c in best}
    if len(cols) == 1 or len(best) == 1:
        return best[0][2]
    if tie == "one":
        return 1
    if tie == "up":
        return best[0][2]
    if tie == "down":
        return best[-1][2]
    return 7


def _wrap(out, g):
    return None if g == out else g


def above_only(inp, out):
    return _wrap(out, _build(inp, lambda r, m: _nearest(r, m, side="above")))


def below_only(inp, out):
    return _wrap(out, _build(inp, lambda r, m: _nearest(r, m, side="below")))


def tie_up(inp, out):
    return _wrap(out, _build(inp, lambda r, m: _nearest(r, m, tie="up")))


def tie_down(inp, out):
    return _wrap(out, _build(inp, lambda r, m: _nearest(r, m, tie="down")))


def tie_bg(inp, out):
    return _wrap(out, _build(inp, lambda r, m: _nearest(r, m, tie="bg")))


def farthest(inp, out):
    return _wrap(out, _build(inp, lambda r, m: _nearest(r, m, far=True)))


def crossing_rarest(inp, out):
    return _wrap(out, _build(inp, lambda r, m: _nearest(r, m), cross=1))


def marks_keep_color(inp, out):
    return _wrap(out, _build(inp, lambda r, m: _nearest(r, m), keep_mark_color=True))


def divider_follows_field(inp, out):
    return _wrap(out, _build(inp, lambda r, m: _nearest(r, m), div_fill=None))


def divider_keeps_input_color(inp, out):
    return _wrap(out, _build(inp, lambda r, m: _nearest(r, m), div_color_keep=True))


def spread_one_row(inp, out):
    return _wrap(out, _build(inp, lambda r, m: _nearest(r, m, maxd=1)))


def lines_take_field_color(inp, out):
    # marked lines get the color of the nearest other marked line instead of 1
    h, w, bg, c, marks = _parse(inp)
    if len(marks) < 2:
        return None
    g = [row[:] for row in out]
    for r, col in marks.items():
        others = {m: k for m, k in marks.items() if m != r}
        k = _nearest(r, others)
        for x in range(w):
            if x != c:
                g[r][x] = k
    return _wrap(out, g)


ALTERNATIVES = [
    ("Field rows take the color of the nearest marked line above only", above_only),
    ("Field rows take the color of the nearest marked line below only", below_only),
    ("A tie between two marked lines goes to the upper line", tie_up),
    ("A tie between two marked lines goes to the lower line", tie_down),
    ("A tie between two marked lines leaves the background color", tie_bg),
    ("Field rows take the color of the farthest marked line", farthest),
    ("Crossings take the rarest input color 1 instead of the divider color", crossing_rarest),
    ("Marked lines keep their own color instead of becoming 1", marks_keep_color),
    ("Divider column cells between lines take the field color instead of 1", divider_follows_field),
    ("Divider column cells between lines keep the input divider color 8", divider_keeps_input_color),
    ("Each marked line colors only the rows adjacent to it, the rest stay background", spread_one_row),
    ("Marked lines take the color of the nearest other marked line", lines_take_field_color),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/332202d5.json').read_text())
    train = task["train"]
    print("pairs", len(train))
    for desc, fn in ALTERNATIVES:
        n = sum(1 for p in train if (g := fn(p["input"], p["output"])) is not None and _valid(g, p["output"]))
        print(n, desc)
