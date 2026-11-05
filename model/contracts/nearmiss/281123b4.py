import json
from pathlib import Path

TRUE_PRIO = [9, 4, 8, 5]


def panels(inp, n=4, gap=1):
    h = len(inp)
    w = (len(inp[0]) - gap * (n - 1)) // n
    return [[row[i * (w + gap):i * (w + gap) + w] for row in inp] for i in range(n)]


def overlay(ps, prio):
    h, w = len(ps[0]), len(ps[0][0])
    res = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            cols = [p[r][c] for p in ps if p[r][c] != 0]
            if cols:
                res[r][c] = min(cols, key=lambda v: prio.index(v) if v in prio else 99)
    return res


def ink_color(p):
    return next(v for row in p for v in row if v)


def reverse_prio(inp, out):
    return overlay(panels(inp), TRUE_PRIO[::-1])


def leftmost_wins(inp, out):
    ps = panels(inp)
    return overlay(ps, [ink_color(p) for p in ps])


def rightmost_wins(inp, out):
    ps = panels(inp)
    return overlay(ps, [ink_color(p) for p in ps][::-1])


def eight_over_nine(inp, out):
    return overlay(panels(inp), [8, 9, 4, 5])


def eight_over_four(inp, out):
    return overlay(panels(inp), [9, 8, 4, 5])


def drop_last_panel(inp, out):
    return overlay(panels(inp)[:3], TRUE_PRIO)


def mirrored(inp, out):
    return [row[::-1] for row in out]


def single_ink_only(inp, out):
    ps = panels(inp)
    h, w = len(ps[0]), len(ps[0][0])
    res = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            cols = [p[r][c] for p in ps if p[r][c] != 0]
            if len(cols) == 1:
                res[r][c] = cols[0]
    return res


def majority_color(inp, out):
    ps = panels(inp)
    h, w = len(ps[0]), len(ps[0][0])
    res = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            cols = [p[r][c] for p in ps if p[r][c] != 0]
            if cols:
                res[r][c] = max(cols, key=lambda v: (cols.count(v), TRUE_PRIO.index(v)))
    return res


def fewest_ink_wins(inp, out):
    ps = panels(inp)
    cnt = {ink_color(p): sum(1 for row in p for v in row if v) for p in ps}
    return overlay(ps, sorted(cnt, key=lambda k: cnt[k]))


def most_ink_wins(inp, out):
    ps = panels(inp)
    cnt = {ink_color(p): sum(1 for row in p for v in row if v) for p in ps}
    return overlay(ps, sorted(cnt, key=lambda k: -cnt[k]))


def first_panel_only(inp, out):
    return panels(inp)[0]


ALTERNATIVES = [
    ("priority order reversed (5 beats 8 beats 4 beats 9)", reverse_prio),
    ("leftmost panel wins at every cell", leftmost_wins),
    ("rightmost panel wins at every cell", rightmost_wins),
    ("8 ranked above 9, rest of the order right", eight_over_nine),
    ("8 ranked above 4, rest of the order right", eight_over_four),
    ("last panel missed: only three panels overlaid", drop_last_panel),
    ("output mirrored left to right", mirrored),
    ("only cells with ink in exactly one panel kept, conflicts left empty", single_ink_only),
    ("most common ink color wins, ties go to the lowest-ranked color", majority_color),
    ("panel with fewest ink cells wins", fewest_ink_wins),
    ("panel with most ink cells wins", most_ink_wins),
    ("output is the first panel alone", first_panel_only),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/281123b4.json'))
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))
            if ok and g != p["output"]:
                n += 1
        print(n, desc)
