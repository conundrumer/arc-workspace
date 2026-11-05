import json
from pathlib import Path


def _bg(g):
    return 0


def _ink(seg):
    return sum(1 for r in seg for v in r if v != 0)


def _cols(g, a, b):
    return [r[a:b] for r in g]


def _segments(g, start, width, step):
    w = len(g[0])
    segs = []
    c = start
    while c + width <= w:
        segs.append((c, c + width))
        c += step
    return segs


def _rebuild(g, segs, order):
    # put segment order[i] content into slot i, keep other columns
    out = [row[:] for row in g]
    contents = [_cols(g, a, b) for a, b in segs]
    for slot, src in enumerate(order):
        a, b = segs[slot]
        for r in range(len(g)):
            out[r][a:b] = contents[src][r]
    return out


def _sorted_order(g, segs, key, reverse=False):
    idx = list(range(len(segs)))
    return sorted(idx, key=lambda i: key(_cols(g, *segs[i])), reverse=reverse)


def _true_segs(g):
    return _segments(g, 0, 2, 3)


def descending(inp, out):
    s = _true_segs(inp)
    return _rebuild(inp, s, _sorted_order(inp, s, _ink, True))


def offset_tiles(inp, out):
    s = _segments(inp, 1, 2, 3)
    return _rebuild(inp, s, _sorted_order(inp, s, _ink))


def wide_tiles_with_gap(inp, out):
    w = len(inp[0])
    s = [(c, min(c + 3, w)) for c in range(0, w, 3)]
    # last chunk is narrower; only sort the full-width ones
    s = [x for x in s if x[1] - x[0] == 3]
    return _rebuild(inp, s, _sorted_order(inp, s, _ink))


def sort_rows(inp, out):
    rows = sorted(inp, key=lambda r: sum(1 for v in r if v != 0))
    return [r[:] for r in rows]


def reverse_tiles(inp, out):
    s = _true_segs(inp)
    return _rebuild(inp, s, list(range(len(s)))[::-1])


def rotate_one(inp, out):
    s = _true_segs(inp)
    n = len(s)
    return _rebuild(inp, s, [(i + 1) % n for i in range(n)])


def one_bubble_pass(inp, out):
    s = _true_segs(inp)
    order = list(range(len(s)))
    k = [_ink(_cols(inp, *x)) for x in s]
    for i in range(len(order) - 1):
        if k[order[i]] > k[order[i + 1]]:
            order[i], order[i + 1] = order[i + 1], order[i]
    return _rebuild(inp, s, order)


def key_first_column_only(inp, out):
    s = _true_segs(inp)
    key = lambda seg: sum(1 for r in seg if r[0] != 0)
    order = _sorted_order(inp, s, key)
    return _rebuild(inp, s, order)


def key_top_half_only(inp, out):
    s = _true_segs(inp)
    h = len(inp) // 2
    key = lambda seg: _ink(seg[:h])
    return _rebuild(inp, s, _sorted_order(inp, s, key))


def swap_min_max_only(inp, out):
    s = _true_segs(inp)
    k = [_ink(_cols(inp, *x)) for x in s]
    order = list(range(len(s)))
    lo, hi = k.index(min(k)), k.index(max(k))
    order[0], order[lo] = order[lo], order[0]
    pos = order.index(hi)
    order[-1], order[pos] = order[pos], order[-1]
    return _rebuild(inp, s, order)


def tiles_mirrored_inside(inp, out):
    s = _true_segs(inp)
    g = _rebuild(inp, s, _sorted_order(inp, s, _ink))
    for a, b in s:
        for r in g:
            r[a:b] = r[a:b][::-1]
    return g


def gap_columns_filled(inp, out):
    ink_color = next(v for r in inp for v in r if v != 0)
    g = [r[:] for r in out]
    for r in g:
        for c in range(2, len(r), 3):
            r[c] = ink_color
    return g


def _differ(fn):
    def wrapped(inp, out):
        g = fn(inp, out)
        return None if g == out else g
    return wrapped


_RAW = [
    ("tiles sorted by ink count descending instead of ascending", descending),
    ("tile decomposition offset by one column", offset_tiles),
    ("tiles taken as 3-wide chunks including the gap column", wide_tiles_with_gap),
    ("rows sorted by ink count instead of column tiles", sort_rows),
    ("tile order reversed without ranking by ink", reverse_tiles),
    ("tiles cyclically shifted by one slot", rotate_one),
    ("single adjacent-swap pass instead of full sort", one_bubble_pass),
    ("tiles ranked by ink in their first column only", key_first_column_only),
    ("tiles ranked by ink in the top half only", key_top_half_only),
    ("only the least and most inked tiles are placed at the ends", swap_min_max_only),
    ("tiles sorted but each tile mirrored left to right", tiles_mirrored_inside),
    ("sorted output with gap columns filled with ink color", gap_columns_filled),
]

ALTERNATIVES = [(d, _differ(f)) for d, f in _RAW]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/85b81ff1.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
