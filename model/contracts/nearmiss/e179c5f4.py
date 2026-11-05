import json
from pathlib import Path


def _dims(g):
    return len(g), len(g[0])


def _blank(h, w, v):
    return [[v] * w for _ in range(h)]


def _colors(inp, out):
    ball = next(c for r in inp for c in r if c != 0)
    fill = next(c for r in out for c in r if c != ball)
    return ball, fill


def _bounce(i, w):
    """Column after i steps from column 0, reflecting off both walls."""
    if w == 1:
        return 0
    p = 2 * (w - 1)
    k = i % p
    return k if k < w else p - k


def _paint(inp, out, colfn, ball=None, fill=None, bottom_up=True):
    h, w = _dims(inp)
    b, f = _colors(inp, out)
    b = b if ball is None else ball
    f = f if fill is None else fill
    g = _blank(h, w, f)
    for i in range(h):
        r = h - 1 - i if bottom_up else i
        c = colfn(i, w)
        if c is not None and 0 <= c < w:
            g[r][c] = b
    return g


def no_fill(inp, out):
    b, f = _colors(inp, out)
    return [[0 if c == f else c for c in r] for r in out]


def no_bounce_stop(inp, out):
    return _paint(inp, out, lambda i, w: i if i < w else None)


def wrap_around(inp, out):
    return _paint(inp, out, lambda i, w: i % w)


def flip_vertical(inp, out):
    return out[::-1]


def start_right(inp, out):
    return [r[::-1] for r in out]


def horizontal_travel(inp, out):
    h, w = _dims(inp)
    b, f = _colors(inp, out)
    g = _blank(h, w, f)
    for i in range(w):
        r = h - 1 - _bounce(i, h)
        g[r][i] = b
    return g


def pause_at_wall(inp, out):
    def col(i, w):
        if w == 1:
            return 0
        p = 2 * w
        k = i % p
        return k if k < w else p - 1 - k
    return _paint(inp, out, col)


def swap_colors(inp, out):
    b, f = _colors(inp, out)
    return [[f if c == b else b for c in r] for r in out]


def start_cell_blank(inp, out):
    h, w = _dims(inp)
    b, f = _colors(inp, out)
    g = [r[:] for r in out]
    g[h - 1][0] = f
    return g


def top_half_blank(inp, out):
    h, w = _dims(inp)
    b, f = _colors(inp, out)
    g = [r[:] for r in out]
    for r in range(h // 2):
        g[r] = [f] * w
    return g


def double_step(inp, out):
    return _paint(inp, out, lambda i, w: _bounce(2 * i, w))


ALTERNATIVES = [
    ("background cells stay 0 instead of becoming the fill color", no_fill),
    ("ball stops at the first wall instead of reflecting", no_bounce_stop),
    ("ball wraps around to the opposite wall instead of reflecting", wrap_around),
    ("ball travels from the top down instead of bottom up", flip_vertical),
    ("ball starts from the bottom-right corner instead of bottom-left", start_right),
    ("ball travels along the short axis, reflecting off top and bottom", horizontal_travel),
    ("ball rests one step on the wall before reflecting", pause_at_wall),
    ("ball and fill colors swapped", swap_colors),
    ("launch cell is treated as background", start_cell_blank),
    ("ball path is dropped in the top half of the grid", top_half_blank),
    ("ball moves two columns per row", double_step),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not isinstance(g[0], list):
        return False
    w = len(g[0])
    if w == 0 or any(not isinstance(r, list) or len(r) != w for r in g):
        return False
    if any(type(c) is not int or not 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/e179c5f4.json"))
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
