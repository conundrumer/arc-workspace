import json
from pathlib import Path


def _bars(inp):
    """Vertical runs of 2 as dicts: col, top, bot."""
    h, w = len(inp), len(inp[0])
    bars = []
    for c in range(w):
        r = 0
        while r < h:
            if inp[r][c] == 2:
                s = r
                while r + 1 < h and inp[r + 1][c] == 2:
                    r += 1
                bars.append({"col": c, "top": s, "bot": r})
            r += 1
    return bars


def _gen(inp, cap=4, src=True, mirror=True, flip=False, shift=0, whole_row=False,
         mirror_len=False, bar_over=False, mirror_same_row=False):
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    bars = _bars(inp)
    if len(bars) != 2:
        return None
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 8:
                continue
            a = next((b for b in bars if b["top"] <= r <= b["bot"]), None)
            if a is None:
                continue
            o = bars[1] if a is bars[0] else bars[0]
            dxa = 1 if a["col"] < c else -1
            if src:
                x = a["col"] + dxa
                while x != c:
                    g[r][x] = 8
                    x += dxa
            if whole_row:
                for x in range(w):
                    if inp[r][x] == 0:
                        g[r][x] = 8
            g[r][c] = cap
            if not mirror:
                continue
            idx = r - a["top"]
            if flip:
                rb = o["bot"] - idx
            else:
                rb = o["top"] + idx
            rb += shift
            if mirror_same_row:
                rb = r
            if not (0 <= rb < h):
                continue
            dxo = 1 if o["col"] == 0 else -1
            x = o["col"] + dxo
            n = 0
            lim = abs(c - a["col"]) if mirror_len else w
            while 0 <= x < w and inp[rb][x] == 0 and n < lim:
                g[rb][x] = 8
                x += dxo
                n += 1
            if bar_over:
                g[rb][o["col"]] = 8
    return g


def _check(f):
    def wrap(inp, out):
        return f(inp, out)
    return wrap


def no_cap(inp, out):
    return _gen(inp, cap=8)


def cap_bar_color(inp, out):
    return _gen(inp, cap=2)


def no_source_line(inp, out):
    return _gen(inp, src=False)


def no_mirror(inp, out):
    return _gen(inp, mirror=False)


def mirror_from_bottom(inp, out):
    return _gen(inp, flip=True)


def mirror_off_by_one(inp, out):
    return _gen(inp, shift=1)


def mirror_same_abs_row(inp, out):
    return _gen(inp, mirror_same_row=True)


def whole_row_source(inp, out):
    return _gen(inp, whole_row=True)


def mirror_same_length(inp, out):
    return _gen(inp, mirror_len=True)


def mirror_overwrites_bar(inp, out):
    return _gen(inp, bar_over=True)


def source_stops_short(inp, out):
    g = [row[:] for row in out]
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if inp[r][c] == 8:
                g[r][c] = 0
    return g


def input_unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("the 8 cell stays 8 (no 4 end mark)", no_cap),
    ("the end cell takes the bar color 2 instead of 4", cap_bar_color),
    ("only the mirrored line on the other bar is drawn, no line from bar to 8", no_source_line),
    ("only the line from bar to 8 is drawn, no mirrored line on the other bar", no_mirror),
    ("mirrored row counted from the bar bottom instead of the top", mirror_from_bottom),
    ("mirrored row one row below the correct one", mirror_off_by_one),
    ("mirrored line placed at the same absolute row as the 8", mirror_same_abs_row),
    ("line from the 8 spans the whole row on both sides", whole_row_source),
    ("mirrored line has the same length as the source line", mirror_same_length),
    ("mirrored line also overwrites the other bar cell", mirror_overwrites_bar),
    ("the 8 cell is erased to 0 instead of becoming 4", source_stops_short),
    ("output equals input", input_unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/673ef223.json").read_text())
    train = task["train"]
    for p in train:
        assert _gen(p["input"]) == p["output"], "base generator mismatch"
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
