"""Near-miss rules for ARC task 20fb2937.

Rule: a divider row (one non-bg color) splits the grid. One side (header) holds
3x3 swatch tiles and, below each, a 3x3 key tile with one mark cell. The other
side (field) holds single mark cells. Each field mark takes the swatch color of
the key with that mark color and becomes a 3x3 block centered on the mark. The
output is the field only.
"""
import json
from collections import Counter
from pathlib import Path

SQUARE3 = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)]


def parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for row in inp for v in row).most_common(1)[0][0]
    div = None
    for r in range(h):
        if len(set(inp[r])) == 1 and inp[r][0] != bg:
            div = r
            break
    if div is None:
        return None
    header, field = inp[:div], inp[div + 1:]
    hh = len(header)
    swatch_cols = {}  # swatch color -> (cmin, cmax)
    keys = []         # (row, col, color) of isolated header cells
    for r in range(hh):
        for c in range(w):
            v = header[r][c]
            if v == bg:
                continue
            nb = [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]
            if any(0 <= a < hh and 0 <= b < w and header[a][b] == v for a, b in nb):
                lo, hi = swatch_cols.get(v, (c, c))
                swatch_cols[v] = (min(lo, c), max(hi, c))
            else:
                keys.append((r, c, v))
    keymap = {}
    for r, c, v in keys:
        for sc, (lo, hi) in swatch_cols.items():
            if lo <= c <= hi:
                keymap[v] = sc
    marks = [(r, c, field[r][c]) for r in range(len(field)) for c in range(w)
             if field[r][c] != bg]
    return dict(bg=bg, div=div, header=header, field=field, keys=keys,
                keymap=keymap, marks=marks, w=w)


def paint(field, marks, keymap, offsets, color_of=None, skip_clipped=False,
          first_only=False, keep_mark=False, bg=7):
    g = [row[:] for row in field]
    fh, w = len(g), len(g[0])
    seen = set()
    for r, c, v in marks:
        if v not in keymap:
            continue
        if first_only and v in seen:
            continue
        seen.add(v)
        col = color_of(v) if color_of else keymap[v]
        cells = [(r + dr, c + dc) for dr, dc in offsets]
        if skip_clipped and any(not (0 <= a < fh and 0 <= b < w) for a, b in cells):
            continue
        for a, b in cells:
            if 0 <= a < fh and 0 <= b < w:
                g[a][b] = col
    if keep_mark:
        for r, c, v in marks:
            g[r][c] = v
    return g


def with_parse(f):
    def wrapper(inp, out):
        p = parse(inp)
        if p is None:
            return None
        return f(p, inp, out)
    return wrapper


@with_parse
def single_cell(p, inp, out):
    return paint(p["field"], p["marks"], p["keymap"], [(0, 0)])


@with_parse
def plus_shape(p, inp, out):
    return paint(p["field"], p["marks"], p["keymap"],
                 [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)])


@with_parse
def anchored_top_left(p, inp, out):
    return paint(p["field"], p["marks"], p["keymap"],
                 [(dr, dc) for dr in (0, 1, 2) for dc in (0, 1, 2)])


@with_parse
def shifted_swatch(p, inp, out):
    sw = sorted(set(p["keymap"].values()), key=lambda s: min(
        c for r, c, v in p["keys"] if p["keymap"].get(v) == s))
    nxt = {s: sw[(i + 1) % len(sw)] for i, s in enumerate(sw)}
    return paint(p["field"], p["marks"], p["keymap"], SQUARE3,
                 color_of=lambda v: nxt[p["keymap"][v]])


@with_parse
def whole_grid(p, inp, out):
    g = paint(p["field"], p["marks"], p["keymap"], SQUARE3)
    return [r[:] for r in p["header"]] + [inp[p["div"]][:]] + g


@with_parse
def header_side(p, inp, out):
    return [r[:] for r in p["header"]]


@with_parse
def own_mark_color(p, inp, out):
    return paint(p["field"], p["marks"], p["keymap"], SQUARE3,
                 color_of=lambda v: v)


def flipped_vertically(inp, out):
    return [r[:] for r in out[::-1]]


@with_parse
def first_mark_per_color(p, inp, out):
    return paint(p["field"], p["marks"], p["keymap"], SQUARE3, first_only=True)


@with_parse
def marks_kept(p, inp, out):
    return paint(p["field"], p["marks"], p["keymap"], SQUARE3, keep_mark=True)


@with_parse
def five_by_five(p, inp, out):
    return paint(p["field"], p["marks"], p["keymap"],
                 [(dr, dc) for dr in range(-2, 3) for dc in range(-2, 3)])


@with_parse
def diagonal_cross(p, inp, out):
    return paint(p["field"], p["marks"], p["keymap"],
                 [(0, 0), (-1, -1), (-1, 1), (1, -1), (1, 1)])


ALTERNATIVES = [
    ("Mark becomes a single cell of the swatch color, no 3x3 block", single_cell),
    ("Block is a plus shape (4-neighbors) instead of the full 3x3", plus_shape),
    ("3x3 block is anchored with the mark at its top-left corner, not centered", anchored_top_left),
    ("Key marks pair with the next swatch in order, so every stamp has the wrong color", shifted_swatch),
    ("Whole input is returned with the field painted; header and divider are kept", whole_grid),
    ("Output is the header side of the divider, not the field", header_side),
    ("Block is painted in the mark's own color instead of the swatch color", own_mark_color),
    ("Correct field painting, but read bottom-up (vertically flipped)", flipped_vertically),
    ("Only the first mark of each color is stamped", first_mark_per_color),
    ("Stamps are drawn but the original mark cells stay in the block centers", marks_kept),
    ("Block is 5x5 instead of 3x3", five_by_five),
    ("Block covers only the center and the four diagonal cells", diagonal_cross),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and all(len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


def _check_true_rule():
    pass


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/20fb2937.json").read_text())
    pairs = task["train"]
    print(f"{len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for pr in pairs:
            g = fn(pr["input"], pr["output"])
            if g is not None and valid(g) and g != pr["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
