from pathlib import Path
import json
from collections import Counter

TASK = str(Path(__file__).resolve().parents[3] / 'data/tasks/c3f564a4.json')


def _noise(inp, out):
    return [[inp[r][c] != out[r][c] for c in range(len(inp[0]))] for r in range(len(inp))]


def _period(out):
    row = out[0]
    for k in range(1, len(row)):
        if all(row[c] == row[c + k] for c in range(len(row) - k)):
            return k
    return len(row)


def _apply(inp, out, f):
    """Clean cells keep the input value; noise cells get f(r, c)."""
    nz = _noise(inp, out)
    return [[f(r, c) if nz[r][c] else inp[r][c] for c in range(len(inp[0]))] for r in range(len(inp))]


def most_common_color(inp, out):
    cnt = Counter(v for row in inp for v in row if v != 0)
    col = cnt.most_common(1)[0][0]
    return _apply(inp, out, lambda r, c: col)


def anti_diagonal_flipped(inp, out):
    k = _period(out)
    return _apply(inp, out, lambda r, c: out[0][(c - r) % k])


def nearest_left_clean(inp, out):
    nz = _noise(inp, out)
    W = len(inp[0])

    def f(r, c):
        for d in range(1, W):
            if c - d >= 0 and not nz[r][c - d]:
                return inp[r][c - d]
            if c + d < W and not nz[r][c + d]:
                return inp[r][c + d]
        return 0
    return _apply(inp, out, f)


def nearest_above_clean(inp, out):
    nz = _noise(inp, out)
    H = len(inp)

    def f(r, c):
        for d in range(1, H):
            if r - d >= 0 and not nz[r - d][c]:
                return inp[r - d][c]
            if r + d < H and not nz[r + d][c]:
                return inp[r + d][c]
        return 0
    return _apply(inp, out, f)


def row0_copied_down(inp, out):
    k = _period(out)
    return _apply(inp, out, lambda r, c: out[0][c % k])


def only_largest_block(inp, out):
    nz = _noise(inp, out)
    H, W = len(inp), len(inp[0])
    seen = set()
    comps = []
    for r in range(H):
        for c in range(W):
            if nz[r][c] and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                comp = []
                while st:
                    y, x = st.pop()
                    comp.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        a, b = y + dy, x + dx
                        if 0 <= a < H and 0 <= b < W and nz[a][b] and (a, b) not in seen:
                            seen.add((a, b))
                            st.append((a, b))
                comps.append(comp)
    if len(comps) < 2:
        return None
    big = set(max(comps, key=len))
    return [[out[r][c] if (not nz[r][c] or (r, c) in big) else inp[r][c] for c in range(W)] for r in range(H)]


def top_row_of_block_unfilled(inp, out):
    nz = _noise(inp, out)
    return [[inp[r][c] if (nz[r][c] and (r == 0 or not nz[r - 1][c])) else out[r][c]
             for c in range(len(inp[0]))] for r in range(len(inp))]


def period_one_short(inp, out):
    k = _period(out) - 1
    if k < 1:
        return None
    return _apply(inp, out, lambda r, c: out[0][(r + c) % k])


def period_one_long(inp, out):
    k = _period(out) + 1
    if k > len(out[0]):
        return None
    return _apply(inp, out, lambda r, c: out[0][(r + c) % k])


def row_offset_by_one(inp, out):
    H = len(out)
    return _apply(inp, out, lambda r, c: out[(r + 1) % H][c])


def crop_noise_bbox(inp, out):
    nz = _noise(inp, out)
    rs = [r for r in range(len(nz)) for c in range(len(nz[0])) if nz[r][c]]
    cs = [c for r in range(len(nz)) for c in range(len(nz[0])) if nz[r][c]]
    if not rs:
        return None
    return [out[r][min(cs):max(cs) + 1] for r in range(min(rs), max(rs) + 1)]


def input_unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("fill noise cells with the most common color of the grid", most_common_color),
    ("fill noise by the diagonal in the wrong direction (c-r instead of r+c)", anti_diagonal_flipped),
    ("fill each noise cell with the nearest clean cell in its row", nearest_left_clean),
    ("fill each noise cell with the nearest clean cell in its column", nearest_above_clean),
    ("tile the first row downward with no per-row shift", row0_copied_down),
    ("repair only the largest noise block, leave the others", only_largest_block),
    ("leave the top row of each noise block unfilled (off by one)", top_row_of_block_unfilled),
    ("use a period one shorter than the true period", period_one_short),
    ("use a period one longer than the true period", period_one_long),
    ("read the pattern from the row below (off by one row)", row_offset_by_one),
    ("output only the crop of the noise bounding box", crop_noise_bbox),
    ("return the input unchanged", input_unchanged),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    train = json.load(open(TASK))["train"]
    print("pairs", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                g = None
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
