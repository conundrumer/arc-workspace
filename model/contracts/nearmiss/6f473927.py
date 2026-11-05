import json
from pathlib import Path


def _side(inp):
    w = len(inp[0])
    cols = [c for r in inp for c, v in enumerate(r) if v != 0]
    return "left" if min(cols) < w - 1 - max(cols) else "right"


def _recolor(v):
    return 8 if v == 0 else 0


def _mirror(inp):
    return [list(reversed(r)) for r in inp]


def _join(inp, tile, side):
    if side == "right":
        return [list(a) + list(b) for a, b in zip(inp, tile)]
    return [list(b) + list(a) for a, b in zip(inp, tile)]


def _true_tile(inp):
    return [[_recolor(v) for v in r] for r in _mirror(inp)]


def swapped_sides(inp, out):
    w = len(inp[0])
    return [r[w:] + r[:w] for r in out]


def copy_not_flipped(inp, out):
    t = [[_recolor(v) for v in r] for r in inp]
    return _join(inp, t, _side(inp))


def flipped_no_recolor(inp, out):
    t = [[8 if v == 0 else v for v in r] for r in _mirror(inp)]
    return _join(inp, t, _side(inp))


def ink_to_8_bg_kept(inp, out):
    t = [[8 if v != 0 else 0 for v in r] for r in _mirror(inp)]
    return _join(inp, t, _side(inp))


def vertical_stack(inp, out):
    t = [[_recolor(v) for v in r] for r in reversed(inp)]
    if _side(inp) == "left":
        return t + [list(r) for r in inp]
    return [list(r) for r in inp] + t


def flipped_vertically_only(inp, out):
    t = [[_recolor(v) for v in r] for r in reversed(inp)]
    return _join(inp, t, _side(inp))


def rotated_180(inp, out):
    t = [[_recolor(v) for v in reversed(r)] for r in reversed(inp)]
    g = _join(inp, t, _side(inp))
    return None if g == out else g


def mirror_tile_blank(inp, out):
    w = len(inp[0])
    side = _side(inp)
    g = [list(r) for r in out]
    for r in g:
        rng = range(w, 2 * w) if side == "right" else range(w)
        for c in rng:
            r[c] = 0
    return g


def only_mirror_tile(inp, out):
    return _true_tile(inp)


def overlap_one_column(inp, out):
    w = len(inp[0])
    side = _side(inp)
    return [r[:w] + r[w + 1:] if side == "right" else r[:w - 1] + r[w:] for r in out]


def mirror_shifted_down(inp, out):
    t = _true_tile(inp)
    t = [t[-1]] + t[:-1]
    return _join(inp, t, _side(inp))


def mirror_bg_only_edge_rows_kept(inp, out):
    # bg recolored to 8 only in the original, mirror tile left as plain flip
    w = len(inp[0])
    side = _side(inp)
    t = _mirror(inp)
    g = _join(inp, t, side)
    return g


ALTERNATIVES = [
    ("mirror tile placed on the ink-far side instead of the ink-edge side", swapped_sides),
    ("second tile is an unflipped copy of the input, recolored", copy_not_flipped),
    ("mirror tile flipped but ink kept as 2 (only background recolored to 8)", flipped_no_recolor),
    ("mirror tile recolors ink to 8 and keeps background 0", ink_to_8_bg_kept),
    ("tiles stacked vertically with a vertical flip instead of side by side", vertical_stack),
    ("second tile flipped top-bottom instead of left-right", flipped_vertically_only),
    ("second tile rotated 180 degrees", rotated_180),
    ("recolored mirror tile region left blank (0)", mirror_tile_blank),
    ("output is only the recolored mirror tile", only_mirror_tile),
    ("tiles overlap by one column (width 2W-1)", overlap_one_column),
    ("mirror tile cyclically shifted down one row", mirror_shifted_down),
    ("mirror tile is a plain flipped copy with no recoloring", mirror_bg_only_edge_rows_kept),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/6f473927.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
