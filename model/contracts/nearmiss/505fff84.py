"""Near-miss readings for ARC task 505fff84.

Rule: in each row that holds a 1 (west) and an 8 (east), take the cells
strictly between them. Stack those segments, top to bottom, as the output.
"""
import json
from pathlib import Path


def _rows(inp):
    """Marked rows as (row index, col of 1, col of 8)."""
    found = []
    for r, row in enumerate(inp):
        if 1 in row and 8 in row:
            found.append((r, row.index(1), row.index(8)))
    return found


def _slice(inp, lo_off, hi_off):
    rows = []
    for r, a, b in _rows(inp):
        rows.append(list(inp[r][a + lo_off:b + hi_off]))
    return rows or None


def inclusive(inp, out):
    return _slice(inp, 0, 1)


def keep_one_marker(inp, out):
    return _slice(inp, 0, 0)


def drop_extra_cell(inp, out):
    return _slice(inp, 2, 0)


def shifted_window(inp, out):
    return _slice(inp, 2, 1)


def mirrored(inp, out):
    return [row[::-1] for row in out]


def rows_reversed(inp, out):
    return [list(row) for row in out[::-1]]


def only_first_row(inp, out):
    return [list(out[0])]


def transposed(inp, out):
    return [list(col) for col in zip(*out)]


def marker_color_fill(inp, out):
    return [[1 if v else 0 for v in row] for row in out]


def outside_cells(inp, out):
    rows = []
    for r, a, b in _rows(inp):
        rows.append(list(inp[r][:a]) + list(inp[r][b + 1:]))
    return rows or None


def span_with_gap_rows(inp, out):
    marked = _rows(inp)
    if not marked:
        return None
    r0, r1 = marked[0][0], marked[-1][0]
    a = min(m[1] for m in marked)
    b = max(m[2] for m in marked)
    return [list(inp[r][a + 1:b]) for r in range(r0, r1 + 1)]


def one_row_concat(inp, out):
    return [[v for row in out for v in row]]


ALTERNATIVES = [
    ("crop includes the 1 and 8 marker cells", inclusive),
    ("crop starts at the 1 marker and stops before the 8 (off by one)", keep_one_marker),
    ("crop starts one cell after the 1 marker and stops before the 8, dropping a cell", drop_extra_cell),
    ("window between the markers shifted one column east", shifted_window),
    ("each segment read east to west (mirrored)", mirrored),
    ("segments stacked bottom to top", rows_reversed),
    ("only the first marked row is extracted", only_first_row),
    ("output transposed (segments stacked as columns)", transposed),
    ("segment cells recolored to the marker color 1", marker_color_fill),
    ("cells outside the markers are kept instead of the cells between", outside_cells),
    ("one block from the first to the last marked row, unmarked rows between included", span_with_gap_rows),
    ("all segments concatenated into a single row", one_row_concat),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/505fff84.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
