import json
from pathlib import Path


def _parse(inp):
    h = len(inp)
    s = next(i for i, r in enumerate(inp) if all(v == 2 for v in r))
    top = [j for j, v in enumerate(inp[0]) if v != 0]
    bot = [j for j, v in enumerate(inp[h - 1]) if v != 0]
    top_longer = len(top) > len(bot)
    up = list(range(1, s))
    down = list(range(s + 1, h - 1))
    return dict(h=h, w=len(inp[0]), s=s, top=top, bot=bot, top_longer=top_longer,
                up=up, down=down, long_rows=up if top_longer else down,
                short_rows=down if top_longer else up,
                long_cols=top if top_longer else bot,
                short_cols=bot if top_longer else top,
                inter=[j for j in top if j in bot],
                color=inp[0][top[0]] if top_longer else inp[h - 1][bot[0]])


def _paint(inp, rows, cols, color=4):
    g = [r[:] for r in inp]
    for i in rows:
        for j in cols:
            g[i][j] = color
    return g


def unchanged(inp, out):
    return [r[:] for r in inp]


def wrong_side(inp, out):
    p = _parse(inp)
    return _paint(inp, p["short_rows"], p["inter"])


def longer_bar_cols(inp, out):
    p = _parse(inp)
    return _paint(inp, p["long_rows"], p["long_cols"])


def one_col_wider(inp, out):
    p = _parse(inp)
    cols = list(p["inter"])
    if cols[0] > 0:
        cols.append(cols[0] - 1)
    else:
        cols.append(cols[-1] + 1)
    return _paint(inp, p["long_rows"], cols)


def both_halves(inp, out):
    p = _parse(inp)
    return _paint(inp, p["up"] + p["down"], p["inter"])


def through_separator(inp, out):
    p = _parse(inp)
    rows = p["long_rows"] + [p["s"]]
    return _paint(inp, rows, p["inter"])


def skip_adjacent_row(inp, out):
    p = _parse(inp)
    rows = p["long_rows"][1:] if p["top_longer"] else p["long_rows"][:-1]
    return _paint(inp, rows, p["inter"])


def bar_color_fill(inp, out):
    p = _parse(inp)
    return _paint(inp, p["long_rows"], p["inter"], p["color"])


def full_width(inp, out):
    p = _parse(inp)
    return _paint(inp, p["long_rows"], range(p["w"]))


def first_col_only(inp, out):
    p = _parse(inp)
    return _paint(inp, p["long_rows"], p["inter"][:1])


def half_height(inp, out):
    p = _parse(inp)
    n = len(p["long_rows"]) // 2
    rows = p["long_rows"][:n] if p["top_longer"] else p["long_rows"][-n:]
    return _paint(inp, rows, p["inter"])


def non_overlap_cols(inp, out):
    p = _parse(inp)
    cols = [j for j in p["long_cols"] if j not in p["inter"]]
    return _paint(inp, p["long_rows"], cols)


ALTERNATIVES = [
    ("Output equals input; no fill", unchanged),
    ("Fill the overlap columns in the shorter bar's half instead of the longer bar's half", wrong_side),
    ("Fill all columns of the longer bar, not only the overlap with the other bar", longer_bar_cols),
    ("Fill is one column wider than the overlap of the two bars", one_col_wider),
    ("Fill the overlap columns in both halves", both_halves),
    ("Fill runs through the separator row, overwriting it", through_separator),
    ("Fill leaves out the row next to the longer bar", skip_adjacent_row),
    ("Fill uses the bar color instead of the new color 4", bar_color_fill),
    ("Fill spans the full grid width in the longer bar's half", full_width),
    ("Fill only the first overlap column", first_col_only),
    ("Fill covers only half the rows between the bar and the separator", half_height),
    ("Fill the longer bar's columns that do not overlap the other bar", non_overlap_cols),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/770cc55f.json"))
    pairs = task["train"]
    for p in pairs:
        pr = _parse(p["input"])
        assert _paint(p["input"], pr["long_rows"], pr["inter"]) == p["output"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
