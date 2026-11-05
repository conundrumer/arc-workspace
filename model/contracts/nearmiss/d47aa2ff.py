"""Near-miss readings for d47aa2ff.

Rule: the input has two panels split by a divider column. A cell inked in both
panels with one color keeps that color. A cell inked only in the left panel
becomes 2. A cell inked only in the right panel becomes 1.
"""
import json
from pathlib import Path


def _split(inp):
    h, w = len(inp), len(inp[0])
    d = next(c for c in range(w) if len({inp[r][c] for r in range(h)}) == 1 and inp[0][c] != 0)
    left = [row[:d] for row in inp]
    right = [row[d + 1:] for row in inp]
    return left, right


def _combine(inp, one_left, one_right, both_diff=0):
    """Overlay the panels. one_left/one_right: color for one-sided ink (None keeps panel color)."""
    left, right = _split(inp)
    h, w = len(left), len(left[0])
    g = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            a, b = left[r][c], right[r][c]
            if a and b:
                g[r][c] = a if a == b else both_diff
            elif a:
                g[r][c] = a if one_left is None else one_left
            elif b:
                g[r][c] = b if one_right is None else one_right
    return g


def swapped_marks(inp, out):
    return _combine(inp, 1, 2)


def keep_panel_colors(inp, out):
    return _combine(inp, None, None)


def all_marks_one(inp, out):
    return _combine(inp, 1, 1)


def all_marks_two(inp, out):
    return _combine(inp, 2, 2)


def intersection_only(inp, out):
    return _combine(inp, 0, 0)


def only_left_marked(inp, out):
    return _combine(inp, 2, 0)


def only_right_marked(inp, out):
    return _combine(inp, 0, 1)


def marks_use_divider_color(inp, out):
    left, _ = _split(inp)
    d = len(left[0])
    return _combine(inp, inp[0][d], inp[0][d])


def left_panel_copy(inp, out):
    return _split(inp)[0]


def right_panel_copy(inp, out):
    return _split(inp)[1]


def mirrored_right_panel(inp, out):
    left, right = _split(inp)
    return _combine([l + [inp[0][len(l)]] + r[::-1] for l, r in zip(left, right)], 2, 1)


def marks_drop_agreed_ink(inp, out):
    # Only one-sided cells are marked; cells inked in both panels are cleared.
    left, right = _split(inp)
    g = [[0] * len(left[0]) for _ in left]
    for r in range(len(left)):
        for c in range(len(left[0])):
            a, b = left[r][c], right[r][c]
            if a and not b:
                g[r][c] = 2
            elif b and not a:
                g[r][c] = 1
    return g


def output_with_divider_column(inp, out):
    # Off-by-one width: the divider column is kept in the crop.
    return [row + [inp[0][len(row)]] for row in out]


ALTERNATIVES = [
    ("one-sided marks swapped: left-only ink 1, right-only ink 2", swapped_marks),
    ("one-sided ink keeps its own panel color instead of 1 or 2", keep_panel_colors),
    ("every one-sided cell marked 1", all_marks_one),
    ("only cells inked in both panels are kept; no marks", intersection_only),
    ("only left-only cells marked 2; right-only ink dropped", only_left_marked),
    ("only right-only cells marked 1; left-only ink dropped", only_right_marked),
    ("one-sided cells filled with the divider color", marks_use_divider_color),
    ("output is the left panel unchanged", left_panel_copy),
    ("output is the right panel unchanged", right_panel_copy),
    ("right panel mirrored left-right before the overlay", mirrored_right_panel),
    ("cells inked in both panels are cleared; only one-sided cells marked", marks_drop_agreed_ink),
    ("output keeps the divider column (width 11)", output_with_divider_column),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/d47aa2ff.json').read_text())
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))
            if ok and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
