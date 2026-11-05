import json
from pathlib import Path


def _segments(flags):
    segs, start = [], None
    for i, f in enumerate(flags):
        if not f and start is None:
            start = i
        if f and start is not None:
            segs.append((start, i))
            start = None
    if start is not None:
        segs.append((start, len(flags)))
    return segs


def _info(inp):
    h, w = len(inp), len(inp[0])
    rs = _segments([all(v == 5 for v in r) for r in inp])
    cs = _segments([all(inp[r][c] == 5 for r in range(h)) for c in range(w)])
    col = next(v for r in inp for v in r if v not in (0, 5))
    counts = {}
    for i, (r0, r1) in enumerate(rs):
        for j, (c0, c1) in enumerate(cs):
            counts[(i, j)] = sum(1 for r in range(r0, r1) for c in range(c0, c1) if inp[r][c] == col)
    return rs, cs, col, counts


def _blank(inp):
    return [[5 if v == 5 else 0 for v in r] for r in inp]


def _fill(g, rs, cs, tiles, col, inset=0, grow=0):
    g = [r[:] for r in g]
    for (i, j) in tiles:
        r0, r1 = rs[i]
        c0, c1 = cs[j]
        for r in range(max(0, r0 + inset - grow), min(len(g), r1 - inset + grow)):
            for c in range(max(0, c0 + inset - grow), min(len(g[0]), c1 - inset + grow)):
                g[r][c] = col
    return g


def _ranked(counts):
    return sorted(counts, key=lambda k: (-counts[k], k))


def min_nonempty(inp, out):
    rs, cs, col, n = _info(inp)
    ne = [k for k in n if n[k] > 0]
    k = min(ne, key=lambda k: (n[k], k))
    return _fill(_blank(inp), rs, cs, [k], col)


def keep_other_marks(inp, out):
    rs, cs, col, n = _info(inp)
    k = _ranked(n)[0]
    return _fill(inp, rs, cs, [k], col)


def fill_with_separator_color(inp, out):
    rs, cs, col, n = _info(inp)
    return _fill(_blank(inp), rs, cs, [_ranked(n)[0]], 5)


def second_most(inp, out):
    rs, cs, col, n = _info(inp)
    return _fill(_blank(inp), rs, cs, [_ranked(n)[1]], col)


def transposed_tile(inp, out):
    rs, cs, col, n = _info(inp)
    i, j = _ranked(n)[0]
    g = _fill(_blank(inp), rs, cs, [(j, i)], col)
    return None if g == out else g


def whole_tile_row(inp, out):
    rs, cs, col, n = _info(inp)
    i, _ = _ranked(n)[0]
    return _fill(_blank(inp), rs, cs, [(i, j) for j in range(len(cs))], col)


def inset_fill(inp, out):
    rs, cs, col, n = _info(inp)
    return _fill(_blank(inp), rs, cs, [_ranked(n)[0]], col, inset=1)


def grow_into_separators(inp, out):
    rs, cs, col, n = _info(inp)
    return _fill(_blank(inp), rs, cs, [_ranked(n)[0]], col, grow=1)


def last_marked_tile(inp, out):
    rs, cs, col, n = _info(inp)
    marks = [(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] == col]
    r, c = marks[-1]
    k = next((i, j) for i, (r0, r1) in enumerate(rs) for j, (c0, c1) in enumerate(cs)
             if r0 <= r < r1 and c0 <= c < c1)
    g = _fill(_blank(inp), rs, cs, [k], col)
    return None if g == out else g


def wrapped_neighbor(inp, out):
    rs, cs, col, n = _info(inp)
    i, j = _ranked(n)[0]
    return _fill(_blank(inp), rs, cs, [(i, (j + 1) % len(cs))], col)


def all_marked_tiles(inp, out):
    rs, cs, col, n = _info(inp)
    return _fill(_blank(inp), rs, cs, [k for k in n if n[k] > 0], col)


def crop_filled_tile(inp, out):
    rs, cs, col, n = _info(inp)
    i, j = _ranked(n)[0]
    (r0, r1), (c0, c1) = rs[i], cs[j]
    return [[col] * (c1 - c0) for _ in range(r1 - r0)]


ALTERNATIVES = [
    ("fills the tile with the fewest marks (among tiles with marks) instead of the most", min_nonempty),
    ("fills the most-marked tile but leaves the marks of the other tiles in place", keep_other_marks),
    ("fills the most-marked tile with the separator color 5 instead of the mark color", fill_with_separator_color),
    ("fills the tile with the second-most marks", second_most),
    ("fills the tile at the transposed tile position of the most-marked tile", transposed_tile),
    ("fills the whole row of tiles that holds the most-marked tile", whole_tile_row),
    ("fills the most-marked tile one cell short on every side", inset_fill),
    ("fills the most-marked tile and one cell into the surrounding separators", grow_into_separators),
    ("fills the tile that holds the last mark in reading order", last_marked_tile),
    ("fills the tile right of the most-marked tile (wrapping)", wrapped_neighbor),
    ("fills every tile that holds a mark", all_marked_tiles),
    ("outputs only the filled tile cropped out of the grid", crop_filled_tile),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/29623171.json"))
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(train)}  {desc}")
