import json
from collections import Counter
from pathlib import Path

MARK = 5


def _counts(inp):
    return Counter(c for r in inp for c in r)


def _ranked(inp):
    cnt = _counts(inp)
    return sorted(cnt, key=lambda c: (-cnt[c], c))


def _remap(inp, f):
    return [[f(c) for c in r] for r in inp]


def mark_zero(inp, out):
    return [[0 if c == MARK else c for c in r] for r in out]


def mark_eight(inp, out):
    return [[8 if c == MARK else c for c in r] for r in out]


def keep_least_common(inp, out):
    cnt = _counts(inp)
    k = min(cnt, key=lambda c: (cnt[c], c))
    return _remap(inp, lambda c: c if c == k else MARK)


def keep_second_common(inp, out):
    rk = _ranked(inp)
    if len(rk) < 2:
        return None
    k = rk[1]
    return _remap(inp, lambda c: c if c == k else MARK)


def keep_top_two(inp, out):
    rk = _ranked(inp)[:2]
    return _remap(inp, lambda c: c if c in rk else MARK)


def inverted(inp, out):
    k = _ranked(inp)[0]
    return _remap(inp, lambda c: MARK if c == k else c)


def recolor_only_second(inp, out):
    rk = _ranked(inp)
    if len(rk) < 2:
        return None
    s = rk[1]
    return _remap(inp, lambda c: MARK if c == s else c)


def keep_corner_color(inp, out):
    k = inp[-1][-1]
    return _remap(inp, lambda c: c if c == k else MARK)


def rotate_output(inp, out):
    return [list(r) for r in zip(*out[::-1])]


def drop_last_row(inp, out):
    return [list(r) for r in out[:-1]]


def mark_only_touching_kept(inp, out):
    k = _ranked(inp)[0]
    h, w = len(inp), len(inp[0])
    res = []
    for i in range(h):
        row = []
        for j in range(w):
            c = inp[i][j]
            if c == k:
                row.append(c)
                continue
            touch = any(
                0 <= i + di < h and 0 <= j + dj < w and inp[i + di][j + dj] == k
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
            row.append(MARK if touch else c)
        res.append(row)
    return res


def unchanged(inp, out):
    return [list(r) for r in inp]


ALTERNATIVES = [
    ("mark non-kept cells with 0 instead of 5", mark_zero),
    ("mark non-kept cells with 8 instead of 5", mark_eight),
    ("keep the least common color instead of the most common", keep_least_common),
    ("keep the second most common color", keep_second_common),
    ("keep the two most common colors", keep_top_two),
    ("inverted: mark the commonest color, keep the others", inverted),
    ("mark only the second most common color, leave other colors", recolor_only_second),
    ("keep the color of the bottom-right cell", keep_corner_color),
    ("output rotated a quarter turn", rotate_output),
    ("output missing its last row", drop_last_row),
    ("mark only non-kept cells that touch a kept cell edge-wise", mark_only_touching_kept),
    ("input returned unchanged", unchanged),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(type(c) is int and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/9565186b.json"))
    pairs = task["train"]
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
