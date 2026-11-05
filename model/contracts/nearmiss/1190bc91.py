"""Near-miss readings for 1190bc91.

Rule: a straight line of distinct colors runs from an edge into the grid.
Each of its cells shoots four diagonal rays in its own color. A cell goes to
the nearest line cell (counted from the end away from the edge), and a ray
stops where it meets a cell a nearer line cell already took. Cells no ray
reaches take the color of the single-color marker blob in their region, if
the region has one.
"""
import json
from collections import Counter
from pathlib import Path

DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
ORTH = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _comps(cells, conn8=False):
    cells = set(cells)
    steps = ORTH + (DIAG if conn8 else [])
    seen, res = set(), []
    for c in sorted(cells):
        if c in seen:
            continue
        st, comp = [c], []
        seen.add(c)
        while st:
            r, q = st.pop()
            comp.append((r, q))
            for dr, dc in steps:
                n = (r + dr, q + dc)
                if n in cells and n not in seen:
                    seen.add(n)
                    st.append(n)
        res.append(comp)
    return res


def _parse(inp):
    """Return (bg, line cells from the end away from the edge, edge direction)."""
    H, W = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    objs = _comps([(r, c) for r in range(H) for c in range(W) if inp[r][c] != bg])
    for comp in objs:
        if len(comp) < 2:
            continue
        rs = sorted({r for r, c in comp})
        cs = sorted({c for r, c in comp})
        if len(cs) == 1:
            c = cs[0]
            if rs[-1] == H - 1:
                return bg, [(r, c) for r in rs], (1, 0)
            if rs[0] == 0:
                return bg, [(r, c) for r in reversed(rs)], (-1, 0)
        if len(rs) == 1:
            r = rs[0]
            if cs[-1] == W - 1:
                return bg, [(r, c) for c in cs], (0, 1)
            if cs[0] == 0:
                return bg, [(r, c) for c in reversed(cs)], (0, -1)
    return None


def solve(inp, dirs="diag", stop="lit", winner="near", fill="area4", color="own",
          anchor="far", rays_from="all", reach=None, stop_at_obj=False):
    H, W = len(inp), len(inp[0])
    bg, seq, edir = _parse(inp)
    if anchor == "edge":
        seq = list(reversed(seq))
    n = len(seq)
    steps = DIAG if dirs == "diag" else ORTH
    if dirs == "back":
        steps = [d for d in DIAG if d[0] * edir[0] + d[1] * edir[1] < 0]
    if dirs == "fwd":
        steps = [d for d in DIAG if d[0] * edir[0] + d[1] * edir[1] > 0]
    col = [inp[r][c] for r, c in seq]
    best = {}
    for k, p in enumerate(seq):
        best[p] = (k, col[k])
    order = range(n) if winner == "near" else range(n - 1, -1, -1)
    for k in order:
        if rays_from == "anchor" and k != 0:
            continue
        r, c = seq[k]
        if color == "own":
            v = col[k]
        elif color == "anchor":
            v = col[0]
        else:  # off by one along the line
            v = col[min(k + 1, n - 1)]
        for dr, dc in steps:
            rr, cc = r + dr, c + dc
            length = 0
            while 0 <= rr < H and 0 <= cc < W:
                if reach is not None and length >= reach:
                    break
                if stop_at_obj and inp[rr][cc] != bg and (rr, cc) not in best:
                    break
                if (rr, cc) in best:
                    if stop == "lit" or best[(rr, cc)][0] == -2:
                        break
                    if winner == "near" and best[(rr, cc)][0] <= k:
                        rr += dr
                        cc += dc
                        length += 1
                        continue
                    if winner != "near" and (rr, cc) in seq:
                        break
                best[(rr, cc)] = (k, v)
                rr += dr
                cc += dc
                length += 1
    out = [[bg] * W for _ in range(H)]
    for (r, c), (k, v) in best.items():
        out[r][c] = v
    unlit = [(r, c) for r in range(H) for c in range(W) if (r, c) not in best]
    if fill == "none":
        for r, c in unlit:
            out[r][c] = inp[r][c]
    elif fill in ("area4", "area8"):
        for comp in _comps(unlit, conn8=(fill == "area8")):
            cols = {inp[r][c] for r, c in comp if inp[r][c] != bg}
            if len(cols) == 1:
                for r, c in comp:
                    out[r][c] = next(iter(cols))
    elif fill == "nearest":
        marks = [(r, c) for r, c in unlit if inp[r][c] != bg]
        for r, c in unlit:
            if marks:
                m = min(marks, key=lambda q: (abs(q[0] - r) + abs(q[1] - c), q))
                out[r][c] = inp[m[0]][m[1]]
    elif fill == "all_unlit_first":
        # every unlit cell takes the first marker color found in reading order
        marks = [inp[r][c] for r, c in unlit if inp[r][c] != bg]
        for r, c in unlit:
            if marks:
                out[r][c] = marks[0]
    return out


def _wrap(**kw):
    def f(inp, out):
        if _parse(inp) is None:
            return None
        return solve(inp, **kw)
    return f


ALTERNATIVES = [
    ("rays never stop; the nearest line cell still wins every cell",
     _wrap(stop="none")),
    ("the farthest line cell wins overlapping cells instead of the nearest",
     _wrap(winner="far", stop="none")),
    ("the sequence is read from the edge end, so the edge cell is index 0",
     _wrap(anchor="edge")),
    ("only the diagonals pointing away from the line's edge are drawn",
     _wrap(dirs="back")),
    ("only the diagonals pointing toward the line's edge are drawn",
     _wrap(dirs="fwd")),
    ("rays go orthogonally (plus shaped) instead of diagonally",
     _wrap(dirs="orth")),
    ("only the anchor cell shoots rays",
     _wrap(rays_from="anchor")),
    ("every ray has the anchor color",
     _wrap(color="anchor")),
    ("each ray takes the color of the next line cell (off by one)",
     _wrap(color="next")),
    ("rays reach only one cell from the line",
     _wrap(reach=1)),
    ("markers do not flood; unlit cells keep their input value",
     _wrap(fill="none")),
    ("unlit cells take the color of the nearest marker cell, even in unmarked regions",
     _wrap(fill="nearest")),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/1190bc91.json"))
    train = task["train"]

    def valid(g, out):
        return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                        for r in g for v in r) and g != out)

    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
