import json
from collections import Counter
from pathlib import Path


def _setup(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    mark = min(cnt, key=lambda k: cnt[k])
    marks = sorted((r, c) for r in range(h) for c in range(w) if inp[r][c] == mark)
    (r0, c0), (r1, c1) = marks[0], marks[1]
    dr, dc = r1 - r0, c1 - c0
    ends = [(marks[0], (-dr, -dc)), (marks[-1], (dr, dc))]
    for (p, d) in ends:
        if 0 <= p[0] + d[0] < h and 0 <= p[1] + d[1] < w:
            return h, w, bg, mark, p, d
    return h, w, bg, mark, ends[1][0], ends[1][1]


def _trace(inp, mode="normal", lookahead=1, start_skip=0):
    """Return (legs, contacts): painted cells grouped by leg, and wall cells touched."""
    h, w, bg, mark, p, d = _setup(inp)

    def cell(r, c):
        return inp[r][c] if 0 <= r < h and 0 <= c < w else None

    def wall(r, c):
        v = cell(r, c)
        return v is not None and v != bg and v != mark

    legs, contacts = [[]], []
    r, c = p
    dr, dc = d
    for _ in range(4 * (h + w)):
        nr, nc = r + dr, c + dc
        if cell(nr, nc) != bg and mode != "through":
            break
        if cell(nr, nc) is None:
            break
        r, c = nr, nc
        if cell(r, c) == bg:
            legs[-1].append((r, c))
        # deflection at the new cell
        k = lookahead
        wv = wall(r + k * dr, c)
        wh = wall(r, c + k * dc)
        if mode == "normal" or mode == "wrongaxis":
            if wv or wh:
                legs.append([])
            if wv:
                contacts.append((r + k * dr, c))
                if mode == "wrongaxis":
                    dc = -dc
                else:
                    dr = -dr
            if wh:
                contacts.append((r, c + k * dc))
                if mode == "wrongaxis":
                    dr = -dr
                else:
                    dc = -dc
    return legs, contacts


def _with(out, cells, val):
    g = [row[:] for row in out]
    for r, c in cells:
        g[r][c] = val
    return g


def _bgof(inp):
    return _setup(inp)[2]


def stop_at_wall(inp, out):
    legs, _ = _trace(inp)
    cells = legs[0]
    base = _with(inp, cells, 3)
    return base


def through_walls_bg_only(inp, out):
    h, w, bg, mark, p, d = _setup(inp)
    g = [row[:] for row in inp]
    r, c = p
    while True:
        r, c = r + d[0], c + d[1]
        if not (0 <= r < h and 0 <= c < w):
            break
        if g[r][c] == bg:
            g[r][c] = 3
    return g


def paint_over_walls(inp, out):
    h, w, bg, mark, p, d = _setup(inp)
    g = [row[:] for row in inp]
    r, c = p
    while True:
        r, c = r + d[0], c + d[1]
        if not (0 <= r < h and 0 <= c < w):
            break
        if g[r][c] != mark:
            g[r][c] = 3
    return g


def wrong_axis(inp, out):
    legs, _ = _trace(inp, mode="wrongaxis")
    return _with(inp, [x for leg in legs for x in leg], 3)


def paint_mark_color(inp, out):
    mark = _setup(inp)[3]
    return [[mark if v == 3 else v for v in row] for row in out]


def paint_wall_color(inp, out):
    h, w, bg, mark, p, d = _setup(inp)
    cnt = Counter(v for row in inp for v in row)
    wallc = [k for k in cnt if k not in (bg, mark)][0]
    return [[wallc if v == 3 else v for v in row] for row in out]


def unchanged(inp, out):
    return [row[:] for row in inp]


def bounce_early(inp, out):
    legs, _ = _trace(inp, lookahead=2)
    return _with(inp, [x for leg in legs for x in leg], 3)


def paint_contact(inp, out):
    _, contacts = _trace(inp)
    return _with(out, contacts, 3)


def skip_first_cell(inp, out):
    legs, _ = _trace(inp)
    return _with(out, [legs[0][0]], _bgof(inp))


def drop_last_cell(inp, out):
    legs, _ = _trace(inp)
    last = [leg for leg in legs if leg][-1][-1]
    return _with(out, [last], _bgof(inp))


def only_reflected_leg(inp, out):
    legs, _ = _trace(inp)
    return _with(inp, [x for leg in legs[1:] for x in leg], 3)


ALTERNATIVES = [
    ("beam stops at the first wall instead of reflecting", stop_at_wall),
    ("beam ignores walls and runs straight to the edge, painting background cells only", through_walls_bg_only),
    ("beam paints over wall cells and runs straight to the edge", paint_over_walls),
    ("reflection flips the wrong direction component", wrong_axis),
    ("beam is painted in the mark color instead of 3", paint_mark_color),
    ("beam is painted in the wall color instead of 3", paint_wall_color),
    ("no beam is drawn; input unchanged", unchanged),
    ("beam turns one cell before the wall", bounce_early),
    ("beam also paints the wall cell it reflects off", paint_contact),
    ("beam starts one cell after the mark tip", skip_first_cell),
    ("beam ends one cell short", drop_last_cell),
    ("only the reflected leg is painted", only_reflected_leg),
]


def _valid(g):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/508bd3b6.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
