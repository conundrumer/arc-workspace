import json
from collections import Counter
from pathlib import Path


def _counts(inp):
    return Counter(c for r in inp for c in r if c != 0)


def _most_frequent(inp, out):
    cnt = _counts(inp)
    return [[cnt.most_common(1)[0][0]]]


def _least_frequent(inp, out):
    cnt = _counts(inp)
    return [[min(cnt, key=lambda c: (cnt[c], c))]]


def _first_nonzero(inp, out):
    for r in inp:
        for c in r:
            if c:
                return [[c]]
    return None


def _crossed_color(inp, out):
    # most common non-zero color other than the uncrossed line's color
    cnt = _counts(inp)
    del cnt[out[0][0]]
    if not cnt:
        return None
    return [[cnt.most_common(1)[0][0]]]


def _num_colors(inp, out):
    return [[len(_counts(inp))]]


def _background(inp, out):
    return [[0]]


def _line_strip(inp, out):
    # output the whole uncrossed line as a strip instead of one cell
    h, w = len(inp), len(inp[0])
    col = out[0][0]
    for i in range(h):
        if all(c == col for c in inp[i]):
            return [[col] * w]
    for j in range(w):
        if all(inp[i][j] == col for i in range(h)):
            return [[col] for _ in range(h)]
    return None


def _filled_input(inp, out):
    return [[out[0][0]] * len(inp[0]) for _ in inp]


def _two_by_two(inp, out):
    c = out[0][0]
    return [[c, c], [c, c]]


def _last_nonzero_col_major(inp, out):
    last = None
    for j in range(len(inp[0])):
        for i in range(len(inp)):
            if inp[i][j]:
                last = inp[i][j]
    return [[last]] if last is not None else None


def _crossed_line_strip(inp, out):
    # keep the input unchanged except the uncrossed line is dropped (zeroed)
    h, w = len(inp), len(inp[0])
    col = out[0][0]
    g = [r[:] for r in inp]
    for i in range(h):
        if all(c == col for c in inp[i]):
            g[i] = [0] * w
            return g
    for j in range(w):
        if all(inp[i][j] == col for i in range(h)):
            for i in range(h):
                g[i][j] = 0
            return g
    return None


ALTERNATIVES = [
    ("most frequent non-zero color", _most_frequent),
    ("least frequent non-zero color", _least_frequent),
    ("first non-zero cell in reading order", _first_nonzero),
    ("color of the crossed (interrupted) lines instead of the uncrossed line", _crossed_color),
    ("count of distinct non-zero colors as the cell value", _num_colors),
    ("background color 0 as the single cell", _background),
    ("whole uncrossed line copied as a strip instead of one cell", _line_strip),
    ("input-sized grid filled with the uncrossed line color", _filled_input),
    ("2x2 block of the right color (off-by-one size)", _two_by_two),
    ("last non-zero cell in column-major order", _last_nonzero_col_major),
    ("input with the uncrossed line erased", _crossed_line_strip),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1a2e2828.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
