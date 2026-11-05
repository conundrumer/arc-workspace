import json
from pathlib import Path


def pieces(g):
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == 0 or (r, c) in seen:
                continue
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != 0 and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            res.append(sorted(cells))
    return res


def split(g):
    h, w = len(g), len(g[0])
    bars, marks = [], []
    for p in pieces(g):
        edge = any(y in (0, h - 1) or x in (0, w - 1) for y, x in p)
        if len(p) > 1 and edge:
            bars.append(p)
        elif len(p) == 1:
            marks.append(p[0])
        else:
            marks.append(p[0])
    return bars, marks


def bar_colors(g, bar):
    return [g[y][x] for y, x in bar]


def copy(g):
    return [row[:] for row in g]


def stamp(g, bar, row, col0, vertical=False, wrap=False, only_bg=False, flip=False):
    """Draw the bar's colors starting at (row, col0); clip or wrap at edges."""
    h, w = len(g), len(g[0])
    cols = bar_colors(g, bar)
    if flip:
        cols = cols[::-1]
    for i, v in enumerate(cols):
        y, x = (row + i, col0) if vertical else (row, col0 + i)
        if wrap:
            y %= h
            x %= w
        if 0 <= y < h and 0 <= x < w:
            if only_bg and g[y][x] != 0:
                continue
            g[y][x] = v


def run(inp, anchor="color", bar_filter=None, mark_filter=None, off=0, **kw):
    bars, marks = split(inp)
    if bar_filter:
        bars = [b for b in bars if bar_filter(b, inp)]
    res = copy(inp)
    for (my, mx) in marks:
        if mark_filter and not mark_filter(my, mx, inp):
            continue
        col = inp[my][mx]
        for b in bars:
            cs = bar_colors(inp, b)
            if anchor == "color":
                if col not in cs:
                    continue
                idx = cs.index(col)
            elif anchor == "left":
                idx = 0
            elif anchor == "right":
                idx = len(cs) - 1
            elif anchor == "color_last":
                if col not in cs:
                    continue
                idx = len(cs) - 1 - cs[::-1].index(col)
            else:
                raise ValueError(anchor)
            if kw.get("vertical"):
                stamp(res, b, my - idx + off, mx, **kw)
            else:
                stamp(res, b, my, mx - idx + off, **kw)
            if anchor == "color":
                break
    return res


def bottom_row(b, g):
    return all(y == len(g) - 1 for y, x in b)


def first_mark_only(inp, out):
    bars, marks = split(inp)
    first = min(marks)
    return run(inp, mark_filter=lambda y, x, g: (y, x) == first)


def bar_start_color(inp, out):
    bars, marks = split(inp)
    res = copy(inp)
    for b in bars:
        cs = bar_colors(inp, b)
        for (my, mx) in marks:
            if inp[my][mx] == cs[0]:
                stamp(res, b, my, mx)
    return res


def erase_bars(inp, out):
    bars, _ = split(inp)
    res = copy(out)
    for b in bars:
        for y, x in b:
            res[y][x] = 0
    return res


def keep_unstamped_marks(inp, out):
    # marks not stamped over: the true output with the marks' neighbours
    # kept as input; here, drop the last mark's stamp
    bars, marks = split(inp)
    last = max(marks)
    return run(inp, mark_filter=lambda y, x, g: (y, x) != last)


def same_row_bar_only(inp, out):
    # mark takes the bar's row offset instead of its own row: stamp on the bar row
    bars, marks = split(inp)
    res = copy(inp)
    for (my, mx) in marks:
        col = inp[my][mx]
        for b in bars:
            cs = bar_colors(inp, b)
            if col in cs:
                stamp(res, b, b[0][0] - 1 if b[0][0] > 0 else 1, mx - cs.index(col))
                break
    return res


def wrap_alt(inp, out):
    return run(inp, wrap=True)


def ALT(f):
    def g(inp, out):
        return f(inp, out)
    return g


ALTERNATIVES = [
    ("bar is stamped with its left end at the mark, ignoring color match",
     lambda inp, out: run(inp, anchor="left")),
    ("bar is stamped with its right end at the mark, ignoring color match",
     lambda inp, out: run(inp, anchor="right")),
    ("stamp is one column right of the color-aligned position",
     lambda inp, out: run(inp, off=1)),
    ("bar is stamped as a vertical column down from the aligned mark",
     lambda inp, out: run(inp, vertical=True)),
    ("bar is stamped mirrored, aligned on the mark's color",
     lambda inp, out: run(inp, flip=True)),
    ("only the first mark in reading order is stamped",
     first_mark_only),
    ("last mark in reading order is left unstamped",
     keep_unstamped_marks),
    ("only a bar on the bottom row counts as a bar",
     lambda inp, out: run(inp, bar_filter=bottom_row)),
    ("each bar is stamped only at the mark matching its first color",
     bar_start_color),
    ("stamps that run past the grid edge wrap around instead of clipping",
     wrap_alt),
    ("the original bars are erased after the copies are drawn",
     erase_bars),
    ("stamp is drawn one row above the mark's row",
     lambda inp, out: run(inp) if False else _row_shift(inp, -1)),
]


def _row_shift(inp, dy):
    bars, marks = split(inp)
    res = copy(inp)
    for (my, mx) in marks:
        col = inp[my][mx]
        for b in bars:
            cs = bar_colors(inp, b)
            if col in cs:
                y = my + dy
                if 0 <= y < len(inp):
                    stamp(res, b, y, mx - cs.index(col))
                break
    return res


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/5af49b42.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
