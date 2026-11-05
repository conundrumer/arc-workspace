import json
from pathlib import Path

LINE, FILL = 2, 8


def segments(inp):
    """Each segment: (horizontal?, fixed index, lo, hi) from 4-connected runs of LINE."""
    h, w = len(inp), len(inp[0])
    seen = set()
    segs = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != LINE or (r, c) in seen:
                continue
            stack, comp = [(r, c)], []
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == LINE and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            rows = {y for y, _ in comp}
            cols = {x for _, x in comp}
            if len(rows) == 1:
                segs.append((True, r, min(cols), max(cols)))
            else:
                segs.append((False, c, min(rows), max(rows)))
    return segs


def at(seg, d, p):
    horiz, f, _, _ = seg
    return (f + d, p) if horiz else (p, f + d)


def paint(inp, seg_filter=None, shrink=0, sides=(-1, 1), color=FILL,
          half=None, over_lines=False, max_d=None, outline=False, d0=False,
          width_of=None):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    segs = segments(inp)
    if seg_filter is not None:
        segs = seg_filter(segs)
    for seg in segs:
        _, f, a, b = seg
        reach = (b - a) // 2 + 2
        start = 0 if d0 else 1
        for d in range(start, reach + 1):
            if max_d is not None and d > max_d:
                break
            lo, hi = a + d + shrink, b - d - shrink
            if width_of is not None:
                lo, hi = width_of(a, b, d)
            ps = list(range(lo, hi + 1))
            if outline:
                ps = [p for p in ps if p in (lo, hi) or (lo + d <= 0)]
                # keep only cells that are on the diamond edge: ends, plus the apex row
                if not ((a + d + shrink) <= (b - d - shrink)):
                    ps = []
            for p in ps:
                if half == "first" and p > (a + b) / 2:
                    continue
                for s in sides:
                    y, x = at(seg, s * d, p)
                    if 0 <= y < h and 0 <= x < w and (over_lines or inp[y][x] == 0):
                        g[y][x] = color
    return g


def true_like(inp):
    return paint(inp)


def one_side(inp, out):
    return paint(inp, sides=(-1,))


def other_side_only(inp, out):
    return paint(inp, sides=(1,))


def wrong_color(inp, out):
    return paint(inp, color=LINE)


def paint_over(inp, out):
    return paint(inp, over_lines=True, d0=True)


def smaller(inp, out):
    return paint(inp, shrink=1)


def larger(inp, out):
    return paint(inp, shrink=-1)


def first_segment_only(inp, out):
    segs = segments(inp)
    if len(segs) < 2:
        return None
    return paint(inp, seg_filter=lambda s: s[:1])


def rectangle(inp, out):
    # band of full segment length out to the largest diamond distance
    def wf(a, b, d):
        return a + 1, b - 1
    return paint(inp, width_of=wf)


def left_half(inp, out):
    return paint(inp, half="first")


def inverted(inp, out):
    def wf(a, b, d):
        H = (b - a) // 2
        k = H + 1 - d
        return a + k, b - k
    return paint(inp, width_of=wf)


def capped_two(inp, out):
    return paint(inp, max_d=2)


def hollow(inp, out):
    g = paint(inp)
    h, w = len(g), len(g[0])
    res = [row[:] for row in g]
    for y in range(h):
        for x in range(w):
            if g[y][x] == FILL and all(
                0 <= y + dy < h and 0 <= x + dx < w and g[y + dy][x + dx] in (FILL, LINE)
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))
            ):
                res[y][x] = 0
    return res


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("fill only the diamond half on the upper/left side of each line", one_side),
    ("fill only the diamond half on the lower/right side of each line", other_side_only),
    ("fill the diamond with the line color 2 instead of 8", wrong_color),
    ("fill the diamond starting at distance 0, so the line cells are overpainted", paint_over),
    ("diamond one step too small: needs cells d+1 steps along the line", smaller),
    ("diamond one step too large: needs cells only d-1 steps along the line", larger),
    ("diamond of only the first segment; other segments get none", first_segment_only),
    ("full rectangle beside the line instead of a tapering diamond", rectangle),
    ("only the half of the diamond up to the segment midpoint", left_half),
    ("inverted diamond: widest row far from the line, narrowest next to it", inverted),
    ("diamond cut off at distance 2 from the line", capped_two),
    ("hollow diamond: interior cells left background", hollow),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/c97c0139.json").read_text())
    train = task["train"]
    # sanity: the reference builder reproduces the true output
    print("reference ok:", all(true_like(p["input"]) == p["output"] for p in train))

    def valid(g, out):
        return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                and len({len(r) for r in g}) == 1
                and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
                and g != out)

    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
