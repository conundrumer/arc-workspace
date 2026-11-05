import json
from pathlib import Path

BG = 7


def _pieces(inp, conn=4):
    h, w = len(inp), len(inp[0])
    if conn == 4:
        nbrs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    else:
        nbrs = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == BG or (r, c) in seen:
                continue
            comp = []
            stack = [(r, c)]
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in nbrs:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != BG and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            res.append(sorted(comp))
    return res


def _copy(g):
    return [row[:] for row in g]


def _bbox(p):
    ys = [y for y, _ in p]
    xs = [x for _, x in p]
    return min(ys), min(xs), max(ys), max(xs)


def _piece_color(out, p):
    return out[p[0][0]][p[0][1]]


def _first_seen_key(inp, out, keyfn):
    ps = _pieces(inp)
    first = {}
    for p in ps:
        first.setdefault(keyfn(p), _piece_color(out, p))
    res = _copy(out)
    for p in ps:
        for y, x in p:
            res[y][x] = first[keyfn(p)]
    return res


def by_size(inp, out):
    return _first_seen_key(inp, out, len)


def by_bbox(inp, out):
    def k(p):
        y0, x0, y1, x1 = _bbox(p)
        return tuple(sorted((y1 - y0 + 1, x1 - x0 + 1)))
    return _first_seen_key(inp, out, k)


def small_unpainted(inp, out):
    res = _copy(out)
    for p in _pieces(inp):
        if len(p) < 3:
            for y, x in p:
                res[y][x] = inp[y][x]
    return res


def big_only(inp, out):
    res = _copy(out)
    for p in _pieces(inp):
        if len(p) < 5:
            for y, x in p:
                res[y][x] = inp[y][x]
    return res


def all_largest_color(inp, out):
    ps = _pieces(inp)
    big = max(ps, key=len)
    col = _piece_color(out, big)
    res = _copy(out)
    for p in ps:
        for y, x in p:
            res[y][x] = col
    return res


def swap_two_colors(inp, out):
    ps = _pieces(inp)
    by_len = {}
    for p in ps:
        by_len[len(p)] = _piece_color(out, p)
    a, b = by_len.get(5), by_len.get(6)
    if a is None or b is None:
        return None
    res = _copy(out)
    for y, row in enumerate(out):
        for x, v in enumerate(row):
            if v == a:
                res[y][x] = b
            elif v == b:
                res[y][x] = a
    return res


def mirrored(inp, out):
    return [row[::-1] for row in out]


def border_unpainted(inp, out):
    h, w = len(inp), len(inp[0])
    res = _copy(out)
    for p in _pieces(inp):
        if any(y in (0, h - 1) or x in (0, w - 1) for y, x in p):
            for y, x in p:
                res[y][x] = inp[y][x]
    return res


def eight_connected(inp, out):
    res = _copy(out)
    for comp in _pieces(inp, 8):
        cnt = {}
        for y, x in comp:
            cnt[out[y][x]] = cnt.get(out[y][x], 0) + 1
        col = max(sorted(cnt), key=lambda k: cnt[k])
        for y, x in comp:
            res[y][x] = col
    return res


def fill_bbox(inp, out):
    res = _copy(out)
    for p in _pieces(inp):
        y0, x0, y1, x1 = _bbox(p)
        col = _piece_color(out, p)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                res[y][x] = col
    return res


def unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("pieces keyed by cell count alone; the first piece of each size sets its color", by_size),
    ("pieces keyed by bounding-box dimensions up to rotation; the first of each box sets its color", by_bbox),
    ("pieces of fewer than 3 cells are left unrecolored", small_unpainted),
    ("only pieces of 5 or more cells are recolored", big_only),
    ("every piece takes the color of the largest piece", all_largest_color),
    ("the colors of the 5-cell and 6-cell shapes are swapped", swap_two_colors),
    ("output is the correct recoloring mirrored left to right", mirrored),
    ("pieces touching the grid border are left unrecolored", border_unpainted),
    ("pieces use 8-connectivity; each merged piece takes the majority color", eight_connected),
    ("each piece's whole bounding box is filled with its color", fill_bbox),
    ("no recoloring: output is the input", unchanged),
]


def _valid(g, out):
    return (
        isinstance(g, list)
        and g
        and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        and g != out
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/ad38a9d0.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
