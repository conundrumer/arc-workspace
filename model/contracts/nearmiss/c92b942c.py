import json
from pathlib import Path

LC, DC = 1, 3
UL_DR = [(-1, -1), (1, 1)]


def _tile(inp, kr, kc):
    h, w = len(inp), len(inp[0])
    return [[inp[r % h][c % w] for c in range(w * kc)] for r in range(h * kr)]


def _marks(g):
    return [(r, c, v) for r, row in enumerate(g) for c, v in enumerate(row) if v != 0]


def render(inp, k=None, kc=None, axis="row", dirs=UL_DR, lc=LC, dc=DC,
           mark_over=False, wrap=False, one_sided=False, rays=False, dc_mark=False, out=None):
    h, w = len(inp), len(inp[0])
    if k is None:
        k = len(out) // h
    if kc is None:
        kc = k
    g = _tile(inp, k, kc)
    H, W = len(g), len(g[0])
    marks = _marks(g)
    res = [row[:] for row in g]
    for r, c, v in marks:
        if axis == "row":
            cols = range(c + 1, W) if one_sided else range(W)
            for cc in cols:
                if res[r][cc] == 0:
                    res[r][cc] = lc
        else:
            for rr in range(H):
                if res[rr][c] == 0:
                    res[rr][c] = lc
    for r, c, v in marks:
        col = v if dc_mark else dc
        for dr, dcc in dirs:
            nr, nc = r + dr, c + dcc
            while True:
                if wrap:
                    nr, nc = nr % H, nc % W
                elif not (0 <= nr < H and 0 <= nc < W):
                    break
                if g[nr][nc] == 0:
                    res[nr][nc] = col
                if not rays:
                    break
                nr, nc = nr + dr, nc + dcc
                if wrap:
                    break
    if mark_over:
        for r, c, v in marks:
            res[r][c] = lc
    return res


def _ok(res, out):
    return res if res != out else None


def baseline(inp, out):
    return render(inp, out=out)


def col_lines(inp, out):
    return render(inp, out=out, axis="col")


def anti_diag(inp, out):
    return render(inp, out=out, dirs=[(-1, 1), (1, -1)])


def four_diag(inp, out):
    return render(inp, out=out, dirs=[(-1, -1), (1, 1), (-1, 1), (1, -1)])


def marks_overwritten(inp, out):
    return render(inp, out=out, mark_over=True)


def untiled(inp, out):
    return render(inp, k=1)


def one_fewer_tile(inp, out):
    return render(inp, k=len(out) // len(inp) - 1)


def one_more_tile(inp, out):
    return render(inp, k=len(out) // len(inp) + 1)


def swapped_colors(inp, out):
    return render(inp, out=out, lc=DC, dc=LC)


def wrapped_diag(inp, out):
    return _ok(render(inp, out=out, wrap=True), out)


def line_right_only(inp, out):
    return render(inp, out=out, one_sided=True)


def diag_rays(inp, out):
    return _ok(render(inp, out=out, rays=True), out)


def diag_in_mark_color(inp, out):
    return render(inp, out=out, dc_mark=True)


ALTERNATIVES = [
    ("line runs along the mark's column instead of its row", col_lines),
    ("diagonal corners on the anti-diagonal (up-right, down-left)", anti_diag),
    ("diagonal corners in all four diagonal directions", four_diag),
    ("marks are overwritten by the line color", marks_overwritten),
    ("input is not tiled (one copy)", untiled),
    ("tile count one too small", one_fewer_tile),
    ("tile count one too large", one_more_tile),
    ("line color and corner color swapped", swapped_colors),
    ("diagonal steps leaving the tiled grid wrap around", wrapped_diag),
    ("line extends only to the right of each mark", line_right_only),
    ("diagonals extend as full rays instead of one step", diag_rays),
    ("diagonal corners take the mark color", diag_in_mark_color),
]


def _valid(g):
    return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/c92b942c.json"))
    train = task["train"]
    for p in train:
        assert baseline(p["input"], p["output"]) == p["output"], "baseline mismatch"
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
