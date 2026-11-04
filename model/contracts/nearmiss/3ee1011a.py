from pathlib import Path
import json
from collections import Counter


def bars(inp):
    """[(color, size, first_pos)] for non-background colors."""
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    first = {}
    for i, r in enumerate(inp):
        for j, v in enumerate(r):
            if v != bg and v not in first:
                first[v] = (i, j)
    return [(c, cnt[c], first[c]) for c in cnt if c != bg]


def nested(sizes_colors, side, anchor="center"):
    """Square canvas; each cell takes the color of the smallest square covering it."""
    sc = sorted(sizes_colors)
    g = [[0] * side for _ in range(side)]
    for i in range(side):
        for j in range(side):
            for s, c in sc:
                if s > side:
                    continue
                if anchor == "center":
                    o = (side - s) // 2
                    ok = o <= i < o + s and o <= j < o + s
                elif anchor == "tl":
                    ok = i < s and j < s
                else:
                    ok = i >= side - s and j >= side - s
                if ok:
                    g[i][j] = c
                    break
    return g


def reverse_colors(inp, out):
    b = sorted(bars(inp), key=lambda x: x[1])
    sizes = [x[1] for x in b]
    cols = [x[0] for x in b][::-1]
    return nested(list(zip(sizes, cols)), max(sizes))


def bigger_canvas(inp, out):
    b = bars(inp)
    s = max(x[1] for x in b) + 1
    return nested([(x[1] + 1, x[0]) for x in b], s)


def center_unfilled(inp, out):
    b = sorted(bars(inp), key=lambda x: x[1])
    inner = b[0][0]
    return [[0 if v == inner else v for v in r] for r in out]


def reading_order_colors(inp, out):
    b = bars(inp)
    sizes = sorted(x[1] for x in b)
    cols = [x[0] for x in sorted(b, key=lambda x: x[2])]
    return nested(list(zip(sizes, cols)), max(sizes))


def outer_only(inp, out):
    return [[v if i in (0, len(out) - 1) or j in (0, len(out[0]) - 1) else 0
             for j, v in enumerate(r)] for i, r in enumerate(out)]


def anchored_tl(inp, out):
    b = bars(inp)
    return nested([(x[1], x[0]) for x in b], max(x[1] for x in b), "tl")


def anchored_br(inp, out):
    b = bars(inp)
    return nested([(x[1], x[0]) for x in b], max(x[1] for x in b), "br")


def second_longest_canvas(inp, out):
    b = sorted(bars(inp), key=lambda x: -x[1])
    s = b[1][1]
    return nested([(x[1], x[0]) for x in b[1:]], s)


def swap_outer_two(inp, out):
    b = sorted(bars(inp), key=lambda x: -x[1])
    c0, c1 = b[0][0], b[1][0]
    m = {c0: c1, c1: c0}
    return [[m.get(v, v) for v in r] for r in out]


def solid_longest(inp, out):
    b = max(bars(inp), key=lambda x: x[1])
    return [[b[0]] * len(out[0]) for _ in out]


def background_ring_inside(inp, out):
    """Canvas gets one extra frame of background color (0) as the outermost ring."""
    h, w = len(out), len(out[0])
    g = [[0] * (w + 2) for _ in range(h + 2)]
    for i in range(h):
        for j in range(w):
            g[i + 1][j + 1] = out[i][j]
    return g


ALTERNATIVES = [
    ("frame colors in reverse length order (shortest bar outermost)", reverse_colors),
    ("canvas one cell wider than the longest bar, every frame one larger", bigger_canvas),
    ("innermost square left as background", center_unfilled),
    ("frame colors taken in reading order of the bars instead of by length", reading_order_colors),
    ("only the outer frame drawn, inside left empty", outer_only),
    ("nested squares anchored at the top-left corner instead of centered", anchored_tl),
    ("nested squares anchored at the bottom-right corner instead of centered", anchored_br),
    ("canvas as wide as the second longest bar, longest bar dropped", second_longest_canvas),
    ("colors of the two longest bars swapped", swap_outer_two),
    ("every cell takes the color of the longest bar", solid_longest),
    ("output padded with a background border around the frames", background_ring_inside),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/3ee1011a.json')))
    train = task["train"]
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error:", e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
