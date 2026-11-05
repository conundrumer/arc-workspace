"""Near-miss readings for a8d7556c: fill big all-0 rectangles (sides >= 2) with 2."""
import json
from pathlib import Path

HOLE, FILL = 0, 2


def _copy(g):
    return [row[:] for row in g]


def _greedy(inp, min_h, min_w, square=False, once=False, smallest_first=False):
    """Greedy fill of all-HOLE rectangles; returns grid."""
    g = _copy(inp)
    H, W = len(g), len(g[0])
    claimed = [[False] * W for _ in range(H)]
    while True:
        best = None
        for r1 in range(H):
            for c1 in range(W):
                for r2 in range(r1 + min_h - 1, H):
                    if any(g[r2][c] != HOLE or claimed[r2][c] for c in range(c1, c1 + 1)):
                        break
                    for c2 in range(c1 + min_w - 1, W):
                        h, w = r2 - r1 + 1, c2 - c1 + 1
                        if any(g[r][c2] != HOLE or claimed[r][c2] for r in range(r1, r2 + 1)):
                            break
                        # check full rectangle (cheap: all rows up to r2 at col c2 checked; rows checked per r2)
                        if not all(g[r][c] == HOLE and not claimed[r][c]
                                   for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)):
                            break
                        if square and h != w:
                            continue
                        key = (h * w) if not smallest_first else -(h * w)
                        if best is None or key > best[0]:
                            best = (key, r1, c1, r2, c2)
        if best is None:
            break
        _, r1, c1, r2, c2 = best
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                claimed[r][c] = True
        if once:
            break
    for r in range(H):
        for c in range(W):
            if claimed[r][c]:
                g[r][c] = FILL
    return g


def _fill_runs_rows(inp):
    """Fill horizontal runs of >= 2 hole cells (rows only)."""
    g = _copy(inp)
    for row in g:
        c = 0
        while c < len(row):
            if row[c] == HOLE:
                d = c
                while d < len(row) and row[d] == HOLE:
                    d += 1
                if d - c >= 2:
                    for k in range(c, d):
                        row[k] = FILL
                c = d
            else:
                c += 1
    return g


def _fill_every_hole(inp, out):
    return [[FILL if v == HOLE else v for v in row] for row in inp]


def _min3(inp, out):
    return _greedy(inp, 3, 3)


def _vert_runs(inp, out):
    return _greedy(inp, 2, 1)


def _wrong_color(inp, out):
    return [[8 if v == FILL else v for v in row] for row in out]


def _largest_only(inp, out):
    return _greedy(inp, 2, 2, once=True)


def _squares_only(inp, out):
    return _greedy(inp, 2, 2, square=True)


def _smallest_first(inp, out):
    return _greedy(inp, 2, 2, smallest_first=True)


def _erode(inp, out):
    H, W = len(out), len(out[0])
    g = _copy(out)
    for r in range(H):
        for c in range(W):
            if out[r][c] == FILL:
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    rr, cc = r + dr, c + dc
                    if not (0 <= rr < H and 0 <= cc < W) or out[rr][cc] != FILL:
                        g[r][c] = HOLE
                        break
    return g


def _dilate(inp, out):
    H, W = len(out), len(out[0])
    g = _copy(out)
    for r in range(H):
        for c in range(W):
            if out[r][c] == FILL:
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < H and 0 <= cc < W:
                            g[rr][cc] = FILL
    return g


def _drop_smallest_rects(inp, out):
    """Leave the rectangles of smallest area unfilled."""
    H, W = len(out), len(out[0])
    seen = set()
    comps = []
    for r in range(H):
        for c in range(W):
            if out[r][c] == FILL and (r, c) not in seen:
                stack, comp = [(r, c)], []
                seen.add((r, c))
                while stack:
                    a, b = stack.pop()
                    comp.append((a, b))
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        x, y = a + da, b + db
                        if 0 <= x < H and 0 <= y < W and out[x][y] == FILL and (x, y) not in seen:
                            seen.add((x, y))
                            stack.append((x, y))
                comps.append(comp)
    if not comps:
        return None
    m = min(len(c) for c in comps)
    g = _copy(out)
    for comp in comps:
        if len(comp) == m:
            for a, b in comp:
                g[a][b] = HOLE
    return g


def _transpose_fill(inp, out):
    """Fill the transposed positions of the true rectangles."""
    H, W = len(out), len(out[0])
    g = _copy(inp)
    for r in range(H):
        for c in range(W):
            if out[r][c] == FILL and c < H and r < W:
                g[c][r] = FILL
    return g


ALTERNATIVES = [
    ("fill every hole cell, not only those inside large rectangles", _fill_every_hole),
    ("minimum rectangle side 3 instead of 2", _min3),
    ("only height is required to be 2, so vertical 1-wide strips count too", _vert_runs),
    ("right rectangles painted with color 8 instead of 2", _wrong_color),
    ("only the single largest rectangle is filled", _largest_only),
    ("only square rectangles are filled", _squares_only),
    ("rectangles taken smallest area first instead of largest", _smallest_first),
    ("each filled rectangle shrunk by one cell on every side (border left unfilled)", _erode),
    ("each filled rectangle grown by one cell on every side", _dilate),
    ("smallest filled rectangles are left unfilled", _drop_smallest_rects),
    ("horizontal runs of two or more hole cells are filled, ignoring the vertical extent", lambda i, o: _fill_runs_rows(i)),
    ("rectangle positions transposed (row and column swapped)", _transpose_fill),
]


def _valid(g, true):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != true


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/a8d7556c.json"))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
