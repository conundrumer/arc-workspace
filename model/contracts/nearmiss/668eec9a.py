import json
from collections import Counter
from pathlib import Path


def _stats(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    cells = {}
    for y, r in enumerate(inp):
        for x, v in enumerate(r):
            if v != bg:
                cells.setdefault(v, []).append((y, x))
    return h, w, bg, cells


def _stack(colors, bg, n_rows, width, top=False):
    rows = [[c] * width for c in colors]
    pad = [[bg] * width for _ in range(n_rows - len(rows))]
    return rows + pad if top else pad + rows


def _by_key(inp, out, key, reverse=False, top=False):
    h, w, bg, cells = _stats(inp)
    cols = sorted(cells, key=lambda c: key(c, cells[c], h, w), reverse=reverse)
    return _stack(cols, bg, len(out), len(out[0]), top)


def order_from_bottom(inp, out):
    return _by_key(inp, out, lambda c, p, h, w: h - 1 - max(y for y, x in p))


def order_from_left(inp, out):
    return _by_key(inp, out, lambda c, p, h, w: min(x for y, x in p))


def order_from_right(inp, out):
    return _by_key(inp, out, lambda c, p, h, w: w - 1 - max(x for y, x in p))


def reversed_order(inp, out):
    return [list(r) for r in out[::-1]]


def top_aligned(inp, out):
    h, w, bg, cells = _stats(inp)
    cols = sorted(cells, key=lambda c: min(y for y, x in cells[c]))
    return _stack(cols, bg, len(out), len(out[0]), top=True)


def by_size_desc(inp, out):
    return _by_key(inp, out, lambda c, p, h, w: len(p), reverse=True)


def by_farthest_from_top(inp, out):
    return _by_key(inp, out, lambda c, p, h, w: max(y for y, x in p))


def single_column(inp, out):
    return [[r[0]] for r in out]


def extra_bg_row(inp, out):
    bg = _stats(inp)[2]
    return [list(r) for r in out] + [[bg] * len(out[0])]


def drop_largest_line(inp, out):
    h, w, bg, cells = _stats(inp)
    big = max(cells, key=lambda c: len(cells[c]))
    return [[bg if v == big else v for v in r] for r in out]


def wrong_background(inp, out):
    # The most common non-background color is read as background.
    h, w, bg, cells = _stats(inp)
    big = max(cells, key=lambda c: len(cells[c]))
    return [[big if v == bg else v for v in r] for r in out]


def input_width_output(inp, out):
    # Rows are drawn full input width.
    h, w, bg, cells = _stats(inp)
    cols = sorted(cells, key=lambda c: min(y for y, x in cells[c]))
    return _stack(cols, bg, len(out), w)


ALTERNATIVES = [
    ("order lines from the bottom edge instead of the top", order_from_bottom),
    ("order lines from the left edge", order_from_left),
    ("order lines from the right edge", order_from_right),
    ("stack order reversed (output flipped vertically)", reversed_order),
    ("stack lines against the top of the output, background at bottom", top_aligned),
    ("order lines by cell count, largest first", by_size_desc),
    ("order lines by their farthest point from the top edge", by_farthest_from_top),
    ("output one cell wide instead of three", single_column),
    ("output has one extra background row", extra_bg_row),
    ("largest line is dropped and left as background", drop_largest_line),
    ("background rows filled with the most common line color", wrong_background),
    ("rows drawn at full input width", input_width_output),
]

if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/668eec9a.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for name, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if (g is not None and g and isinstance(g, list)
                    and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                    and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                    and g != p["output"]):
                n += 1
        print(n, name)
