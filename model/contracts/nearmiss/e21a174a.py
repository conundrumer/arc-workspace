import json
from pathlib import Path


def _copy(g):
    return [list(r) for r in g]


def _layers(inp):
    """Layers by color: list of (color, r0, r1), top to bottom."""
    spans = {}
    for r, row in enumerate(inp):
        for v in row:
            if v:
                lo, hi = spans.get(v, (r, r))
                spans[v] = (min(lo, r), max(hi, r))
    return sorted(((c, lo, hi) for c, (lo, hi) in spans.items()), key=lambda t: t[1])


def _blank(inp):
    return [[0] * len(inp[0]) for _ in inp]


def _place(inp, layers, starts, colors=None):
    g = _blank(inp)
    for i, (c, lo, hi) in enumerate(layers):
        for k in range(hi - lo + 1):
            r = starts[i] + k
            if 0 <= r < len(g):
                for x, v in enumerate(inp[lo + k]):
                    if v:
                        g[r][x] = colors[i] if colors else v
    return g


def flip_all_pictures(inp, out):
    ls = _layers(inp)
    r0, r1 = ls[0][1], ls[-1][2]
    g = _copy(inp)
    g[r0:r1 + 1] = [list(r) for r in reversed(inp[r0:r1 + 1])]
    return g


def flip_whole_grid(inp, out):
    return [list(r) for r in reversed(inp)]


def slot_start(inp, out):
    ls = _layers(inp)
    n = len(ls)
    starts = [ls[n - 1 - i][1] for i in range(n)]
    return _place(inp, ls, starts)


def swap_ends(inp, out):
    ls = _layers(inp)
    if len(ls) < 3:
        return None
    order = [ls[-1]] + ls[1:-1] + [ls[0]]
    return _stack(inp, ls, order)


def _stack(inp, ls, order):
    """Place the layers of `order` top to bottom, packed from the stack top."""
    r = ls[0][1]
    starts = []
    for c, lo, hi in order:
        starts.append(r)
        r += hi - lo + 1
    return _place(inp, order, starts)


def keep_ends(inp, out):
    ls = _layers(inp)
    if len(ls) < 3:
        return None
    order = [ls[0]] + ls[-2:0:-1] + [ls[-1]]
    return _stack(inp, ls, order)


def rotate_cyclic(inp, out):
    ls = _layers(inp)
    return _stack(inp, ls, ls[1:] + ls[:1])


def sort_by_color(inp, out):
    ls = _layers(inp)
    return _stack(inp, ls, sorted(ls, key=lambda t: t[0]))


def colors_stay_in_slot(inp, out):
    ls = _layers(inp)
    n = len(ls)
    r0, r1 = ls[0][1], ls[-1][2]
    g = _copy(out)
    # slot colors: the input layer owning each row
    row_color = {}
    for c, lo, hi in ls:
        for r in range(lo, hi + 1):
            row_color[r] = c
    # rows of the output stack hold the reversed layers; recolor by the input color of that row
    for r in range(r0, r1 + 1):
        g[r] = [row_color[r] if v else 0 for v in out[r]]
    return g


def drop_smallest_layer(inp, out):
    cnt = {}
    for row in inp:
        for v in row:
            if v:
                cnt[v] = cnt.get(v, 0) + 1
    c = min(cnt, key=lambda k: (cnt[k], k))
    return [[0 if v == c else v for v in row] for row in out]


def shift_down(inp, out):
    return [[0] * len(out[0])] + _copy(out[:-1])


def shift_right(inp, out):
    return [[0] + row[:-1] for row in out]


def unchanged(inp, out):
    return _copy(inp)


def reverse_columns(inp, out):
    """Stack axis taken as horizontal: mirror the ink columns, keep pictures."""
    cols = [x for x in range(len(inp[0])) if any(row[x] for row in inp)]
    c0, c1 = cols[0], cols[-1]
    return [row[:c0] + row[c0:c1 + 1][::-1] + row[c1 + 1:] for row in inp]


ALTERNATIVES = [
    ("mirror the whole stack vertically, flipping each layer's picture too", flip_all_pictures),
    ("flip the whole grid vertically, so the stack mirrors across the grid middle", flip_whole_grid),
    ("each layer lands at the start row of its mirror layer's slot, so unequal heights leave gaps or overlap", slot_start),
    ("swap only the top and bottom layers", swap_ends),
    ("reverse only the inner layers, keeping the top and bottom layers fixed", keep_ends),
    ("move the top layer to the bottom, shifting the others up", rotate_cyclic),
    ("order layers by color value, ascending from the top", sort_by_color),
    ("reverse the shapes but each slot keeps its original color", colors_stay_in_slot),
    ("true output with the smallest layer left out", drop_smallest_layer),
    ("true output shifted down by one row", shift_down),
    ("mirror the columns of the ink instead of the order of the layers", reverse_columns),
    ("leave the grid unchanged", unchanged),
]


def _valid(g, out):
    if g is None:
        return False
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/e21a174a.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  ERROR", fn.__name__, e)
                g = None
            n += _valid(g, p["output"])
        print(n, fn.__name__, "-", desc)
