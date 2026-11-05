import json
from pathlib import Path


def _bars(inp):
    """Per color: (r0, r1, left col, right col) of the bounding box."""
    pos = {}
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v:
                pos.setdefault(v, []).append((r, c))
    res = {}
    for col, ps in pos.items():
        rs = [p[0] for p in ps]
        cs = [p[1] for p in ps]
        res[col] = (min(rs), max(rs), min(cs), max(cs))
    return res


def _render(inp, extra=0, spread=1, mode="out", up=True, down=True,
            colors=None, overlap=6, keep=True, per_row=False):
    h, w = len(inp), len(inp[0])
    cells = {}
    for col, (r0, r1, l, r) in _bars(inp).items():
        if colors is not None and col not in colors:
            continue
        n = r1 - r0 + 1
        stride = n + extra
        for k in range(-h, h + 1):
            if k < 0 and not up:
                continue
            if k > 0 and not down:
                continue
            if k == 0 and not keep:
                continue
            top = r0 + k * stride
            for i in range(n):
                row = top + i
                if not 0 <= row < h:
                    continue
                if per_row:
                    d = (r0 - row) if row < r0 else (row - r1 if row > r1 else 0)
                else:
                    d = abs(k)
                off = spread * d
                if mode == "out":
                    lc, rc = l - off, r + off
                elif mode == "in":
                    lc, rc = l + off, r - off
                elif mode == "shift":
                    s = -off if k < 0 else off
                    lc, rc = l + s, r + s
                else:  # straight
                    lc, rc = l, r
                for c in (lc, rc):
                    if 0 <= c < w:
                        cells.setdefault((row, c), set()).add(col)
    g = [[0] * w for _ in range(h)]
    for (row, c), s in cells.items():
        if len(s) == 1:
            g[row][c] = next(iter(s))
        elif overlap == "last":
            g[row][c] = max(s)
        else:
            g[row][c] = overlap
    return g


def _differs(g, out):
    return None if g == out else g


def correct(inp, out):
    return _render(inp)


def stride_plus_one(inp, out):
    return _differs(_render(inp, extra=1), out)


def stride_minus_one(inp, out):
    return _differs(_render(inp, extra=-1), out)


def spread_two(inp, out):
    return _differs(_render(inp, spread=2), out)


def only_up(inp, out):
    return _differs(_render(inp, down=False), out)


def only_down(inp, out):
    return _differs(_render(inp, up=False), out)


def converge_inward(inp, out):
    return _differs(_render(inp, mode="in"), out)


def straight_extension(inp, out):
    return _differs(_render(inp, mode="straight"), out)


def slide_diagonally(inp, out):
    return _differs(_render(inp, mode="shift"), out)


def per_row_diagonal(inp, out):
    return _differs(_render(inp, per_row=True), out)


def overlap_last_color_wins(inp, out):
    return _differs(_render(inp, overlap="last"), out)


def overlap_left_as_background(inp, out):
    return _differs(_render(inp, overlap=0), out)


def erase_original_bars(inp, out):
    g = [row[:] for row in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v:
                g[r][c] = 0
    return _differs(g, out)


def trace_only_first_color(inp, out):
    cols = sorted(_bars(inp))
    return _differs(_render(inp, colors={cols[0]}), out)


ALTERNATIVES = [
    ("segment stride one row longer than the bar height", stride_plus_one),
    ("segment stride one row shorter than the bar height", stride_minus_one),
    ("bars widen by two columns per segment instead of one", spread_two),
    ("bars widen by one column per row instead of per segment", per_row_diagonal),
    ("trace goes upward only", only_up),
    ("trace goes downward only", only_down),
    ("bars narrow inward instead of widening", converge_inward),
    ("bars extend straight up and down without widening", straight_extension),
    ("whole bar pair slides sideways along the trace instead of widening", slide_diagonally),
    ("where two colors meet the higher color wins instead of 6", overlap_last_color_wins),
    ("where two colors meet the cell stays background", overlap_left_as_background),
    ("original bars erased, only the traced copies remain", erase_original_bars),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/58e15b12.json").read_text())
    train = task["train"]
    print("correct reproduces out:", [correct(p["input"], p["output"]) == p["output"] for p in train])
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(train), desc)
