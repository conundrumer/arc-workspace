import json
from pathlib import Path


def _colors(inp):
    """Per non-zero color: (first row, last row, first col, last col, cell count)."""
    info = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == 0:
                continue
            if v not in info:
                info[v] = [r, r, c, c, 0]
            d = info[v]
            d[0] = min(d[0], r)
            d[1] = max(d[1], r)
            d[2] = min(d[2], c)
            d[3] = max(d[3], c)
            d[4] += 1
    return info


def _chart(order, length):
    """Bars as columns, anchored at the top, one column per color in order."""
    h = max(length[c] for c in order)
    return [[c if r < length[c] else 0 for c in order] for r in range(h)]


def _by_length(length, descending=True):
    return sorted(length, key=lambda c: -length[c] if descending else length[c])


def _row_extent(inp):
    return {c: d[1] - d[0] + 1 for c, d in _colors(inp).items()}


def ascending_order(inp, out):
    return [row[::-1] for row in out]


def anchor_bottom(inp, out):
    return out[::-1]


def width_extent(inp, out):
    length = {c: d[3] - d[2] + 1 for c, d in _colors(inp).items()}
    return _chart(_by_length(length), length)


def cell_count_extent(inp, out):
    length = {c: d[4] for c, d in _colors(inp).items()}
    return _chart(_by_length(length), length)


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def appearance_order(inp, out):
    info = _colors(inp)
    order = sorted(info, key=lambda c: (info[c][0], info[c][2]))
    return _chart(order, _row_extent(inp))


def full_columns(inp, out):
    tops = [max(out[i][j] for i in range(len(out))) for j in range(len(out[0]))]
    return [list(tops) for _ in out]


def extent_minus_one(inp, out):
    length = {c: e - 1 for c, e in _row_extent(inp).items()}
    h = max(length.values())
    if h == 0:
        return None
    order = _by_length(_row_extent(inp))
    return [[c if r < length[c] else 0 for c in order] for r in range(h)]


def far_edge_distance(inp, out):
    length = {c: d[1] + 1 for c, d in _colors(inp).items()}
    return _chart(_by_length(length), length)


def drop_longest(inp, out):
    if len(out[0]) < 2:
        return None
    return [row[1:] for row in out]


def extra_background_row(inp, out):
    return [list(r) for r in out] + [[0] * len(out[0])]


def rotated_180(inp, out):
    return [row[::-1] for row in out[::-1]]


ALTERNATIVES = [
    ("bars ordered shortest first (longest at the far edge)", ascending_order),
    ("bars anchored at the bottom edge instead of the top", anchor_bottom),
    ("extent measured as horizontal width of each color", width_extent),
    ("extent measured as the count of cells of each color", cell_count_extent),
    ("bars drawn as rows instead of columns (output transposed)", transposed),
    ("bars ordered by first appearance top to bottom instead of by extent", appearance_order),
    ("every bar fills its whole column (bar length ignored)", full_columns),
    ("each bar one cell too short", extent_minus_one),
    ("extent taken as distance from the top edge to the color's far edge", far_edge_distance),
    ("longest bar dropped from the output", drop_longest),
    ("output one background line too tall", extra_background_row),
    ("output rotated 180 degrees (bars anchored at the bottom, longest at the right)", rotated_180),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b7999b51.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
