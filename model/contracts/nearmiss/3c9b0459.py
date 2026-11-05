import json
from collections import Counter
from pathlib import Path


def hflip(inp, out):
    return [r[::-1] for r in inp]


def vflip(inp, out):
    return [r[:] for r in inp[::-1]]


def transpose(inp, out):
    return [list(r) for r in zip(*inp)]


def anti_transpose(inp, out):
    return [list(r) for r in zip(*[row[::-1] for row in inp[::-1]])]


def rot_cw(inp, out):
    return [list(r) for r in zip(*inp[::-1])]


def rot_ccw(inp, out):
    return [list(r) for r in zip(*inp)][::-1]


def identity(inp, out):
    return [r[:] for r in inp]


def swap_top_colors(inp, out):
    cnt = Counter(c for r in out for c in r).most_common()
    if len(cnt) < 2:
        return None
    a, b = cnt[0][0], cnt[1][0]
    m = {a: b, b: a}
    return [[m.get(c, c) for c in r] for r in out]


def rotate_top_rows_only(inp, out):
    top = [r[:] for r in inp[:-1]]
    rot = [r[::-1] for r in top[::-1]]
    return rot + [inp[-1][:]]


def last_row_untransformed(inp, out):
    g = [r[:] for r in out]
    g[-1] = inp[-1][:]
    return g


def shift_columns(inp, out):
    return [r[1:] + r[:1] for r in out]


def drop_last_row_col(inp, out):
    return [r[:-1] for r in out[:-1]]


ALTERNATIVES = [
    ("mirror left-right instead of rotating 180 degrees", hflip),
    ("mirror top-bottom instead of rotating 180 degrees", vflip),
    ("transpose across the main diagonal", transpose),
    ("transpose across the anti-diagonal", anti_transpose),
    ("rotate 90 degrees clockwise", rot_cw),
    ("rotate 90 degrees counterclockwise", rot_ccw),
    ("leave the input unchanged", identity),
    ("correct rotation but the two most common colors swapped", swap_top_colors),
    ("rotate only the top rows, leave the last row in place", rotate_top_rows_only),
    ("rotate everything but copy the last row from the input", last_row_untransformed),
    ("correct rotation then cyclic shift of columns by one", shift_columns),
    ("correct rotation but the last row and column dropped (off-by-one size)", drop_last_row_col),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/3c9b0459.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
