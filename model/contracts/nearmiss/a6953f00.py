import json
from pathlib import Path


def _crop(g, r, c, h, w):
    return [row[c:c + w] for row in g[r:r + h]]


def _corner_origin(g, rc, h, w):
    """Top-left (row, col) of an h x w crop at corner rc = (0|1, 0|1)."""
    r = 0 if rc[0] == 0 else len(g) - h
    c = 0 if rc[1] == 0 else len(g[0]) - w
    return r, c


def _true_corner(inp, out):
    h, w = len(out), len(out[0])
    for rc in [(0, 1), (0, 0), (1, 0), (1, 1)]:
        r, c = _corner_origin(inp, rc, h, w)
        if _crop(inp, r, c, h, w) == out:
            return rc
    return None


def _at(inp, rc, h, w):
    r, c = _corner_origin(inp, rc, h, w)
    return _crop(inp, r, c, h, w)


def diagonal_corner(inp, out):
    rc = _true_corner(inp, out)
    return _at(inp, (1 - rc[0], 1 - rc[1]), 2, 2)


def other_row_side(inp, out):
    rc = _true_corner(inp, out)
    return _at(inp, (1 - rc[0], rc[1]), 2, 2)


def other_col_side(inp, out):
    rc = _true_corner(inp, out)
    return _at(inp, (rc[0], 1 - rc[1]), 2, 2)


def crop_3x3(inp, out):
    rc = _true_corner(inp, out)
    return _at(inp, rc, 3, 3)


def single_cell(inp, out):
    rc = _true_corner(inp, out)
    return _at(inp, rc, 1, 1)


def inward_offset(inp, out):
    rc = _true_corner(inp, out)
    r, c = _corner_origin(inp, rc, 2, 2)
    r += 1 if rc[0] == 0 else -1
    c += 1 if rc[1] == 0 else -1
    return _crop(inp, r, c, 2, 2)


def mirrored_crop(inp, out):
    return [row[::-1] for row in out]


def rotated_crop(inp, out):
    return [list(row) for row in zip(*out[::-1])]


def full_width_strip(inp, out):
    rc = _true_corner(inp, out)
    return _at(inp, (rc[0], 0), 2, len(inp[0]))


def always_bottom_right(inp, out):
    return _at(inp, (1, 1), 2, 2)


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("crop the diagonally opposite corner", diagonal_corner),
    ("crop the corner on the other top/bottom side, same left/right side", other_row_side),
    ("crop the corner on the other left/right side, same top/bottom side", other_col_side),
    ("crop a 3x3 window at the right corner", crop_3x3),
    ("output only the single corner cell", single_cell),
    ("2x2 window shifted one cell inward from the right corner", inward_offset),
    ("right 2x2 crop, mirrored left to right", mirrored_crop),
    ("right 2x2 crop, rotated a quarter turn", rotated_crop),
    ("two full-width rows from the right top/bottom side", full_width_strip),
    ("always crop the bottom-right corner", always_bottom_right),
    ("return the input unchanged", unchanged),
]


def _valid(g):
    return (
        isinstance(g, list) and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/a6953f00.json"))
    pairs = task["train"]
    print(f"pairs: {len(pairs)}")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
