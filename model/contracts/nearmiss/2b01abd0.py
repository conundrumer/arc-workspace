import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    axis = None
    for y in range(h):
        if inp[y][0] != bg and all(v == inp[y][0] for v in inp[y]):
            axis = ("h", y, inp[y][0])
    for x in range(w):
        col = [inp[y][x] for y in range(h)]
        if col[0] != bg and all(v == col[0] for v in col):
            axis = ("v", x, col[0])
    kind, pos, lc = axis
    fig = {}
    for y in range(h):
        for x in range(w):
            v = inp[y][x]
            if v != bg and v != lc:
                fig[(y, x)] = v
    cols = sorted(set(fig.values()))
    swap = {cols[0]: cols[1], cols[1]: cols[0]} if len(cols) == 2 else {}
    return h, w, bg, kind, pos, lc, fig, swap


def _mir(kind, pos, y, x, extra=0):
    # reflect across the line; extra shifts the copy away from the line
    if kind == "h":
        ny = 2 * pos - y
        ny += extra if y < pos else -extra
        return ny, x
    nx = 2 * pos - x
    nx += extra if x < pos else -extra
    return y, nx


def _build(inp, orig="swap", copy="keep", remove_orig=False, flip_along=False,
           translate=False, extra=0, drop_line=False, mirror=True):
    h, w, bg, kind, pos, lc, fig, swap = _parse(inp)
    g = [r[:] for r in inp]
    ys = [p[0] for p in fig]
    xs = [p[1] for p in fig]
    y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)

    def recolor(v, mode):
        if mode == "swap":
            return swap.get(v, v)
        return v

    for (y, x), v in fig.items():
        g[y][x] = bg if remove_orig else recolor(v, orig)
    if drop_line:
        for y in range(h):
            for x in range(w):
                if inp[y][x] == lc:
                    g[y][x] = bg
    if mirror:
        for (y, x), v in fig.items():
            if translate:
                # same orientation, only moved to the other side
                if kind == "h":
                    ny, nx = y0 + y1 - y, x
                    ny = 2 * pos - (y0 + y1) + y
                else:
                    ny, nx = y, 2 * pos - (x0 + x1) + x
            else:
                ny, nx = _mir(kind, pos, y, x, extra)
            if flip_along:
                if kind == "h":
                    nx = x0 + x1 - nx
                else:
                    ny = y0 + y1 - ny
            if 0 <= ny < h and 0 <= nx < w:
                g[ny][nx] = recolor(v, copy)
    return g


def no_swap(inp, out):
    return _build(inp, orig="keep", copy="keep")


def swap_both(inp, out):
    return _build(inp, orig="swap", copy="swap")


def swap_copy_only(inp, out):
    return _build(inp, orig="keep", copy="swap")


def translate_copy(inp, out):
    return _build(inp, orig="swap", copy="keep", translate=True)


def off_by_one(inp, out):
    return _build(inp, orig="swap", copy="keep", extra=1)


def moved_not_copied(inp, out):
    return _build(inp, orig="swap", copy="keep", remove_orig=True)


def swap_only(inp, out):
    return _build(inp, orig="swap", mirror=False)


def mirror_only_no_original_swap(inp, out):
    return _build(inp, orig="swap", copy="keep", drop_line=True)


def rotated_copy(inp, out):
    return _build(inp, orig="swap", copy="keep", flip_along=True)


def grid_flip(inp, out):
    h, w, bg, kind, pos, lc, fig, swap = _parse(inp)
    g = _build(inp, orig="swap", copy="keep", mirror=False)
    # reflect the figure over the grid centre instead of the line
    for (y, x), v in fig.items():
        g[y][x] = swap.get(v, v)
    for (y, x), v in fig.items():
        ny, nx = (h - 1 - y, x) if kind == "h" else (y, w - 1 - x)
        if inp[ny][nx] == bg:
            g[ny][nx] = v
    return g


def single_color(inp, out):
    h, w, bg, kind, pos, lc, fig, swap = _parse(inp)
    cnt = Counter(fig.values())
    major = cnt.most_common(1)[0][0]
    g = _build(inp, orig="keep", copy="keep")
    for (y, x) in fig:
        g[y][x] = major
    return g


def copy_swapped_original_untouched_extra_row(inp, out):
    # swap applied to the copy and original, but the true output's copy dropped
    h, w, bg, kind, pos, lc, fig, swap = _parse(inp)
    g = [r[:] for r in out]
    for y in range(h):
        for x in range(w):
            if (y, x) not in fig and inp[y][x] == bg and out[y][x] != bg:
                g[y][x] = bg
    return g


ALTERNATIVES = [
    ("mirror copy, no color swap anywhere", no_swap),
    ("colors swapped on both original and copy", swap_both),
    ("swap applied to the copy, original keeps its colors", swap_copy_only),
    ("copy translated across the line without flipping", translate_copy),
    ("copy placed one cell further from the line", off_by_one),
    ("figure moved across the line, original erased", moved_not_copied),
    ("colors swapped in place, no mirrored copy", swap_only),
    ("copy also flipped along the line direction", rotated_copy),
    ("figure reflected over grid centre instead of the line", grid_flip),
    ("all figure cells recolored to the majority color, mirrored", single_color),
    ("correct figure and copy, but the line erased", mirror_only_no_original_swap),
    ("mirrored copy omitted, original left swapped", copy_swapped_original_untouched_extra_row),
]


def _valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    w = len(g[0])
    for r in g:
        if not isinstance(r, list) or len(r) != w:
            return False
        for v in r:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/2b01abd0.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            n += _valid(g, p["output"])
        print(n, desc)
