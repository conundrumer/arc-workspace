"""Near-miss rules for f76d97a5.

Rule: two colors; 5 is the marker color. Cells of color 5 take the other
color, cells of the other color become 0.
"""
import json
from pathlib import Path

MARKER = 5


def _other(inp):
    cols = {v for r in inp for v in r}
    rest = sorted(cols - {MARKER})
    return rest[0] if rest else None


def _map(inp, f):
    return [[f(v) for v in r] for r in inp]


def keep_marker_color(inp, out):
    # marker cells keep color 5 instead of taking the other color
    return _map(inp, lambda v: MARKER if v == MARKER else 0)


def complement(inp, out):
    # the other color's cells are the shape; marker cells become 0
    o = _other(inp)
    return _map(inp, lambda v: 0 if v == MARKER else o)


def background_marker(inp, out):
    # background filled with the marker color instead of 0
    return _map(out, lambda v: MARKER if v == 0 else v)


def minority_color_is_shape(inp, out):
    # the least frequent color is taken as the shape cells
    flat = [v for r in inp for v in r]
    cols = sorted(set(flat))
    if len(cols) != 2:
        return None
    o = _other(inp)
    mn = min(cols, key=flat.count)
    return _map(inp, lambda v: o if v == mn else 0)


def corner_color_is_shape(inp, out):
    # the top-left color is taken as the shape color
    c = inp[0][0]
    o = _other(inp)
    return _map(inp, lambda v: o if v == c else 0)


def upper_rows_only(inp, out):
    # rule applied only to the upper half of the rows; the rest left as input
    h = len(out)
    return [list(out[i]) if i < h // 2 else list(inp[i]) for i in range(h)]


def shifted_right(inp, out):
    # output shifted one column right with wrap-around
    return [[r[-1]] + r[:-1] for r in out]


def cropped(inp, out):
    # off-by-one crop: last row and column dropped
    return [r[:-1] for r in out[:-1]]


def top_row_unfilled(inp, out):
    return [list(inp[0])] + [list(r) for r in out[1:]]


def border_unfilled(inp, out):
    # only the interior is rewritten; border cells are all 0
    h, w = len(out), len(out[0])
    return [[out[i][j] if 0 < i < h - 1 and 0 < j < w - 1 else 0
             for j in range(w)] for i in range(h)]


def unchanged(inp, out):
    return [list(r) for r in inp]


def even_columns_only(inp, out):
    # rule applied only in even columns; other columns left as in the input
    return [[out[i][j] if j % 2 == 0 else inp[i][j] for j in range(len(out[0]))]
            for i in range(len(out))]


ALTERNATIVES = [
    ("marker cells keep color 5 instead of taking the other color", keep_marker_color),
    ("other color's cells are the shape and marker cells become 0", complement),
    ("background filled with 5 instead of 0", background_marker),
    ("the least frequent color is taken as the shape", minority_color_is_shape),
    ("the top-left color is taken as the shape color", corner_color_is_shape),
    ("rule applied only to the upper half of the rows", upper_rows_only),
    ("output shifted one column to the right with wrap", shifted_right),
    ("output cropped by one row and one column", cropped),
    ("top row left as in the input", top_row_unfilled),
    ("border cells of the output left as background", border_unfilled),
    ("rule applied only in even columns", even_columns_only),
    ("input returned unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/f76d97a5.json"))
    train = task["train"]
    print("pairs", len(train), "readings", len(ALTERNATIVES))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
