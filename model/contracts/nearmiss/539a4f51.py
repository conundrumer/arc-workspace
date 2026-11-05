import json
from pathlib import Path


def shown(inp):
    """Colors of the shown shells: the diagonal up to the background."""
    cols = []
    for k in range(min(len(inp), len(inp[0]))):
        if inp[k][k] == 0:
            break
        cols.append(inp[k][k])
    return cols


def build(inp, size, color_of_shell, shape=None):
    cols = shown(inp)
    n = len(cols)
    g = []
    for r in range(size):
        row = []
        for c in range(size):
            k = max(r, c) if shape is None else shape(r, c, size)
            row.append(color_of_shell(cols, n, k))
        g.append(row)
    return g


def clamp(inp, out):
    return build(inp, len(out), lambda cols, n, k: cols[min(k, n - 1)])


def pingpong(inp, out):
    def f(cols, n, k):
        p = 2 * (n - 1)
        if p == 0:
            return cols[0]
        m = k % p
        return cols[m if m < n else p - m]
    return build(inp, len(out), f)


def crop_same_size(inp, out):
    h, w = len(inp), len(inp[0])
    return [row[:w] for row in out[:h]]


def with_background(inp, out):
    cols = [inp[k][k] for k in range(len(inp))]
    return build(inp, len(out), lambda _c, n, k: cols[k % len(cols)])


def flip_both(inp, out):
    return [row[::-1] for row in out[::-1]]


def shift_one(inp, out):
    return build(inp, len(out), lambda cols, n, k: cols[(k + 1) % n])


def scale_three(inp, out):
    return build(inp, 3 * len(inp), lambda cols, n, k: cols[k % n])


def reversed_cycle(inp, out):
    return build(inp, len(out), lambda cols, n, k: cols[(-k) % n])


def tile_input(inp, out):
    h, w = len(inp), len(inp[0])
    return [[inp[r % h][c % w] for c in range(2 * w)] for r in range(2 * h)]


def dedupe_runs(inp, out):
    cols = shown(inp)
    d = [c for i, c in enumerate(cols) if i == 0 or c != cols[i - 1]]
    m = len(d)
    return build(inp, len(out), lambda _c, n, k: d[k % m])


def stripes_by_row(inp, out):
    return build(inp, len(out), lambda cols, n, k: cols[k % n],
                 shape=lambda r, c, s: r)


def no_wrap_last_shell_rest_bg(inp, out):
    return build(inp, len(out), lambda cols, n, k: cols[k] if k < n else 0)


ALTERNATIVES = [
    ("shell colors do not repeat; shells past the shown ones take the last color", clamp),
    ("shell colors bounce back and forth instead of cycling", pingpong),
    ("output keeps the input size (top-left crop of the true output)", crop_same_size),
    ("background color counts as one more shell in the cycle", with_background),
    ("output shells are centered on the opposite corner", flip_both),
    ("cycle starts one shell late", shift_one),
    ("output is scaled by 3 instead of 2", scale_three),
    ("cycle runs in reverse order", reversed_cycle),
    ("input is tiled 2 by 2, background cells included", tile_input),
    ("equal neighbouring shell colors are merged before cycling", dedupe_runs),
    ("color depends on the row index only, giving horizontal bands", stripes_by_row),
    ("shells beyond the shown ones are filled with background", no_wrap_last_shell_rest_bg),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/539a4f51.json").read_text())
    train = task["train"]
    print("pairs", len(train))
    for desc, fn in ALTERNATIVES:
        cnt = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                cnt += 1
        print(cnt, desc)
