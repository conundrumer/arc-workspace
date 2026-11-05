"""Near-miss readings for ARC task b0f4d537."""
import json
from pathlib import Path

DIV = 5
MARK = 4


def _split(inp):
    """Return (key grid, field grid) from an input."""
    h, w = len(inp), len(inp[0])
    dcols = [c for c in range(w) if all(inp[r][c] == DIV for r in range(h))]
    c0 = dcols[0]
    left = [row[:c0] for row in inp]
    right = [row[c0 + 1:] for row in inp]
    if any(v == MARK for row in left for v in row):
        field, panel = left, right
    else:
        field, panel = right, left
    cells = [(r, c) for r, row in enumerate(panel) for c, v in enumerate(row) if v != DIV]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    k0 = min(c for _, c in cells)
    k1 = max(c for _, c in cells)
    key = [row[k0:k1 + 1] for row in panel[r0:r1 + 1]]
    return key, field


def _lines(inp):
    _, field = _split(inp)
    h, w = len(field), len(field[0])
    lr = [r for r in range(h) if field[r][0] == MARK and field[r][-1] == MARK]
    lc = [c for c in range(w) if field[0][c] == MARK and field[h - 1][c] == MARK]
    return lr, lc


def _row_color(out, r, lc):
    w = len(out[0])
    for c in range(w):
        if c not in lc:
            return out[r][c]
    return out[r][0]


def _col_color(out, c, lr):
    h = len(out)
    for r in range(h):
        if r not in lr:
            return out[r][c]
    return out[0][c]


def _crossings(inp, out, prefer):
    lr, lc = _lines(inp)
    res = [row[:] for row in out]
    for r in lr:
        for c in lc:
            rc = _row_color(out, r, lc)
            cc = _col_color(out, c, lr)
            res[r][c] = rc if prefer == "row" else cc
    return res


def row_priority(inp, out):
    return _crossings(inp, out, "row")


def col_priority(inp, out):
    return _crossings(inp, out, "col")


def key_unstretched(inp, out):
    key, _ = _split(inp)
    return key


def field_unchanged(inp, out):
    _, field = _split(inp)
    return field


def proportional_resize(inp, out):
    key, _ = _split(inp)
    kh, kw = len(key), len(key[0])
    h, w = len(out), len(out[0])
    return [[key[r * kh // h][c * kw // w] for c in range(w)] for r in range(h)]


def horizontal_lines_only(inp, out):
    lr, lc = _lines(inp)
    return [[(0 if (r not in lr and c in lc) else v) for c, v in enumerate(row)]
            for r, row in enumerate(out)]


def vertical_lines_only(inp, out):
    lr, lc = _lines(inp)
    return [[(0 if (c not in lc and r in lr) else v) for c, v in enumerate(row)]
            for r, row in enumerate(out)]


def mirrored_vertically(inp, out):
    return out[::-1]


def mirrored_horizontally(inp, out):
    return [row[::-1] for row in out]


def markers_kept(inp, out):
    _, field = _split(inp)
    return [[(MARK if field[r][c] == MARK else v) for c, v in enumerate(row)]
            for r, row in enumerate(out)]


def cropped_off_by_one(inp, out):
    return [row[:-1] for row in out[:-1]]


def lines_between_markers_only(inp, out):
    """Lines drawn only strictly between their end markers, not on the border."""
    lr, lc = _lines(inp)
    h, w = len(out), len(out[0])
    res = [row[:] for row in out]
    for r in lr:
        res[r][0] = 0
        res[r][w - 1] = 0
    for c in lc:
        res[0][c] = 0
        res[h - 1][c] = 0
    return res


ALTERNATIVES = [
    ("crossing cells take the line row's color instead of the key's crossing color", row_priority),
    ("crossing cells take the line column's color instead of the key's crossing color", col_priority),
    ("the output is the key cropped out of its panel, not stretched to the field", key_unstretched),
    ("the output is the field itself with its marker cells left in place", field_unchanged),
    ("the key is resized proportionally to the field, so line rows and columns are not matched to markers", proportional_resize),
    ("only the horizontal lines are drawn; line columns are left empty", horizontal_lines_only),
    ("only the vertical lines are drawn; line rows are left empty", vertical_lines_only),
    ("the key is applied upside down (line rows counted from the wrong end)", mirrored_vertically),
    ("the key is applied left to right reversed (line columns counted from the wrong end)", mirrored_horizontally),
    ("marker cells stay 4 in the output on top of the stretched key", markers_kept),
    ("output is one row and one column too small (off-by-one crop)", cropped_off_by_one),
    ("lines skip the field border cells where the markers are", lines_between_markers_only),
]


def _valid(g):
    return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b0f4d537.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, repr(e))
                g = None
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), fn.__name__, "-", desc)
