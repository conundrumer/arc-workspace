"""Near-miss readings for ARC task b27ca6d3."""
import json
from collections import Counter
from pathlib import Path

FRAME = 3

N4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
N8 = N4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _groups(inp, nbrs=N4):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    groups = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] == bg or (i, j) in seen:
                continue
            stack = [(i, j)]
            seen.add((i, j))
            cells = []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da, db in nbrs:
                    p, q = a + da, b + db
                    if 0 <= p < h and 0 <= q < w and (p, q) not in seen and inp[p][q] != bg:
                        seen.add((p, q))
                        stack.append((p, q))
            groups.append(cells)
    return groups


def _paint(inp, groups, offsets, over_marks=False, color=FRAME, wrap=False, pair_color=None):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    res = [r[:] for r in inp]
    for g in groups:
        gs = set(g)
        for a, b in g:
            for da, db in offsets:
                p, q = a + da, b + db
                if wrap:
                    p, q = p % h, q % w
                if not (0 <= p < h and 0 <= q < w) or (p, q) in gs:
                    continue
                if inp[p][q] == bg or over_marks:
                    res[p][q] = color
        if pair_color is not None:
            for a, b in g:
                res[a][b] = pair_color
    return res


def _pairs(inp, k=2, nbrs=N4):
    return [g for g in _groups(inp, nbrs) if len(g) == k]


def _singles(inp):
    return _pairs(inp, 1)


def side_only(inp, out):
    return _paint(inp, _pairs(inp), N4)


def horizontal_only(inp, out):
    ps = [g for g in _pairs(inp) if len({a for a, _ in g}) == 1]
    return _paint(inp, ps, N8)


def recolor_pair(inp, out):
    return _paint(inp, _pairs(inp), [], pair_color=FRAME)


def singles_framed(inp, out):
    return _paint(inp, _singles(inp), N8)


def all_groups_framed(inp, out):
    return _paint(inp, _groups(inp), N8)


def first_cell_only(inp, out):
    """Frame only the 3x3 neighborhood of the first cell of each pair."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    res = [r[:] for r in inp]
    for g in _pairs(inp):
        a, b = min(g)
        for da, db in N8:
            p, q = a + da, b + db
            if 0 <= p < h and 0 <= q < w and (p, q) not in g and inp[p][q] == bg:
                res[p][q] = FRAME
    return res


def thick_ring(inp, out):
    offs = [(a, b) for a in range(-2, 3) for b in range(-2, 3)]
    return _paint(inp, _pairs(inp), offs)


def wrap_around(inp, out):
    return _paint(inp, _pairs(inp), N8, wrap=True)


def shifted_down(inp, out):
    offs = [(a + 1, b) for a, b in N8] + [(1, 0)]
    return _paint(inp, _pairs(inp), [(a + 1, b) for a in range(-1, 2) for b in range(-1, 2)])


def long_axis_only(inp, out):
    """Frame only the two sides across the pair's long axis (end caps missing)."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    res = [r[:] for r in inp]
    for g in _pairs(inp):
        gs = set(g)
        rows = {a for a, _ in g}
        horizontal = len(rows) == 1
        offs = [(da, db) for da, db in N8 if (da != 0 if horizontal else db != 0)]
        for a, b in g:
            for da, db in offs:
                p, q = a + da, b + db
                if 0 <= p < h and 0 <= q < w and (p, q) not in gs and inp[p][q] == bg:
                    res[p][q] = FRAME
    return res


def wrong_color(inp, out):
    marks = {c for r in inp for c in r} - {_bg(inp)}
    mark = next(iter(marks))
    return _paint(inp, _pairs(inp), N8, color=mark)


def box_filled_with_pair(inp, out):
    """Frame the pair but also paint the whole union of frame boxes, leaving only the pair."""
    return _paint(inp, _pairs(inp) + _singles(inp)[:1], N8)


ALTERNATIVES = [
    ("frame only touches the pair at sides, no corner cells", side_only),
    ("only horizontal pairs get a frame", horizontal_only),
    ("pair cells are recolored instead of surrounded by a frame", recolor_pair),
    ("single marks get the frame instead of pairs", singles_framed),
    ("every group of marks gets a frame, not only pairs", all_groups_framed),
    ("frame surrounds only the first cell of each pair", first_cell_only),
    ("frame is two cells thick", thick_ring),
    ("frame wraps around the grid edges", wrap_around),
    ("frame is placed one row too low", shifted_down),
    ("frame omits the end caps beyond the pair's short sides", long_axis_only),
    ("frame is drawn in the mark color", wrong_color),
    ("a frame is also drawn around the first single mark", box_filled_with_pair),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/b27ca6d3.json").read_text())
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
