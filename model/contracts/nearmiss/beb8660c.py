from pathlib import Path
import json


def bars(inp):
    """(row, color, length) for each row holding a bar, top to bottom."""
    res = []
    for r, row in enumerate(inp):
        cells = [c for c in row if c != 0]
        if cells:
            res.append((r, cells[0], len(cells)))
    return res


def build(inp, order, align="right", from_bottom=True, gap=0):
    """Stack bars in `order` (list of (color, length)); first item is placed at the edge."""
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    r = h - 1 if from_bottom else 0
    step = -(1 + gap) if from_bottom else (1 + gap)
    for color, n in order:
        if not 0 <= r < h:
            break
        if align == "right":
            s = w - n
        elif align == "left":
            s = 0
        else:
            s = (w - n) // 2
        for c in range(s, s + n):
            g[r][c] = color
        r += step
    return g


def by_len_desc(inp):
    return [(c, n) for _, c, n in sorted(bars(inp), key=lambda b: -b[2])]


def left_align(inp, out):
    return build(inp, by_len_desc(inp), align="left")


def centered(inp, out):
    return build(inp, by_len_desc(inp), align="center")


def ascending(inp, out):
    return build(inp, list(reversed(by_len_desc(inp))))


def stack_at_top(inp, out):
    return build(inp, by_len_desc(inp), from_bottom=False)


def keep_rows(inp, out):
    # bars right-aligned but left on their original rows (no stacking)
    h, w = len(inp), len(inp[0])
    g = [[0] * w for _ in range(h)]
    for r, c, n in bars(inp):
        for x in range(w - n, w):
            g[r][x] = c
    return g


def keep_order(inp, out):
    # stacked at the bottom, right-aligned, but in original top-to-bottom order
    return build(inp, [(c, n) for _, c, n in reversed(bars(inp))])


def by_color(inp, out):
    order = [(c, n) for _, c, n in sorted(bars(inp), key=lambda b: -b[1])]
    return build(inp, order)


def color_shift(inp, out):
    # lengths in the right order, colors taken from the neighbouring (next longer) bar
    o = by_len_desc(inp)
    cols = [c for c, _ in o]
    cols = cols[1:] + cols[:1]
    return build(inp, [(cols[i], o[i][1]) for i in range(len(o))])


def base_on_top(inp, out):
    o = by_len_desc(inp)
    base = [b for b in o if b[0] == 8]
    rest = [b for b in o if b[0] != 8]
    return build(inp, rest + base)


def short_by_one(inp, out):
    o = [(c, max(1, n - 1)) if c != 8 else (c, n) for c, n in by_len_desc(inp)]
    return build(inp, o)


def base_dropped(inp, out):
    return build(inp, [b for b in by_len_desc(inp) if b[0] != 8])


def transposed(inp, out):
    # bars stand vertically against the right edge, left-to-right order by length
    h, w = len(inp), len(inp[0])
    g = build(inp, by_len_desc(inp))
    return [list(r) for r in zip(*g)]


def gap_rows(inp, out):
    return build(inp, by_len_desc(inp), gap=1)


ALTERNATIVES = [
    ("bars aligned to the left edge instead of the right", left_align),
    ("bars centered horizontally", centered),
    ("longest bar on top, shortest at the bottom (ascending order)", ascending),
    ("stack pressed against the top edge instead of the bottom", stack_at_top),
    ("bars right-aligned but left on their original rows, not stacked", keep_rows),
    ("bars stacked and right-aligned in original input order, not sorted by length", keep_order),
    ("bars sorted by color value instead of length", by_color),
    ("colors shifted by one rank: each length painted with the next longer bar's color", color_shift),
    ("base bar of color 8 placed on top of the stack", base_on_top),
    ("every non-base bar one cell too short", short_by_one),
    ("base bar of color 8 omitted from the output", base_dropped),
    ("stack drawn transposed, with vertical bars", transposed),
    ("one empty row left between consecutive bars", gap_rows),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/beb8660c.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                g = None
                print("  error", e)
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
