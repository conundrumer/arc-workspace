import json
from pathlib import Path


def _color(inp):
    return max((v for row in inp for v in row), default=0)


def _copy(g):
    return [list(r) for r in g]


def _h_spans(inp):
    """Gaps between consecutive marks in a row: list of cell lists."""
    spans = []
    for r, row in enumerate(inp):
        cols = [c for c, v in enumerate(row) if v]
        for a, b in zip(cols, cols[1:]):
            if b - a > 1:
                spans.append([(r, c) for c in range(a + 1, b)])
    return spans


def _v_spans(inp):
    spans = []
    for c in range(len(inp[0])):
        rows = [r for r in range(len(inp)) if inp[r][c]]
        for a, b in zip(rows, rows[1:]):
            if b - a > 1:
                spans.append([(r, c) for r in range(a + 1, b)])
    return spans


def _h_crossed(inp, span):
    # a mark shares a column with a span cell
    return any(inp[r2][c] for r, c in span for r2 in range(len(inp)))


def _v_crossed(inp, span):
    return any(inp[r][c2] for r, c in span for c2 in range(len(inp[0])))


def _paint(inp, cells, color):
    g = _copy(inp)
    for r, c in cells:
        g[r][c] = color
    return g


def vertical_axis(inp, out):
    cells = [p for s in _v_spans(inp) if not _v_crossed(inp, s) for p in s]
    return _paint(inp, cells, _color(inp))


def no_crossing_check_both_axes(inp, out):
    cells = [p for s in _h_spans(inp) + _v_spans(inp) for p in s]
    return _paint(inp, cells, _color(inp))


def only_crossed_spans(inp, out):
    cells = [p for s in _h_spans(inp) if _h_crossed(inp, s) for p in s]
    return _paint(inp, cells, _color(inp))


def cast_to_border(inp, out):
    cells = []
    for r, row in enumerate(inp):
        if any(row):
            cells += [(r, c) for c in range(len(row))]
    return _paint(inp, cells, _color(inp))


def wrong_fill_color(inp, out):
    col = _color(inp)
    g = _copy(out)
    changed = False
    for r in range(len(g)):
        for c in range(len(g[0])):
            if out[r][c] and not inp[r][c]:
                g[r][c] = 1 if col != 1 else 3
                changed = True
    return g if changed else None


def keep_only_first_filled_row(inp, out):
    rows = sorted({r for r in range(len(out)) for c in range(len(out[0]))
                   if out[r][c] and not inp[r][c]})
    if len(rows) < 2:
        return None
    g = _copy(out)
    for r in rows[1:]:
        g[r] = list(inp[r])
    return g


def fill_one_short(inp, out):
    g = _copy(out)
    changed = False
    for r in range(len(g)):
        added = [c for c in range(len(g[0])) if out[r][c] and not inp[r][c]]
        if added:
            g[r][added[-1]] = 0
            changed = True
    return g if changed else None


def bounding_box_fill(inp, out):
    pts = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v]
    r0, r1 = min(p[0] for p in pts), max(p[0] for p in pts)
    c0, c1 = min(p[1] for p in pts), max(p[1] for p in pts)
    cells = [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    return _paint(inp, cells, _color(inp))


def horizontal_no_crossing_check(inp, out):
    cells = [p for s in _h_spans(inp) for p in s]
    g = _paint(inp, cells, _color(inp))
    return g if g != out else None


def fill_vertical_gaps_unchecked_and_keep_horizontal(inp, out):
    # true output plus the vertical spans that the crossing rule rejects
    cells = [p for s in _v_spans(inp) for p in s]
    g = _paint(out, cells, _color(inp))
    return g if g != out else None


def input_unchanged(inp, out):
    return _copy(inp)


def fill_with_marks_erased(inp, out):
    # fills the true spans but drops the original marks
    g = _copy(out)
    changed = False
    for r in range(len(g)):
        for c in range(len(g[0])):
            if inp[r][c]:
                g[r][c] = 0
                changed = True
    return g if changed else None


ALTERNATIVES = [
    ("fill vertical gaps between marks instead of horizontal ones", vertical_axis),
    ("fill gaps along both axes with no crossing check", no_crossing_check_both_axes),
    ("fill only the horizontal gaps that a mark crosses", only_crossed_spans),
    ("cast each mark's row to the grid border", cast_to_border),
    ("fill the correct cells with the wrong color", wrong_fill_color),
    ("fill only the first of the correct filled rows", keep_only_first_filled_row),
    ("fill each correct span one cell short", fill_one_short),
    ("fill the bounding box of the marks", bounding_box_fill),
    ("fill every horizontal gap, ignoring the crossing condition", horizontal_no_crossing_check),
    ("correct fill plus the vertical gaps the crossing rule rejects", fill_vertical_gaps_unchecked_and_keep_horizontal),
    ("correct fill but the original marks erased", fill_with_marks_erased),
    ("leave the input unchanged", input_unchanged),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/5ad8a7c0.json").read_text())
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != p["output"])
            n += ok
        print(f"{n}/{len(train)}  {desc}")
