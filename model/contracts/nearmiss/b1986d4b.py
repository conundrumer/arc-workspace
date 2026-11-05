"""Near-miss readings for ARC task b1986d4b."""
import json
from collections import Counter
from pathlib import Path


def _components(inp):
    """4-connected same-color components of non-background cells."""
    h, w = len(inp), len(inp[0])
    bg = Counter(c for r in inp for c in r).most_common(1)[0][0]
    seen = set()
    comps = []
    for y in range(h):
        for x in range(w):
            if (y, x) in seen or inp[y][x] == bg:
                continue
            col = inp[y][x]
            stack = [(y, x)]
            seen.add((y, x))
            cells = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and inp[ny][nx] == col:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            comps.append((col, cells))
    return bg, comps


def _squares(inp):
    """Return (bg, noise, [(color, size, count)]) read from the input."""
    bg, comps = _components(inp)
    pieces = Counter(c for c, _ in comps)
    noise = max(pieces, key=lambda c: pieces[c])
    info = {}
    for col, cells in comps:
        if col == noise:
            continue
        ys = [y for y, _ in cells]
        size = max(ys) - min(ys) + 1
        info.setdefault(col, [size, 0])[1] += 1
    return bg, noise, [(c, s, n) for c, (s, n) in info.items()]


def _build(inp, gap_col=1, gap_row=1, trailing=True, corner="tl", axis="h",
           over="small", count_adj=0, full=False, rev=False, sq=None):
    bg, _, found = _squares(inp)
    if sq is None:
        sq = found
    items = [(c, s, n + count_adj) for c, s, n in sq if n + count_adj > 0]
    if not items:
        return None
    if full:
        top = max(n for _, _, n in items)
        items = [(c, s, top) for c, s, _ in items]
    nst = max(n for _, _, n in items)
    stacks = [[(c, s) for c, s, n in items if n > i] for i in range(nst)]
    if rev:
        stacks.reverse()
    maxsize = max(s for _, s, _ in items)
    height = maxsize + gap_row
    widths = [max(s for _, s in st) for st in stacks]
    total = sum(widths) + gap_col * (len(stacks) if trailing else len(stacks) - 1)
    g = [[bg] * total for _ in range(height)]
    x0 = 0
    for st, wd in zip(stacks, widths):
        if over == "small":
            order = sorted(st, key=lambda t: -t[1])
        elif over == "large":
            order = sorted(st, key=lambda t: t[1])
        else:  # lowest color value drawn last
            order = sorted(st, key=lambda t: -t[0])
        for c, s in order:
            for y in range(s):
                for x in range(s):
                    g[y][x0 + x] = c
        x0 += wd + gap_col
    if corner == "bl":
        g = g[::-1]
    elif corner == "tr":
        g = [r[::-1] for r in g]
    elif corner == "br":
        g = [r[::-1] for r in g[::-1]]
    if axis == "v":
        g = [list(r) for r in zip(*g)]
    return g


def true_reading(inp, out):
    return _build(inp)


def corner_bottom_left(inp, out):
    return _build(inp, corner="bl")


def corner_top_right(inp, out):
    return _build(inp, corner="tr")


def stacks_in_column(inp, out):
    return _build(inp, axis="v")


def large_over_small(inp, out):
    return _build(inp, over="large")


def lowest_color_on_top(inp, out):
    return _build(inp, over="color")


def no_gap(inp, out):
    return _build(inp, gap_col=0, gap_row=0)


def gap_two(inp, out):
    return _build(inp, gap_col=2, gap_row=2)


def no_trailing_gap_column(inp, out):
    return _build(inp, trailing=False)


def one_stack_too_few(inp, out):
    return _build(inp, count_adj=-1)


def one_stack_too_many(inp, out):
    return _build(inp, count_adj=1)


def every_stack_full(inp, out):
    return _build(inp, full=True)


def stacks_reversed(inp, out):
    return _build(inp, rev=True)


ALTERNATIVES = [
    ("nest in the bottom-left corner of each slot, gap line on top", corner_bottom_left),
    ("nest in the top-right corner, stacks laid from the right, gap on the left", corner_top_right),
    ("stacks laid down a column instead of along a row", stacks_in_column),
    ("larger square drawn over smaller ones, so only the largest shows", large_over_small),
    ("overlap decided by color value, lowest color drawn on top", lowest_color_on_top),
    ("no background gap between stacks or below them", no_gap),
    ("gap of two lines instead of one", gap_two),
    ("no gap column after the last stack", no_trailing_gap_column),
    ("each size counted one square too few, so one stack fewer", one_stack_too_few),
    ("each size counted one square too many, so one stack more", one_stack_too_many),
    ("every stack holds every size, not only sizes with enough squares", every_stack_full),
    ("stacks laid in reverse order, fewest sizes first", stacks_reversed),
]


def _valid(g, out):
    if g is None or not g or not isinstance(g, list):
        return False
    if any(not isinstance(r, list) or len(r) != len(g[0]) for r in g):
        return False
    if any(not isinstance(v, int) or not 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/b1986d4b.json"))
    pairs = task["train"]
    for p in pairs:
        assert true_reading(p["input"], p["output"]) == p["output"], "builder does not reproduce output"
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
