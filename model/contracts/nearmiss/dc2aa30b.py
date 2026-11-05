import json
from pathlib import Path


def _spans(flags):
    spans, start = [], None
    for i, f in enumerate(flags + [True]):
        if not f and start is None:
            start = i
        if f and start is not None:
            spans.append((start, i))
            start = None
    return spans


def _layout(inp):
    rows = _spans([all(v == 0 for v in r) for r in inp])
    cols = _spans([all(r[c] == 0 for r in inp) for c in range(len(inp[0]))])
    return rows, cols


def _tiles(inp):
    rows, cols = _layout(inp)
    tiles = {}
    for i, (r0, r1) in enumerate(rows):
        for j, (c0, c1) in enumerate(cols):
            tiles[(i, j)] = [row[c0:c1] for row in inp[r0:r1]]
    return tiles, rows, cols


def _count(tile, color):
    return sum(row.count(color) for row in tile)


def _place(inp, order, slots, color=1, transform=None, reverse=False):
    """Rank tiles by count of `color`, put the tile of rank k into slots[k]."""
    tiles, rows, cols = _tiles(inp)
    keys = sorted(tiles, key=lambda k: (_count(tiles[k], color), k), reverse=reverse)
    res = [row[:] for row in inp]
    for k, slot in zip(keys, slots):
        t = tiles[k]
        if transform:
            t = transform(t)
        r0, _ = rows[slot[0]]
        c0, _ = cols[slot[1]]
        for di, row in enumerate(t):
            for dj, v in enumerate(row):
                res[r0 + di][c0 + dj] = v
    return res


def _slots(n_r, n_c, start_row_bottom, start_col_right, row_first, snake=False):
    ri = list(range(n_r))[::-1] if start_row_bottom else list(range(n_r))
    ci = list(range(n_c))[::-1] if start_col_right else list(range(n_c))
    out = []
    if row_first:
        for a, r in enumerate(ri):
            cs = ci[::-1] if snake and a % 2 else ci
            out += [(r, c) for c in cs]
    else:
        for a, c in enumerate(ci):
            rs = ri[::-1] if snake and a % 2 else ri
            out += [(r, c) for r in rs]
    return out


def _dims(inp):
    rows, cols = _layout(inp)
    return len(rows), len(cols)


def mk(color=1, bottom=True, right=False, row_first=True, snake=False, reverse=False,
       transform=None):
    def f(inp, out):
        nr, nc = _dims(inp)
        return _place(inp, None, _slots(nr, nc, bottom, right, row_first, snake),
                      color, transform, reverse)
    return f


def rotate_rank(inp, out):
    nr, nc = _dims(inp)
    s = _slots(nr, nc, True, False, True)
    return _place(inp, None, s[1:] + s[:1])


def sort_within_band(inp, out):
    tiles, rows, cols = _tiles(inp)
    res = [row[:] for row in inp]
    for i in range(len(rows)):
        keys = sorted([(i, j) for j in range(len(cols))],
                      key=lambda k: _count(tiles[k], 1))
        for j, k in enumerate(keys):
            r0, _ = rows[i]
            c0, _ = cols[j]
            for di, row in enumerate(tiles[k]):
                for dj, v in enumerate(row):
                    res[r0 + di][c0 + dj] = v
    return res


def sort_within_col(inp, out):
    tiles, rows, cols = _tiles(inp)
    res = [row[:] for row in inp]
    for j in range(len(cols)):
        keys = sorted([(i, j) for i in range(len(rows))],
                      key=lambda k: _count(tiles[k], 1))[::-1]
        for i, k in enumerate(keys):
            r0, _ = rows[i]
            c0, _ = cols[j]
            for di, row in enumerate(tiles[k]):
                for dj, v in enumerate(row):
                    res[r0 + di][c0 + dj] = v
    return res


def dividers_filled(inp, out):
    res = [row[:] for row in out]
    for r in range(len(res)):
        for c in range(len(res[0])):
            if inp[r][c] == 0:
                res[r][c] = 2
    return res


def transpose_tile(t):
    return [list(r) for r in zip(*t)]


def flip_tile(t):
    return [r[::-1] for r in t]


def first_slot_unfilled(inp, out):
    """Slot of the rank-0 tile (bottom-left rank start) is left as the input tile."""
    rows, cols = _layout(inp)
    res = [row[:] for row in out]
    r0, r1 = rows[-1]
    c0, c1 = cols[0]
    for r in range(r0, r1):
        for c in range(c0, c1):
            res[r][c] = inp[r][c]
    return res


ALTERNATIVES = [
    ("rank by count of color 2 instead of color 1 (reverses the rank order)", mk(color=2)),
    ("tiles are ranked only within their own column band, not across the grid", sort_within_col),
    ("slot order starts at the top-left slot and runs along rows downward", mk(bottom=False)),
    ("slot order starts at bottom-left but runs up each column first, then steps right",
     mk(row_first=False)),
    ("slot order starts at the bottom-right slot and runs left along rows", mk(right=True)),
    ("slot order starts at the top-left slot and runs down columns first", mk(bottom=False, row_first=False)),
    ("slot order snakes: alternate lines of slots run in opposite directions", mk(snake=True)),
    ("each tile is transposed when placed in its slot", mk(transform=transpose_tile)),
    ("each tile is mirrored left-right when placed in its slot", mk(transform=flip_tile)),
    ("every tile lands one slot later than its rank slot (off by one)", rotate_rank),
    ("tiles are ranked only within their own row band, not across the grid", sort_within_band),
    ("divider cells are overwritten with color 2 in the output", dividers_filled),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/dc2aa30b.json'))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            ok = (g is not None and isinstance(g, list) and g
                  and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                  and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
                  and g != p["output"])
            n += bool(ok)
        print(n, desc)
