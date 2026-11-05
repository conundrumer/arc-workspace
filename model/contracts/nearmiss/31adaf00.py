import json
from pathlib import Path


def _copy(g):
    return [r[:] for r in g]


def _painted(inp, out):
    return [[inp[r][c] == 0 and out[r][c] != 0 for c in range(len(inp[0]))] for r in range(len(inp))]


def _squares(inp, m, color=0):
    """All squares of side >= m whose cells all equal color: (r, c, n)."""
    h, w = len(inp), len(inp[0])
    res = []
    for n in range(m, min(h, w) + 1):
        for r in range(h - n + 1):
            for c in range(w - n + 1):
                if all(inp[r + i][c + j] == color for i in range(n) for j in range(n)):
                    res.append((r, c, n))
    return res


def _overlap(a, b):
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[2] <= b[1] or b[1] + b[2] <= a[1])


def _components(mask):
    h, w = len(mask), len(mask[0])
    seen = set()
    comps = []
    for r in range(h):
        for c in range(w):
            if mask[r][c] and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                cells = []
                while st:
                    y, x = st.pop()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny][nx] and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                comps.append(cells)
    return comps


def _recolor(inp, out, color):
    p = _painted(inp, out)
    g = _copy(out)
    for r, row in enumerate(p):
        for c, v in enumerate(row):
            if v:
                g[r][c] = color
    return g


def wrong_color_2(inp, out):
    return _recolor(inp, out, 2)


def wrong_color_bg(inp, out):
    return _recolor(inp, out, 5)


def drop_smallest(inp, out):
    comps = _components(_painted(inp, out))
    if len(comps) < 2:
        return None
    small = min(comps, key=len)
    g = _copy(out)
    for r, c in small:
        g[r][c] = 0
    return g


def drop_largest(inp, out):
    comps = _components(_painted(inp, out))
    if len(comps) < 2:
        return None
    big = max(comps, key=len)
    g = _copy(out)
    for r, c in big:
        g[r][c] = 0
    return g


def only_largest(inp, out):
    comps = _components(_painted(inp, out))
    if len(comps) < 2:
        return None
    big = max(comps, key=len)
    g = _copy(inp)
    for r, c in big:
        g[r][c] = 1
    return g


def no_overlap_resolution(inp, out):
    """Paint every empty square of side >= 3, even where squares overlap."""
    g = _copy(inp)
    for r, c, n in _squares(inp, 3):
        for i in range(n):
            for j in range(n):
                g[r + i][c + j] = 1
    return g


def min_side_three(inp, out):
    """Only squares of side >= 3 count, chosen largest first."""
    sq = sorted(_squares(inp, 3), key=lambda s: -s[2])
    chosen = []
    for s in sq:
        if not any(_overlap(s, t) for t in chosen):
            chosen.append(s)
    g = _copy(inp)
    for r, c, n in chosen:
        for i in range(n):
            for j in range(n):
                g[r + i][c + j] = 1
    return g


def min_side_four(inp, out):
    """Only squares of side >= 4 are painted: drop painted parts that are 3x3 squares."""
    sq = _squares(inp, 4)
    g = _copy(inp)
    for r, c, n in sq:
        for i in range(n):
            for j in range(n):
                g[r + i][c + j] = 1
    return g


def paint_dilated(inp, out):
    """Painted squares grow by one cell on the empty cells next to them."""
    p = _painted(inp, out)
    h, w = len(p), len(p[0])
    g = _copy(out)
    for r in range(h):
        for c in range(w):
            if p[r][c]:
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = r + dy, c + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] == 0:
                        g[ny][nx] = 1
    return g


def paint_five_squares(inp, out):
    """Mixes up the background: paints empty squares of the 5 color."""
    g = _copy(inp)
    for r, c, n in _squares(inp, 3, 5):
        for i in range(n):
            for j in range(n):
                g[r + i][c + j] = 1
    return g


def paint_all_overlapping(inp, out):
    """Paints every empty square of side 2 or more, with no overlap resolution."""
    g = _copy(inp)
    for r, c, n in _squares(inp, 2):
        for i in range(n):
            for j in range(n):
                g[r + i][c + j] = 1
    return g


def input_unchanged(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("paints the squares with 2 instead of the new color", wrong_color_2),
    ("paints the squares with the 5 color", wrong_color_bg),
    ("leaves the smallest painted square unpainted", drop_smallest),
    ("leaves the largest painted square unpainted", drop_largest),
    ("paints only the largest square", only_largest),
    ("paints all empty squares of side 3 or more, with no overlap resolution", no_overlap_resolution),
    ("counts only squares of side 3 or more, chosen largest first", min_side_three),
    ("paints only squares of side 4 or more", min_side_four),
    ("paints painted squares plus the empty cells next to them", paint_dilated),
    ("treats 5 as the background and paints squares of 5", paint_five_squares),
    ("paints every empty square of side 2 or more, with no overlap resolution", paint_all_overlapping),
    ("returns the input unchanged", input_unchanged),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/31adaf00.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
