from pathlib import Path
import json
from collections import Counter

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/5751f35e.json')


def copy(g):
    return [r[:] for r in g]


def bg_of(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def ring(r, c, h, w):
    return min(r, c, h - 1 - r, w - 1 - c)


def starts(inp, key=min, depth=ring):
    """Per ink color, the ring depth at which its box starts."""
    h, w = len(inp), len(inp[0])
    bg = bg_of(inp)
    ds = {}
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v != bg:
                ds.setdefault(v, []).append(depth(r, c, h, w))
    return {v: key(d) for v, d in ds.items()}


def paint(inp, st, depth=ring):
    h, w = len(inp), len(inp[0])
    bg = bg_of(inp)
    g = [[bg] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            k = depth(r, c, h, w)
            best = None
            for v, s in st.items():
                if s <= k and (best is None or s > st[best]):
                    best = v
            if best is not None:
                g[r][c] = best
    return g


def outer_takes_second(inp, out):
    """The outer ring takes the color of the next ring in."""
    g = copy(out)
    h, w = len(g), len(g[0])
    for r in range(h):
        for c in range(w):
            if ring(r, c, h, w) == 0:
                g[r][c] = out[1][1]
    return g


def box_of_color(g, col):
    cells = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v == col]
    return (min(r for r, _ in cells), max(r for r, _ in cells),
            min(c for _, c in cells), max(c for _, c in cells))


def core_grown(inp, out):
    """The innermost box is one ring too large."""
    g = copy(out)
    h, w = len(g), len(g[0])
    col = out[h // 2][w // 2]
    r0, r1, c0, c1 = box_of_color(out, col)
    for r in range(max(r0 - 1, 0), min(r1 + 1, h - 1) + 1):
        for c in range(max(c0 - 1, 0), min(c1 + 1, w - 1) + 1):
            g[r][c] = col
    return g


def core_shrunk(inp, out):
    """The innermost box is one ring too small."""
    g = copy(out)
    h, w = len(g), len(g[0])
    col = out[h // 2][w // 2]
    r0, r1, c0, c1 = box_of_color(out, col)
    surround = out[r0 - 1][c0 - 1]
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if r in (r0, r1) or c in (c0, c1):
                g[r][c] = surround
    return g


def starts_shifted(inp, out):
    """Every box starts one ring deeper than it should."""
    st = {v: s + 1 for v, s in starts(inp).items()}
    return paint(inp, st)


def deepest_start(inp, out):
    """A color's box starts at its deepest cell, not its shallowest."""
    return paint(inp, starts(inp, key=max))


def median_start(inp, out):
    """A color's box starts at the median depth of its cells."""
    def med(d):
        d = sorted(d)
        return d[len(d) // 2]
    return paint(inp, starts(inp, key=med))


def stripes(inp, out):
    """Depth measured by distance to the top and bottom edges only."""
    def d(r, c, h, w):
        return min(r, h - 1 - r)
    return paint(inp, starts(inp, depth=d), depth=d)


def column_only(inp, out):
    """Depth measured by distance to the left and right edges only."""
    def d(r, c, h, w):
        return min(c, w - 1 - c)
    return paint(inp, starts(inp, depth=d), depth=d)


def order_by_count(inp, out):
    """Colors nest by cell count: most frequent outermost."""
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = bg_of(inp)
    cols = sorted((v for v in cnt if v != bg), key=lambda v: (-cnt[v], v))
    real = starts(inp)
    st = {}
    for v, s in zip(cols, sorted(real.values())):
        st[v] = s
    g = paint(inp, st)
    return g


def fill_with_bg_only(inp, out):
    """Damage is blanked: ink stays where it is, damaged cells inside the nest stay bg."""
    h, w = len(inp), len(inp[0])
    g = copy(out)
    bg = bg_of(inp)
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg:
                g[r][c] = bg
    return g


def mirror_lr_only(inp, out):
    """Damage recovered only from the left-right mirror cell."""
    h, w = len(inp), len(inp[0])
    bg = bg_of(inp)
    g = copy(inp)
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg and inp[r][w - 1 - c] != bg:
                g[r][c] = inp[r][w - 1 - c]
    return g


def ring_majority(inp, out):
    """Each ring takes its most common ink color; a ring with no ink is bg."""
    h, w = len(inp), len(inp[0])
    bg = bg_of(inp)
    cnt = {}
    for r in range(h):
        for c in range(w):
            if inp[r][c] != bg:
                cnt.setdefault(ring(r, c, h, w), Counter())[inp[r][c]] += 1
    return [[cnt[ring(r, c, h, w)].most_common(1)[0][0] if ring(r, c, h, w) in cnt else bg
             for c in range(w)] for r in range(h)]


def input_unchanged(inp, out):
    """Nothing is repaired."""
    return copy(inp)


ALTERNATIVES = [
    ("outer ring takes the color of the second ring", outer_takes_second),
    ("innermost box is one ring too large", core_grown),
    ("innermost box is one ring too small", core_shrunk),
    ("every box starts one ring deeper than its shallowest cell", starts_shifted),
    ("a color's box starts at its deepest cell", deepest_start),
    ("a color's box starts at the median depth of its cells", median_start),
    ("rings measured by distance to top and bottom edges only", stripes),
    ("rings measured by distance to left and right edges only", column_only),
    ("colors nest by cell count, most frequent outermost", order_by_count),
    ("damaged cells stay background, only ink cells get ring colors", fill_with_bg_only),
    ("damage recovered only from the left-right mirror cell", mirror_lr_only),
    ("nothing is repaired", input_unchanged),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r) and g != out)


if __name__ == '__main__':
    task = json.load(open(TASK))
    pairs = task['train']
    print(f"pairs: {len(pairs)}")
    bad = 0
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g, p['output']):
                ok += 1
        print(f"{ok}/{len(pairs)}  {desc}")
        if ok == 0:
            bad += 1
    print("FAIL" if bad else "OK")
