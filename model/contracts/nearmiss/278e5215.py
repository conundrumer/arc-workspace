import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    # stencil: the color whose cells form the large shape (the most common non-bg color)
    stencil = Counter(v for r in inp for v in r if v != bg).most_common(1)[0][0]
    def bbox(pred):
        cells = [(y, x) for y in range(h) for x in range(w) if pred(inp[y][x])]
        ys = [c[0] for c in cells]
        xs = [c[1] for c in cells]
        return min(ys), max(ys), min(xs), max(xs)
    sb = bbox(lambda v: v == stencil)
    lb = bbox(lambda v: v != bg and v != stencil)
    legend = [row[lb[2]:lb[3] + 1] for row in inp[lb[0]:lb[1] + 1]]
    mask = [[inp[y][x] == stencil for x in range(sb[2], sb[3] + 1)]
            for y in range(sb[0], sb[1] + 1)]
    cols = legend[0]
    line = legend[-1][0]
    return mask, cols, line, legend


def _render(mask, cols, line):
    return [[cols[x] if m else line for x, m in enumerate(row)] for row in mask]


def swapped_roles(inp, out):
    mask, cols, line, _ = _parse(inp)
    return [[line if m else cols[x] for x, m in enumerate(row)] for row in mask]


def mirrored_legend(inp, out):
    mask, cols, line, _ = _parse(inp)
    return _render(mask, cols[::-1], line)


def mirrored_stencil(inp, out):
    mask, cols, line, _ = _parse(inp)
    return _render([r[::-1] for r in mask], cols, line)


def flipped_stencil(inp, out):
    mask, cols, line, _ = _parse(inp)
    return _render(mask[::-1], cols, line)


def line_color_is_commonest_column_color(inp, out):
    mask, cols, line, legend = _parse(inp)
    body = [v for r in legend[:-1] for v in r]
    return _render(mask, cols, Counter(body).most_common(1)[0][0])


def box_one_extra_column(inp, out):
    mask, cols, line, _ = _parse(inp)
    grid = _render(mask, cols, line)
    return [r + [line] for r in grid]


def box_drops_last_row(inp, out):
    mask, cols, line, _ = _parse(inp)
    return _render(mask[:-1], cols, line)


def columns_shifted_one(inp, out):
    mask, cols, line, _ = _parse(inp)
    return _render(mask, cols[-1:] + cols[:-1], line)


def background_for_non_stencil(inp, out):
    mask, cols, line, _ = _parse(inp)
    return [[cols[x] if m else 0 for x, m in enumerate(row)] for row in mask]


def every_cell_column_colored(inp, out):
    mask, cols, line, _ = _parse(inp)
    return [[cols[x] for x in range(len(row))] for row in mask]


def colors_by_row_index(inp, out):
    mask, cols, line, _ = _parse(inp)
    return [[cols[y % len(cols)] if m else line for m in row]
            for y, row in enumerate(mask)]


def transposed_output(inp, out):
    return [list(r) for r in zip(*out)]


ALTERNATIVES = [
    ("stencil cells get the line color and the rest get column colors", swapped_roles),
    ("legend column colors are read right to left", mirrored_legend),
    ("stencil shape is mirrored left to right", mirrored_stencil),
    ("stencil shape is flipped top to bottom", flipped_stencil),
    ("line color is the most common color of the legend body", line_color_is_commonest_column_color),
    ("crop takes one extra column on the right, filled with the line color", box_one_extra_column),
    ("crop drops the last row of the stencil box", box_drops_last_row),
    ("column colors are shifted one column to the right", columns_shifted_one),
    ("non-stencil cells stay background instead of taking the line color", background_for_non_stencil),
    ("every cell takes its column color, the stencil shape is ignored", every_cell_column_colored),
    ("column color is indexed by row instead of column", colors_by_row_index),
    ("true output transposed", transposed_output),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/278e5215.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
