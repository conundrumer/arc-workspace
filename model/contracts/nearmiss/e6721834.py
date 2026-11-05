import json
from collections import Counter
from pathlib import Path


def mode(cells):
    return Counter(cells).most_common(1)[0][0]


def halves(inp, out):
    """Return (dot_half, obj_half) as grids; the dot half has the output's background."""
    h, w = len(inp), len(inp[0])
    bg = mode([c for r in out for c in r])
    if len(out) == h // 2 and len(out[0]) == w:
        a, b = inp[: h // 2], inp[h // 2:]
    else:
        a = [r[: w // 2] for r in inp]
        b = [r[w // 2:] for r in inp]
    ma = mode([c for r in a for c in r])
    return (a, b) if ma == bg else (b, a)


def components(g, bg):
    h, w = len(g), len(g[0])
    seen = set()
    comps = []
    for i in range(h):
        for j in range(w):
            if g[i][j] != bg and (i, j) not in seen:
                st, comp = [(i, j)], []
                seen.add((i, j))
                while st:
                    y, x = st.pop()
                    comp.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if (0 <= ny < h and 0 <= nx < w and g[ny][nx] != bg
                                and (ny, nx) not in seen):
                            seen.add((ny, nx))
                            st.append((ny, nx))
                comps.append(comp)
    return comps


def copy(g):
    return [r[:] for r in g]


def obj_half_unchanged(inp, out):
    return copy(halves(inp, out)[1])


def dots_erased_only(inp, out):
    dot, _ = halves(inp, out)
    bg = mode([c for r in dot for c in r])
    return [[bg] * len(dot[0]) for _ in dot]


def dots_kept(inp, out):
    return copy(halves(inp, out)[0])


def input_unchanged(inp, out):
    return copy(inp)


def rects_unmoved(inp, out):
    dot, obj = halves(inp, out)
    dbg = mode([c for r in dot for c in r])
    obg = mode([c for r in obj for c in r])
    return [[dbg if c == obg else c for c in r] for r in obj]


def marks_as_body(inp, out):
    bg = mode([c for r in out for c in r])
    g = copy(out)
    for comp in components(out, bg):
        body = mode([out[y][x] for y, x in comp])
        for y, x in comp:
            g[y][x] = body
    return g


def only_marks(inp, out):
    bg = mode([c for r in out for c in r])
    g = copy(out)
    for comp in components(out, bg):
        body = mode([out[y][x] for y, x in comp])
        for y, x in comp:
            if g[y][x] == body:
                g[y][x] = bg
    return g


def shifted_one_down_right(inp, out):
    bg = mode([c for r in out for c in r])
    h, w = len(out), len(out[0])
    g = [[bg] * w for _ in range(h)]
    for i in range(h - 1):
        for j in range(w - 1):
            g[i + 1][j + 1] = out[i][j]
    return g


def flip_h(inp, out):
    return [r[::-1] for r in out]


def flip_v(inp, out):
    return [r[:] for r in out[::-1]]


def only_largest_rect(inp, out):
    bg = mode([c for r in out for c in r])
    comps = components(out, bg)
    if len(comps) < 2:
        return None
    keep = max(comps, key=len)
    g = [[bg] * len(out[0]) for _ in out]
    for y, x in keep:
        g[y][x] = out[y][x]
    return g


def object_background(inp, out):
    dot, obj = halves(inp, out)
    dbg = mode([c for r in dot for c in r])
    obg = mode([c for r in obj for c in r])
    return [[obg if c == dbg else c for c in r] for r in out]


ALTERNATIVES = [
    ("output is the object half as given (wrong half)", obj_half_unchanged),
    ("output is the dot half with dots erased and no rectangle drawn", dots_erased_only),
    ("output is the dot half with its dots kept", dots_kept),
    ("output is the whole input unchanged", input_unchanged),
    ("rectangles drawn on the dot half at their original coordinates, not moved to the dots", rects_unmoved),
    ("every moved rectangle drawn in its body color only, marks lost", marks_as_body),
    ("only the marks drawn, rectangle bodies left out", only_marks),
    ("every rectangle placed one cell too far down and right", shifted_one_down_right),
    ("output mirrored left to right", flip_h),
    ("output mirrored top to bottom", flip_v),
    ("only the largest rectangle drawn, the others dropped", only_largest_rect),
    ("output keeps the object half's background color instead of the dot half's", object_background),
]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(type(c) is int and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/e6721834.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = sum(valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, "/", len(pairs), desc)
