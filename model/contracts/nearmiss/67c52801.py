import json
from pathlib import Path


def _copy(g):
    return [list(r) for r in g]


def _slots(inp, out):
    """Slots in the marker row (row above the bottom ground row): (c0, c1, color)."""
    m = len(inp) - 2
    row = inp[m]
    res = []
    c = 0
    while c < len(row):
        if row[c] == 0:
            c0 = c
            while c < len(row) and row[c] == 0:
                c += 1
            res.append((c0, c - 1, out[m][c0]))
        else:
            c += 1
    return res


def _piece_cells(inp, color):
    """Cells of the colored block above the marker row."""
    m = len(inp) - 2
    return [(r, c) for r in range(m) for c in range(len(inp[0])) if inp[r][c] == color]


def _painted(inp, out, height_of, only=None, start_off=0, colors=None):
    """Clear the filled cells of out, then paint each slot `height_of(slot)` rows
    tall, starting `start_off` rows above the marker row."""
    g = _copy(out)
    m = len(inp) - 2
    sl = _slots(inp, out)
    for (a, b, col) in sl:
        for r in range(m + 1):
            for c in range(a, b + 1):
                g[r][c] = 0
    for i, (a, b, col) in enumerate(sl):
        if only is not None and i not in only:
            continue
        if colors is not None:
            col = colors[i]
        h = height_of((a, b, col))
        for k in range(start_off, start_off + h):
            r = m - k
            if 0 <= r:
                for c in range(a, b + 1):
                    g[r][c] = col
    return g


def _guard(f):
    def w(inp, out):
        g = f(inp, out)
        if g is None or g == out:
            return None
        return g
    return w


def height_one(inp, out):
    return _painted(inp, out, lambda s: 1)


def height_three(inp, out):
    return _painted(inp, out, lambda s: 3)


def pieces_left(inp, out):
    g = _copy(out)
    m = len(inp) - 2
    for r in range(m):
        for c in range(len(inp[0])):
            if inp[r][c] != 0:
                g[r][c] = inp[r][c]
    return g


def swap_slot_colors(inp, out):
    sl = _slots(inp, out)
    if len(sl) < 2:
        return None
    cols = [s[2] for s in sl]
    cols[0], cols[1] = cols[1], cols[0]
    return _painted(inp, out, lambda s: 2, colors=cols)


def full_column(inp, out):
    m = len(inp) - 2
    return _painted(inp, out, lambda s: m + 1)


def all_first_color(inp, out):
    sl = _slots(inp, out)
    cols = [sl[0][2]] * len(sl)
    return _painted(inp, out, lambda s: 2, colors=cols)


def height_piece_rows(inp, out):
    def h(s):
        cells = _piece_cells(inp, s[2])
        rows = [r for r, _ in cells]
        return max(rows) - min(rows) + 1
    return _painted(inp, out, h)


def height_piece_cols(inp, out):
    def h(s):
        cells = _piece_cells(inp, s[2])
        cs = [c for _, c in cells]
        return max(cs) - min(cs) + 1
    return _painted(inp, out, h)


def into_ground(inp, out):
    g = _copy(out)
    gr = len(inp) - 1
    for (a, b, col) in _slots(inp, out):
        for c in range(a, b + 1):
            g[gr][c] = col
    return g


def lifted_one(inp, out):
    return _painted(inp, out, lambda s: 2, start_off=1)


def unchanged(inp, out):
    return _copy(inp)


def narrowest_only(inp, out):
    sl = _slots(inp, out)
    if len(sl) < 2:
        return None
    i = min(range(len(sl)), key=lambda i: sl[i][1] - sl[i][0])
    return _painted(inp, out, lambda s: 2, only={i})


ALTERNATIVES = [
    ("pieces fill each slot only one cell deep (marker row only)", _guard(height_one)),
    ("pieces fill each slot three cells deep", _guard(height_three)),
    ("pieces are copied into the slots but also stay at their original place", _guard(pieces_left)),
    ("the first two slots get each other's piece color", _guard(swap_slot_colors)),
    ("each slot is filled with its color up to the top edge of the grid", _guard(full_column)),
    ("every slot gets the color of the leftmost slot's piece", _guard(all_first_color)),
    ("fill depth equals the piece's own vertical extent", _guard(height_piece_rows)),
    ("fill depth equals the piece's own horizontal extent", _guard(height_piece_cols)),
    ("pieces sink one row too far, into the ground row", _guard(into_ground)),
    ("pieces fill the two rows above the marker row, leaving the marker row slot empty", _guard(lifted_one)),
    ("only the narrowest slot is filled", _guard(narrowest_only)),
    ("input returned unchanged", _guard(unchanged)),
]


def _valid(g):
    return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/67c52801.json').read_text())
    train = task["train"]
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
