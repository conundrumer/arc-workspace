"""Near-miss rules for ac605cbb.

Rule: each seed color draws a fixed stamp from the seed: a line of 5 and an
end cell in the seed's color. Where two stamps' lines share a cell, that cell
becomes 4 and a diagonal ray of 4 goes from it toward the lower left to the
grid edge.
"""
import json
from pathlib import Path

# color -> (line offsets (dr, dc), end offset (dr, dc))
STAMPS = {
    1: ([(0, 1), (0, 2)], (-1, 2)),
    2: ([(0, -1), (0, -2), (0, -3)], (0, -4)),
    3: ([(1, 0), (2, 0)], (3, 0)),
    6: ([(-1, 0), (-2, 0), (-3, 0), (-4, 0), (-5, 0)], (-6, 0)),
}


def _sim(inp, stamp_of=None, line_col=5, end_col=None, cross_col=4,
         ray_dir=(1, -1), ray_len=None, keep_seed=True, draw_end=True,
         draw_ray=True, cross=True, xform=None):
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    seeds = [(r, c, inp[r][c]) for r in range(h) for c in range(w) if inp[r][c]]

    def put(r, c, v):
        if 0 <= r < h and 0 <= c < w:
            g[r][c] = v

    line_owner = {}
    ends = []
    for r, c, col in seeds:
        line, end = STAMPS[stamp_of(col) if stamp_of else col]
        if xform:
            line = [xform(o) for o in line]
            end = xform(end)
        for dr, dc in line:
            line_owner.setdefault((r + dr, c + dc), set()).add((r, c))
        ends.append((r + end[0], c + end[1], col if end_col is None else end_col))
    crossings = []
    for (r, c), own in line_owner.items():
        put(r, c, line_col)
        if len(own) > 1:
            crossings.append((r, c))
    if draw_end:
        for r, c, col in ends:
            put(r, c, col)
    for r, c in crossings:
        put(r, c, cross_col if cross else line_col)
    if draw_ray and cross:
        for r, c in crossings:
            k = 1
            while ray_len is None or k <= ray_len:
                rr, cc = r + ray_dir[0] * k, c + ray_dir[1] * k
                if not (0 <= rr < h and 0 <= cc < w):
                    break
                if g[rr][cc] == 0:
                    g[rr][cc] = cross_col
                k += 1
    if not keep_seed:
        for r, c, _ in seeds:
            g[r][c] = 0
    else:
        for r, c, col in seeds:
            g[r][c] = col
    return g


def _wrap(**kw):
    def f(inp, out):
        g = _sim(inp, **kw)
        return None if g == out else g
    return f


def _end_too_near(inp, out):
    # the end cell is drawn one cell earlier, so the stamp has one line cell fewer
    h, w = len(inp), len(inp[0])
    base = _sim(inp)
    seeds = [(r, c, inp[r][c]) for r in range(h) for c in range(w) if inp[r][c]]
    for r, c, col in seeds:
        line, end = STAMPS[col]
        er, ec = r + end[0], c + end[1]
        last = line[-1]
        lr, lc = r + last[0], c + last[1]
        if (er, ec) != (lr, lc) and 0 <= er < h and 0 <= ec < w:
            base[er][ec] = 0
        # end cell replaces the last line cell
        if 0 <= lr < h and 0 <= lc < w:
            base[lr][lc] = col
    return None if base == out else base


def _ray_wall_stop(inp, out):
    # the ray stops after one cell
    g = _sim(inp, ray_len=1)
    return None if g == out else g


ALTERNATIVES = [
    ("the crossing cell and its ray are drawn in the line color 5 instead of 4",
     _wrap(cross_col=5)),
    ("the crossing cell is 4 but no ray is drawn",
     _wrap(draw_ray=False)),
    ("the ray runs to the lower right instead of the lower left",
     _wrap(ray_dir=(1, 1))),
    ("the ray runs to the upper left instead of the lower left",
     _wrap(ray_dir=(-1, -1))),
    ("the ray is only one cell long",
     _ray_wall_stop),
    ("the end cell of each stamp is the line color 5 instead of the seed color",
     _wrap(end_col=5)),
    ("each stamp's line is drawn but its end cell is left out",
     _wrap(draw_end=False)),
    ("each stamp is drawn flipped top to bottom",
     _wrap(xform=lambda o: (-o[0], o[1]))),
    ("each stamp is rotated a quarter turn clockwise about its seed",
     _wrap(xform=lambda o: (o[1], -o[0]))),
    ("every seed uses the stamp of color 1, whatever its color",
     _wrap(stamp_of=lambda col: 1)),
    ("the seed cells are erased after the stamps are drawn",
     _wrap(keep_seed=False)),
    ("each stamp is one cell short: the end cell lands on the last line cell",
     _end_too_near),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
               for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/ac605cbb.json").read_text())
    train = task["train"]
    for p in train:
        assert _sim(p["input"]) == p["output"], "simulator mismatch"
    print(f"readings={len(ALTERNATIVES)} pairs={len(train)}")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn([r[:] for r in p["input"]], [r[:] for r in p["output"]])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
