import json
from pathlib import Path


def marks(inp):
    return sorted((r, c, v) for r, row in enumerate(inp) for c, v in enumerate(row) if v)


def owners(inp, tie="up", shift=0):
    ms = marks(inp)
    h = len(inp)
    res = []
    for r in range(h):
        best = None
        for mr, _, v in ms:
            d = abs(r - mr)
            key = (d, mr if tie == "up" else -mr)
            if best is None or key < best[0]:
                best = (key, mr, v)
        res.append(best[1:])
    if shift:
        res = [res[min(max(r - shift, 0), h - 1)] for r in range(h)]
    return res


def render(inp, rowcol, full, left=True, right=True):
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for r in range(h):
        col = rowcol[r]
        if col is None:
            continue
        if r in full:
            g[r] = [col] * w
        else:
            if left:
                g[r][0] = col
            if right:
                g[r][w - 1] = col
    return g


def base_full(inp):
    h = len(inp)
    return {0, h - 1} | {m[0] for m in marks(inp)}


def std_cols(inp, **kw):
    return [o[1] for o in owners(inp, **kw)]


def correct(inp):
    return render(inp, std_cols(inp), base_full(inp))


def tie_down(inp, out):
    return render(inp, std_cols(inp, tie="down"), base_full(inp))


def only_mark_rows(inp, out):
    cols = std_cols(inp)
    mrs = {m[0] for m in marks(inp)}
    return render(inp, [c if r in mrs else None for r, c in enumerate(cols)], mrs)


def full_territory_rows(inp, out):
    h = len(inp)
    return render(inp, std_cols(inp), set(range(h)))


def transposed(inp, out):
    t = [list(r) for r in zip(*inp)]
    g = render(t, std_cols(t), base_full(t))
    return [list(r) for r in zip(*g)]


def left_border_only(inp, out):
    return render(inp, std_cols(inp), base_full(inp), right=False)


def own_downward(inp, out):
    ms = marks(inp)
    h = len(inp)
    cols = []
    for r in range(h):
        prev = [m for m in ms if m[0] <= r]
        cols.append(prev[-1][2] if prev else ms[0][2])
    return render(inp, cols, base_full(inp))


def own_upward(inp, out):
    ms = marks(inp)
    h = len(inp)
    cols = []
    for r in range(h):
        nxt = [m for m in ms if m[0] >= r]
        cols.append(nxt[0][2] if nxt else ms[-1][2])
    return render(inp, cols, base_full(inp))


def shifted_boundary(inp, out):
    return render(inp, std_cols(inp, shift=1), base_full(inp))


def mark_row_unfilled(inp, out):
    mrs = {m[0] for m in marks(inp)}
    return render(inp, std_cols(inp), base_full(inp) - mrs)


def outer_rows_blank(inp, out):
    ms = marks(inp)
    lo, hi = ms[0][0], ms[-1][0]
    cols = std_cols(inp)
    cols = [c if lo <= r <= hi else None for r, c in enumerate(cols)]
    return render(inp, cols, {m[0] for m in ms})


def edge_rows_not_full(inp, out):
    return render(inp, std_cols(inp), {m[0] for m in marks(inp)})


def nearest_by_rank(inp, out):
    ms = marks(inp)
    h = len(inp)
    cols = [ms[min(len(ms) - 1, r * len(ms) // h)][2] for r in range(h)]
    return render(inp, cols, base_full(inp))


ALTERNATIVES = [
    ("tie between two equidistant marks goes down instead of up", tie_down),
    ("only the mark rows are drawn; no territory borders or edge rows", only_mark_rows),
    ("every row of a territory is drawn as a full row, not just its border cells", full_territory_rows),
    ("rule applied along columns instead of rows (transposed)", transposed),
    ("territory borders drawn on the left column only", left_border_only),
    ("each mark owns rows from itself downward to the next mark", own_downward),
    ("each mark owns rows from itself upward to the previous mark", own_upward),
    ("territory boundaries between marks shifted down by one row", shifted_boundary),
    ("mark row left as a border row instead of a full line", mark_row_unfilled),
    ("rows beyond the outermost marks left empty", outer_rows_blank),
    ("top and bottom grid edge rows not drawn as full lines", edge_rows_not_full),
    ("territory split into equal bands by mark order, ignoring distance", nearest_by_rank),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/0f63c0b9.json").read_text())
    train = task["train"]
    assert all(correct(p["input"]) == p["output"] for p in train), "base render mismatch"
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
