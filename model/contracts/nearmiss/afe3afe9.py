"""Near-miss readings for ARC task afe3afe9.

Rule: hollow 3x3 squares sit on a 7x7 slot tiling (pitch 4). One grid edge is a
line. Each square becomes one cell of its color; the cells of each slot line
slide to the side a quarter turn clockwise from the line's side.
"""
import json
from pathlib import Path

PITCH = 4
SLOTS = 7
CW = {"top": "R", "right": "D", "bottom": "L", "left": "U"}
CCW = {"top": "L", "right": "U", "bottom": "R", "left": "D"}
TOWARD = {"top": "U", "right": "R", "bottom": "D", "left": "L"}
AWAY = {"top": "D", "right": "L", "bottom": "U", "left": "R"}


def line_side(inp):
    h, w = len(inp), len(inp[0])
    sides = {
        "top": inp[0],
        "bottom": inp[-1],
        "left": [r[0] for r in inp],
        "right": [r[-1] for r in inp],
    }
    for name, cells in sides.items():
        if len(set(cells)) == 1 and cells[0] != 0:
            return name, cells[0]
    return None, None


def slot_grid(inp):
    side, lc = line_side(inp)
    h, w = len(inp), len(inp[0])
    pts = [(r, c) for r in range(h) for c in range(w) if inp[r][c] not in (0, lc)]
    br = min(r for r, _ in pts) % PITCH
    bc = min(c for _, c in pts) % PITCH
    grid = []
    for i in range(SLOTS):
        row = []
        for j in range(SLOTS):
            r, c = br + PITCH * i, bc + PITCH * j
            v = 0
            if r < h and c < w and inp[r][c] not in (0, lc):
                v = inp[r][c]
            row.append(v)
        grid.append(row)
    return grid


def transpose(g):
    return [list(r) for r in zip(*g)]


def trim(g):
    rows = [r for r in g if any(r)]
    cols = [j for j in range(len(g[0])) if any(r[j] for r in g)]
    if not rows:
        return g
    lo, hi = min(cols), max(cols)
    return [r[lo:hi + 1] for r in rows]


def pack(S, d, width=None, key=None):
    """Slide the cells of each slot line toward side d (L, R, U or D)."""
    if d in "UD":
        res = pack(transpose(S), "L" if d == "U" else "R", width, key)
        return transpose(res)
    rows = S[:]
    first = min(i for i, r in enumerate(rows) if any(r))
    last = max(i for i, r in enumerate(rows) if any(r))
    rows = rows[first:last + 1]
    lines = []
    for r in rows:
        cells = [v for v in r if v]
        if key == "reverse":
            cells = cells[::-1]
        elif key == "sort":
            cells = sorted(cells)
        lines.append(cells)
    n = width or max(len(l) for l in lines)
    out = []
    for l in lines:
        pad = [0] * (n - len(l))
        out.append(l + pad if d == "L" else pad + l)
    return out


def true_dir(inp):
    side, _ = line_side(inp)
    return CW[side]


def alt_ccw(inp, out):
    side, _ = line_side(inp)
    return pack(slot_grid(inp), CCW[side])


def alt_toward_line(inp, out):
    side, _ = line_side(inp)
    return pack(slot_grid(inp), TOWARD[side])


def alt_away_from_line(inp, out):
    side, _ = line_side(inp)
    return pack(slot_grid(inp), AWAY[side])


def alt_no_slide(inp, out):
    return trim(slot_grid(inp))


def alt_line_color_fill(inp, out):
    _, lc = line_side(inp)
    return [[lc if v == 0 else v for v in r] for r in out]


def alt_full_width(inp, out):
    return pack(slot_grid(inp), true_dir(inp), width=SLOTS)


def alt_reverse_order(inp, out):
    return pack(slot_grid(inp), true_dir(inp), key="reverse")


def alt_sort_by_color(inp, out):
    return pack(slot_grid(inp), true_dir(inp), key="sort")


def alt_transpose(inp, out):
    return transpose(out)


def alt_flip_lines(inp, out):
    if true_dir(inp) in "LR":
        return out[::-1]
    return [r[::-1] for r in out]


def alt_rings_kept(inp, out):
    res = []
    for r in out:
        for k in range(3):
            row = []
            for v in r:
                if v == 0:
                    row += [0, 0, 0]
                elif k == 1:
                    row += [v, 0, v]
                else:
                    row += [v, v, v]
            res.append(row)
    return res


def alt_crop_far_line(inp, out):
    d = true_dir(inp)
    if d == "R":
        return [r[1:] for r in out]
    if d == "L":
        return [r[:-1] for r in out]
    if d == "D":
        return out[1:]
    return out[:-1]


ALTERNATIVES = [
    ("pack a quarter turn counterclockwise from the line side instead of clockwise", alt_ccw),
    ("pack toward the line's side", alt_toward_line),
    ("pack away from the line's side", alt_away_from_line),
    ("each square becomes one cell but no cells slide; slot gaps are kept", alt_no_slide),
    ("pack correctly but fill empty cells with the line color", alt_line_color_fill),
    ("pack correctly but the output is as long as the slot count (7) along the pack axis", alt_full_width),
    ("pack to the correct side but each line's cell order is reversed", alt_reverse_order),
    ("pack to the correct side but each line's cells are sorted by color", alt_sort_by_color),
    ("output is transposed: slot lines and pack axis swapped", alt_transpose),
    ("the order of the slot lines across the pack axis is flipped", alt_flip_lines),
    ("squares are kept as 3x3 hollow rings in the packed layout, not shrunk to one cell", alt_rings_kept),
    ("off-by-one crop: the output drops its far line on the side opposite the pack side", alt_crop_far_line),
]


def valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1
        and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/afe3afe9.json").read_text())
    pairs = task["train"]
    for p in pairs:
        assert pack(slot_grid(p["input"]), true_dir(p["input"])) == p["output"], "base pack mismatch"
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
