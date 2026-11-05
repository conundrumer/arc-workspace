"""Near-miss readings for task 1b8318e3.

Rule: the 2x2 blocks (color 5) stay. Every other non-background cell is a dot.
Each dot slides along a row, column or diagonal and stops beside a block.
The shortest slide wins; a straight (row/column) slide wins a tie over a diagonal one.
A dot with no slide disappears.
"""
import json
from collections import Counter
from pathlib import Path

DIRS4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
DIRS8 = DIRS4 + DIAG


def _setup(inp, out):
    h, w = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    cols = {v for r in inp for v in r if v != bg}
    block = {c for c in cols
             if all(out[i][j] == c for i in range(h) for j in range(w) if inp[i][j] == c)}
    block = max(block, key=lambda c: sum(r.count(c) for r in inp))
    return h, w, bg, block


def _runs(inp, bg, block, pos, diag_side_rule=True, dirs=DIRS8, side_only=False):
    """All (steps, dir, end) slides of the dot at pos."""
    h, w = len(inp), len(inp[0])
    isb = lambda i, j: 0 <= i < h and 0 <= j < w and inp[i][j] == block

    def beside(i, j, dirs_):
        return any(isb(i + a, j + b) for a, b in dirs_)

    res = []
    for d in dirs:
        i, j = pos
        k = 0
        while True:
            i += d[0]; j += d[1]; k += 1
            if not (0 <= i < h and 0 <= j < w):
                break
            if inp[i][j] != bg:
                break
            if d in DIRS4:
                ok = beside(i, j, DIRS4 if side_only else DIRS8)
            elif diag_side_rule:
                ok = isb(i + d[0], j + d[1]) and not beside(i, j, DIRS4)
            else:
                ok = beside(i, j, DIRS8)
            if ok:
                res.append((k, d, (i, j)))
    return res


def _solve(inp, out, pick="short", diag_side_rule=True, dirs=DIRS8, tie_cardinal=True,
           recolor=None, keep_origin=False, back_off=0, overshoot=False, side_only=False):
    h, w, bg, block = _setup(inp, out)
    g = [[block if inp[i][j] == block else bg for j in range(w)] for i in range(h)]
    for i in range(h):
        for j in range(w):
            c = inp[i][j]
            if c in (bg, block):
                continue
            if keep_origin:
                g[i][j] = c
            runs = _runs(inp, bg, block, (i, j), diag_side_rule, dirs, side_only)
            if not runs:
                continue
            if pick == "short":
                m = min(r[0] for r in runs)
            else:
                m = max(r[0] for r in runs)
            best = [r for r in runs if r[0] == m]
            if tie_cardinal and any(r[1] in DIRS4 for r in best):
                best = [r for r in best if r[1] in DIRS4]
            k, d, (a, b) = best[0]
            a -= back_off * d[0]; b -= back_off * d[1]
            if overshoot:
                a += d[0]; b += d[1]
            if 0 <= a < h and 0 <= b < w:
                g[a][b] = c if recolor is None else recolor(c, block)
    return g


def correct(inp, out):
    return _solve(inp, out)


def stay(inp, out):
    return [r[:] for r in inp]


def dots_deleted(inp, out):
    h, w, bg, block = _setup(inp, out)
    return [[block if v == block else bg for v in r] for r in inp]


def straight_only(inp, out):
    return _solve(inp, out, dirs=DIRS4)


def diagonal_only(inp, out):
    return _solve(inp, out, dirs=DIAG)


def longest_slide(inp, out):
    return _solve(inp, out, pick="long")


def vertical_only(inp, out):
    return _solve(inp, out, dirs=[(-1, 0), (1, 0)])


def side_contact_only(inp, out):
    return _solve(inp, out, dirs=DIRS4, side_only=True)


def stop_one_short(inp, out):
    return _solve(inp, out, back_off=1)


def overshoot_into_block(inp, out):
    return _solve(inp, out, overshoot=True)


def copy_not_move(inp, out):
    return _solve(inp, out, keep_origin=True)


def recolor_to_block(inp, out):
    return _solve(inp, out, recolor=lambda c, b: b)


def transposed_result(inp, out):
    return [list(r) for r in zip(*out)]


ALTERNATIVES = [
    ("dots never move; output equals input", stay),
    ("dots are deleted and only the blocks stay", dots_deleted),
    ("dots slide only along rows and columns; diagonal-only dots vanish", straight_only),
    ("dots slide only along diagonals", diagonal_only),
    ("dot takes the longest valid slide instead of the shortest", longest_slide),
    ("dots slide only up or down", vertical_only),
    ("dots stop only at edge contact with a block; corner contact does not count", side_contact_only),
    ("dot stops one cell before the cell beside the block", stop_one_short),
    ("dot slides one cell too far and overwrites a block cell", overshoot_into_block),
    ("dot is copied to its target and also stays at its start", copy_not_move),
    ("moved dots take the block color", recolor_to_block),
    ("correct output transposed (row and column swapped)", transposed_result),
]


def _valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r)
            and g != out)


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/1b8318e3.json").read_text())
    pairs = task["train"]
    c = correct
    for n, p in enumerate(pairs):
        assert c(p["input"], p["output"]) == p["output"], f"model solver wrong on pair {n}"
    print("pairs:", len(pairs))
    for desc, f in ALTERNATIVES:
        cnt = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                cnt += 1
        print(f"{cnt}/{len(pairs)}  {desc}")
