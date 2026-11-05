import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _boxes(inp):
    """8-connected components of non-background cells, as (cells, bbox)."""
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] == bg or (i, j) in seen:
                continue
            st = [(i, j)]
            seen.add((i, j))
            cells = []
            while st:
                a, b = st.pop()
                cells.append((a, b))
                for da in (-1, 0, 1):
                    for db in (-1, 0, 1):
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and (x, y) not in seen and inp[x][y] != bg:
                            seen.add((x, y))
                            st.append((x, y))
            rs = [c[0] for c in cells]
            cs = [c[1] for c in cells]
            res.append((cells, (min(rs), min(cs), max(rs), max(cs))))
    return res


def _inside(p, bb):
    return bb[0] <= p[0] <= bb[2] and bb[1] <= p[1] <= bb[3]


def _fours(inp, out):
    bg = _bg(inp)
    return {(i, j) for i, r in enumerate(out) for j, v in enumerate(r) if v != inp[i][j] and inp[i][j] == bg}


def _doors(inp, out):
    bbs = [b for _, b in _boxes(inp)]
    return {p for p in _fours(inp, out) if any(_inside(p, b) for b in bbs)}


def _bbox(cells):
    rs = [c[0] for c in cells]
    cs = [c[1] for c in cells]
    return (min(rs), min(cs), max(rs), max(cs))


def _paint(inp, cells, color, only_bg=True):
    g = [r[:] for r in inp]
    bg = _bg(inp)
    for i, j in cells:
        if 0 <= i < len(g) and 0 <= j < len(g[0]) and (not only_bg or g[i][j] == bg):
            g[i][j] = color
    return g


def _rect(bb):
    return {(i, j) for i in range(bb[0], bb[2] + 1) for j in range(bb[1], bb[3] + 1)}


def _col(out, inp):
    f = _fours(inp, out)
    return out[next(iter(f))[0]][next(iter(f))[1]]


def doors_only(inp, out):
    return _paint(inp, _doors(inp, out), _col(out, inp))


def doors_and_outer_neighbors_only(inp, out):
    f = _fours(inp, out)
    d = _doors(inp, out)
    bbs = [b for _, b in _boxes(inp)]
    cells = set(d)
    for (i, j) in d:
        for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if (a, b) in f and not any(_inside((a, b), bb) for bb in bbs):
                cells.add((a, b))
    return _paint(inp, cells, _col(out, inp))


def shadow_ignored(inp, out):
    f = _fours(inp, out)
    return _paint(inp, _rect(_bbox(f)), _col(out, inp))


def span_from_door_cells(inp, out):
    d = _doors(inp, out)
    bb = _bbox(d)
    f = {p for p in _fours(inp, out) if _inside(p, bb)}
    return _paint(inp, f, _col(out, inp))


def span_overwrites_boxes(inp, out):
    f = _fours(inp, out)
    return _paint(inp, _rect(_bbox(f)), _col(out, inp), only_bg=False)


def span_grown_by_one(inp, out):
    f = _fours(inp, out)
    b = _bbox(f)
    big = (b[0] - 1, b[1] - 1, b[2] + 1, b[3] + 1)
    keep = {p for p in _rect(big)}
    g = _paint(inp, keep, _col(out, inp))
    for i, j in f:
        g[i][j] = out[i][j]
    return g if g != out else None


def span_shrunk_by_one(inp, out):
    f = _fours(inp, out)
    b = _bbox(f)
    small = (b[0] + 1, b[1] + 1, b[2] - 1, b[3] - 1)
    cells = {p for p in f if _inside(p, small)} | _doors(inp, out)
    return _paint(inp, cells, _col(out, inp))


def doors_left_open(inp, out):
    d = _doors(inp, out)
    g = [r[:] for r in out]
    for i, j in d:
        g[i][j] = inp[i][j]
    return g


def hull_of_boxes(inp, out):
    bb = _bbox([c for cells, _ in _boxes(inp) for c in cells])
    cells = _rect(bb) | _doors(inp, out)
    return _paint(inp, cells, _col(out, inp))


def fill_color_5(inp, out):
    c = _col(out, inp)
    return [[5 if v == c and inp[i][j] != c else v for j, v in enumerate(r)] for i, r in enumerate(out)]


def fill_color_box(inp, out):
    c = _col(out, inp)
    return [[2 if v == c and inp[i][j] != c else v for j, v in enumerate(r)] for i, r in enumerate(out)]


def only_first_box_door(inp, out):
    """Only the first box found (reading order) is opened and joined to the span."""
    bbs = _boxes(inp)
    if len(bbs) < 2:
        return None
    d = _doors(inp, out)
    first = bbs[0][1]
    f = _fours(inp, out)
    keep_doors = {p for p in d if _inside(p, first)}
    bb = _bbox(keep_doors | {p for p in f if not any(_inside(p, b) for _, b in bbs)})
    cells = keep_doors | {p for p in f if _inside(p, bb) and p not in d}
    return _paint(inp, cells, _col(out, inp))


ALTERNATIVES = [
    ("Only the door gaps are painted; no span rectangle", doors_only),
    ("Door gaps and their outside neighbours painted, no rectangle between them", doors_and_outer_neighbors_only),
    ("Shadow ignored: the whole span rectangle is painted, including shadow cells", shadow_ignored),
    ("Span rectangle taken from the door cells, not their outside neighbours", span_from_door_cells),
    ("Span rectangle overwrites box walls and centre cells too", span_overwrites_boxes),
    ("Span rectangle grown by one cell on every side", span_grown_by_one),
    ("Span rectangle shrunk by one cell on every side", span_shrunk_by_one),
    ("Rectangle painted but door gaps left unpainted", doors_left_open),
    ("Rectangle is the hull of all boxes instead of the door span", hull_of_boxes),
    ("Fill color is 5 (the box centre color) instead of 4", fill_color_5),
    ("Fill color is 2 (the box wall color) instead of 4", fill_color_box),
    ("Only the first box's door is used to build the span", only_first_box_door),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/692cd3b6.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, len(pairs), desc)
