import json
from pathlib import Path


def _copy(g):
    return [list(r) for r in g]


def _outside(i, j, n):
    return not (i < n and j < n)


def tiled_input(inp, out):
    n = len(inp)
    N = len(out)
    return [[inp[i % n][j % n] for j in range(N)] for i in range(N)]


def anchored_bottom_right(inp, out):
    return [list(reversed(r)) for r in reversed(out)]


def anchored_top_right(inp, out):
    return [list(reversed(r)) for r in out]


def diag_period_n(inp, out):
    n = len(inp)
    g = _copy(out)
    for i in range(n, len(g)):
        g[i][i] = inp[i % n][i % n]
    return g


def diag_bounce(inp, out):
    n = len(inp)
    g = _copy(out)
    p = 2 * (n - 1)
    for i in range(n, len(g)):
        k = i % p
        k = k if k < n else p - k
        g[i][i] = inp[k][k]
    return g


def diag_not_continued(inp, out):
    n = len(inp)
    g = _copy(out)
    for i in range(n, len(g)):
        g[i][i] = g[i][i - 1]
    return g


def no_arms(inp, out):
    n = len(inp)
    bg = inp[0][0]
    g = _copy(out)
    for i in range(len(g)):
        for j in range(len(g[0])):
            if _outside(i, j, n) and i != j:
                g[i][j] = bg
    return g


def one_arm_only(inp, out):
    n = len(inp)
    bg = inp[0][0]
    g = _copy(out)
    for i in range(len(g)):
        for j in range(len(g[0])):
            if _outside(i, j, n) and i > j:
                g[i][j] = bg
    return g


def cropped_one_short(inp, out):
    return [r[:-1] for r in out[:-1]]


def padded_one_extra(inp, out):
    g = [r + [r[-1]] for r in out]
    g.append(list(g[-1]))
    return g


def swap_corner_center_colors(inp, out):
    a = inp[0][0]
    b = inp[len(inp) // 2][len(inp) // 2]
    if a == b:
        return None
    m = {a: b, b: a}
    return [[m.get(v, v) for v in r] for r in out]


def input_only_with_blank(inp, out):
    n = len(inp)
    bg = inp[0][0]
    return [[inp[i][j] if i < n and j < n else bg for j in range(len(out[0]))]
            for i in range(len(out))]


ALTERNATIVES = [
    ("the input is tiled periodically over the whole canvas", tiled_input),
    ("the input sits at the bottom-right corner, pattern rotated half a turn", anchored_bottom_right),
    ("the input sits at the top-right corner, pattern mirrored left-right", anchored_top_right),
    ("the diagonal repeats with the input's full period instead of its true period", diag_period_n),
    ("the diagonal bounces back and forth along the input's diagonal", diag_bounce),
    ("the diagonal is not continued beyond the input; cells copy their left neighbor", diag_not_continued),
    ("only the diagonal grows outside the input; the arms are missing", no_arms),
    ("only the arms on the upper-right side of the diagonal are painted", one_arm_only),
    ("the canvas is one row and one column smaller", cropped_one_short),
    ("the canvas is one row and one column larger", padded_one_extra),
    ("the corner color and the center color are swapped", swap_corner_center_colors),
    ("only the input is placed; the rest is its corner color", input_only_with_blank),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/3979b1a8.json"))
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(f"{ok}/{len(pairs)}  {fn.__name__}: {desc}")
