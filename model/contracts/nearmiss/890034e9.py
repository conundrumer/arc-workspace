from pathlib import Path
import json
from collections import Counter

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/890034e9.json')


def copy(g):
    return [row[:] for row in g]


def info(inp, out):
    """New frame bbox and color (from the diff), and the original frame bbox."""
    H, W = len(inp), len(inp[0])
    ch = [(r, c) for r in range(H) for c in range(W) if inp[r][c] != out[r][c]]
    r0 = min(r for r, c in ch); r1 = max(r for r, c in ch)
    c0 = min(c for r, c in ch); c1 = max(c for r, c in ch)
    col = out[ch[0][0]][ch[0][1]]
    h, w = r1 - r0 + 1, c1 - c0 + 1
    orig = None
    for a in range(H - h + 1):
        for b in range(W - w + 1):
            if (a, b) == (r0, c0):
                continue
            if all(inp[r][c] == col for r, c in border(a, b, a + h - 1, b + w - 1)) and \
               all(inp[r][c] == 0 for r in range(a + 1, a + h - 1) for c in range(b + 1, b + w - 1)):
                orig = (a, b, a + h - 1, b + w - 1)
    return (r0, c0, r1, c1), col, orig


def border(r0, c0, r1, c1):
    cells = []
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if r in (r0, r1) or c in (c0, c1):
                cells.append((r, c))
    return cells


def paint(g, cells, v):
    H, W = len(g), len(g[0])
    for r, c in cells:
        if 0 <= r < H and 0 <= c < W:
            g[r][c] = v


def base(inp, out):
    """Input with the true new frame erased."""
    g = copy(out)
    (r0, c0, r1, c1), col, orig = info(inp, out)
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            g[r][c] = inp[r][c]
    return g


def wrong_color(inp, out):
    (r0, c0, r1, c1), col, orig = info(inp, out)
    cnt = Counter(v for row in inp for v in row if v != col and v != 0)
    d = cnt.most_common(1)[0][0]
    g = base(inp, out)
    paint(g, border(r0, c0, r1, c1), d)
    return g


def too_big(inp, out):
    (r0, c0, r1, c1), col, orig = info(inp, out)
    g = base(inp, out)
    paint(g, border(r0 - 1, c0 - 1, r1 + 1, c1 + 1), col)
    return g


def too_small(inp, out):
    (r0, c0, r1, c1), col, orig = info(inp, out)
    g = base(inp, out)
    paint(g, border(r0 + 1, c0 + 1, r1 - 1, c1 - 1), col)
    return g


def filled(inp, out):
    (r0, c0, r1, c1), col, orig = info(inp, out)
    g = base(inp, out)
    paint(g, [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)], col)
    return g


def transposed_size(inp, out):
    (r0, c0, r1, c1), col, orig = info(inp, out)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    g = base(inp, out)
    paint(g, border(r0, c0, r0 + w - 1, c0 + h - 1), col)
    return g


def shifted(inp, out):
    (r0, c0, r1, c1), col, orig = info(inp, out)
    g = base(inp, out)
    paint(g, border(r0 + 1, c0 + 1, r1 + 1, c1 + 1), col)
    return g


def mirrored_place(inp, out):
    (r0, c0, r1, c1), col, orig = info(inp, out)
    W = len(inp[0])
    g = base(inp, out)
    paint(g, border(r0, W - 1 - c1, r1, W - 1 - c0), col)
    return g


def corners_only(inp, out):
    (r0, c0, r1, c1), col, orig = info(inp, out)
    g = base(inp, out)
    paint(g, [(r0, c0), (r0, c1), (r1, c0), (r1, c1)], col)
    return g


def moved_not_copied(inp, out):
    (r0, c0, r1, c1), col, orig = info(inp, out)
    if orig is None:
        return None
    g = copy(out)
    paint(g, border(*orig), 0)
    return g


def transposed_place(inp, out):
    (r0, c0, r1, c1), col, orig = info(inp, out)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    g = base(inp, out)
    paint(g, border(c0, r0, c0 + h - 1, r0 + w - 1), col)
    return g


def unchanged(inp, out):
    return copy(inp)


ALTERNATIVES = [
    ("copy drawn in a wrong color (most common non-background color)", wrong_color),
    ("copy drawn one ring too large, around the right hole", too_big),
    ("copy drawn one ring too small, on the hole's own edge cells", too_small),
    ("copy drawn as a filled rectangle instead of an outline", filled),
    ("copy drawn with height and width swapped", transposed_size),
    ("copy drawn offset by one cell down and right", shifted),
    ("copy drawn at the horizontally mirrored location", mirrored_place),
    ("copy drawn at the transposed (row/col swapped) location with swapped size", transposed_place),
    ("only the four corners of the copy drawn", corners_only),
    ("frame moved: original frame erased to 0 as well", moved_not_copied),
    ("no new frame drawn, input returned", unchanged),
]


def valid(g, true):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != true


if __name__ == "__main__":
    task = json.load(open(TASK))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", e)
                g = None
            n += valid(g, p["output"])
        print(n, desc)
