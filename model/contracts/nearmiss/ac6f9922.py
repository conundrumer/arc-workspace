import json
from collections import Counter
from pathlib import Path


def _analyse(inp):
    h, w = len(inp), len(inp[0])
    bg = inp[0][0]
    cnt = Counter(v for row in inp for v in row if v != bg)
    bar = cnt.most_common(1)[0][0]
    seen = set()
    wins = []
    for r in range(h):
        for c in range(w):
            if (r, c) in seen or inp[r][c] == bar:
                continue
            comp, stack, edge = [], [(r, c)], False
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                if y in (0, h - 1) or x in (0, w - 1):
                    edge = True
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] != bar:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            if edge:
                continue
            top = min(y for y, _ in comp)
            left = min(x for _, x in comp)
            marks = [(y, x) for y, x in comp if inp[y][x] != bg]
            color = inp[marks[0][0]][marks[0][1]] if marks else bg
            wins.append({"top": top, "left": left, "color": color, "size": len(marks)})
    tops = sorted({d["top"] for d in wins})
    lefts = sorted({d["left"] for d in wins})
    for d in wins:
        d["ri"] = tops.index(d["top"])
        d["ci"] = lefts.index(d["left"])
    return bg, bar, wins, len(tops), len(lefts)


def _grid(inp, fn, default):
    bg, bar, wins, nr, nc = _analyse(inp)
    g = [[default] * nc for _ in range(nr)]
    for d in wins:
        g[d["ri"]][d["ci"]] = fn(d, bg, bar)
    return g


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def hflip(inp, out):
    return [r[::-1] for r in out]


def vflip(inp, out):
    return out[::-1]


def empty_is_bar(inp, out):
    bg, bar, wins, nr, nc = _analyse(inp)
    g = [r[:] for r in out]
    for d in wins:
        if d["color"] == bg:
            g[d["ri"]][d["ci"]] = bar
    return g


def one_mark_color(inp, out):
    bg, bar, wins, nr, nc = _analyse(inp)
    first = next((d["color"] for d in sorted(wins, key=lambda d: (d["ri"], d["ci"])) if d["color"] != bg), None)
    g = [r[:] for r in out]
    for d in wins:
        if d["color"] != bg:
            g[d["ri"]][d["ci"]] = first
    return g


def crop_bar_box(inp, out):
    bg, bar, wins, nr, nc = _analyse(inp)
    ys = [y for y, row in enumerate(inp) for v in row if v == bar]
    xs = [x for row in inp for x, v in enumerate(row) if v == bar]
    return [row[min(xs):max(xs) + 1] for row in inp[min(ys):max(ys) + 1]]


def single_row(inp, out):
    bg, bar, wins, nr, nc = _analyse(inp)
    order = sorted(wins, key=lambda d: (d["ri"], d["ci"]))
    return [[d["color"] for d in order]]


def padded_border(inp, out):
    bg = _analyse(inp)[0]
    w = len(out[0])
    return [[bg] * (w + 2)] + [[bg] + r + [bg] for r in out] + [[bg] * (w + 2)]


def largest_mark_only(inp, out):
    bg, bar, wins, nr, nc = _analyse(inp)
    best = max(wins, key=lambda d: d["size"])
    return _grid(inp, lambda d, bg, bar: d["color"] if d is best else bg, bg)


def mark_as_bar_color(inp, out):
    return _grid(inp, lambda d, bg, bar: bar if d["color"] != bg else bg, 0)


def shift_columns(inp, out):
    return [r[-1:] + r[:-1] for r in out]


def drop_last_row(inp, out):
    return out[:-1]


ALTERNATIVES = [
    ("output transposed: rows and columns of windows swapped", transpose),
    ("output mirrored left to right", hflip),
    ("output flipped top to bottom", vflip),
    ("empty windows take the bar color instead of the background", empty_is_bar),
    ("every marked window takes the color of the first mark", one_mark_color),
    ("no downsampling: input cropped to the bounding box of the bars", crop_bar_box),
    ("windows listed in reading order as one row", single_row),
    ("output wrapped in a one-cell background border", padded_border),
    ("only the largest mark is kept, other windows are background", largest_mark_only),
    ("a marked window shows presence only: it takes the bar color", mark_as_bar_color),
    ("window colors shifted one column right with wraparound", shift_columns),
    ("last row of windows dropped", drop_last_row),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/ac6f9922.json").read_text())
    train = task["train"]
    print("pairs", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
