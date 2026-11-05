"""Near-miss rules for f45f5ca7.

True rule: each colored cell in column 0 moves right by a distance fixed by
its color (8 -> 1, 2 -> 2, 4 -> 3, 3 -> 4).
"""
import json
from collections import Counter
from pathlib import Path

DIST = {8: 1, 2: 2, 4: 3, 3: 4}


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _ink(inp):
    bg = _bg(inp)
    return bg, [(r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v != bg]


def _render(inp, placer):
    """placer(r, c, v, h, w) -> (r2, c2, v2) or None to drop the cell."""
    bg, ink = _ink(inp)
    h, w = len(inp), len(inp[0])
    g = [[bg] * w for _ in range(h)]
    for r, c, v in ink:
        p = placer(r, c, v, h, w)
        if p is None:
            continue
        r2, c2, v2 = p
        if 0 <= r2 < h and 0 <= c2 < w:
            g[r2][c2] = v2
    return g


def _dist_shift(delta):
    def f(inp, out):
        return _render(inp, lambda r, c, v, h, w: (r, c + DIST[v] + delta, v))
    return f


def far_by_one(inp, out):
    return _dist_shift(1)(inp, out)


def short_by_one(inp, out):
    return _dist_shift(-1)(inp, out)


def move_down(inp, out):
    return _render(inp, lambda r, c, v, h, w: (r + DIST[v], c, v))


def rank_order_distance(inp, out):
    rank = {2: 1, 3: 2, 4: 3, 8: 4}
    return _render(inp, lambda r, c, v, h, w: (r, c + rank[v], v))


def same_distance_all(inp, out):
    return _render(inp, lambda r, c, v, h, w: (r, c + 1, v))


def keep_original_too(inp, out):
    g = [row[:] for row in out]
    for r, c, v in _ink(inp)[1]:
        g[r][c] = v
    return g


def eight_stays(inp, out):
    g = [row[:] for row in out]
    for r, c, v in _ink(inp)[1]:
        if v == 8:
            g[r][DIST[v]] = _bg(inp)
            g[r][c] = v
    return g


def from_right_edge(inp, out):
    return _render(inp, lambda r, c, v, h, w: (r, w - 1 - DIST[v], v))


def half_color_distance(inp, out):
    return _render(inp, lambda r, c, v, h, w: (r, c + v // 2, v))


def swap_three_four_colors(inp, out):
    sw = {3: 4, 4: 3}
    return _render(inp, lambda r, c, v, h, w: (r, c + DIST[v], sw.get(v, v)))


def drop_last_cell(inp, out):
    g = [row[:] for row in out]
    ink = _ink(inp)[1]
    r, c, v = ink[-1]
    g[r][DIST[v]] = _bg(inp)
    return g


def distance_by_row_parity(inp, out):
    # distance follows the row index instead of the color
    return _render(inp, lambda r, c, v, h, w: (r, c + 1 + r % 4, v))


ALTERNATIVES = [
    ("each cell moves one column too far", far_by_one),
    ("each cell moves one column too short", short_by_one),
    ("cells move down by the color distance instead of right", move_down),
    ("distance ranks colors by value (2,3,4,8 -> 1..4)", rank_order_distance),
    ("every cell moves by the same distance of 1", same_distance_all),
    ("original cells stay and copies are added", keep_original_too),
    ("color 8 cells are not moved", eight_stays),
    ("cells are placed measured from the right edge", from_right_edge),
    ("distance is half the color value", half_color_distance),
    ("colors 3 and 4 are swapped after the move", swap_three_four_colors),
    ("the last colored cell is dropped", drop_last_cell),
    ("distance depends on row index, not color", distance_by_row_parity),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/f45f5ca7.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
