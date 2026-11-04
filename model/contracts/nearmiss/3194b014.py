from pathlib import Path
import json
from collections import Counter


def bg_of(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def blocks(inp):
    """Per non-bg color: (largest 4-connected component size, bbox) -> list sorted by size desc."""
    bg = bg_of(inp)
    h, w = len(inp), len(inp[0])
    best = {}
    seen = set()
    for i in range(h):
        for j in range(w):
            c = inp[i][j]
            if c == bg or (i, j) in seen:
                continue
            stack = [(i, j)]
            seen.add((i, j))
            cells = []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and (x, y) not in seen and inp[x][y] == c:
                        seen.add((x, y))
                        stack.append((x, y))
            if c not in best or len(cells) > best[c][0]:
                rs = [p[0] for p in cells]
                cs = [p[1] for p in cells]
                best[c] = (len(cells), (min(rs), max(rs), min(cs), max(cs)))
    return sorted(((s, c, bb) for c, (s, bb) in best.items()), reverse=True)


def real_blocks(inp):
    return [b for b in blocks(inp) if b[0] >= 10]


def sq(c, n=3):
    return [[c] * n for _ in range(n)]


def second_largest(inp, out):
    b = real_blocks(inp)
    return sq(b[1][1]) if len(b) > 1 else None


def smallest(inp, out):
    b = real_blocks(inp)
    return sq(b[-1][1]) if len(b) > 1 else None


def most_frequent_nonbg(inp, out):
    bg = bg_of(inp)
    cnt = Counter(c for r in inp for c in r if c != bg)
    return sq(cnt.most_common(1)[0][0])


def topmost(inp, out):
    b = real_blocks(inp)
    return sq(min(b, key=lambda t: t[2][0])[1])


def bottommost(inp, out):
    b = real_blocks(inp)
    return sq(max(b, key=lambda t: t[2][1])[1])


def tallest(inp, out):
    b = real_blocks(inp)
    return sq(max(b, key=lambda t: (t[2][1] - t[2][0], -t[2][2]))[1])


def widest_leftmost_tiebreak(inp, out):
    b = real_blocks(inp)
    return sq(min(b, key=lambda t: (-(t[2][3] - t[2][2]), t[2][2]))[1])


def size_1(inp, out):
    return [[out[0][0]]]


def size_4(inp, out):
    return sq(out[0][0], 4)


def hollow(inp, out):
    g = [r[:] for r in out]
    g[1][1] = bg_of(inp)
    return g


def background_fill(inp, out):
    return sq(bg_of(inp))


def crop_block(inp, out):
    b = real_blocks(inp)
    r0, r1, c0, c1 = b[0][2]
    return [[b[0][1]] * (c1 - c0 + 1) for _ in range(r1 - r0 + 1)]


def bbox_span_with_noise(inp, out):
    # biggest by bbox area of per-color extent over all cells (noise colors win)
    bg = bg_of(inp)
    ext = {}
    for i, r in enumerate(inp):
        for j, c in enumerate(r):
            if c == bg:
                continue
            e = ext.setdefault(c, [i, i, j, j])
            e[0] = min(e[0], i); e[1] = max(e[1], i)
            e[2] = min(e[2], j); e[3] = max(e[3], j)
    c = max(ext, key=lambda k: (ext[k][1] - ext[k][0] + 1) * (ext[k][3] - ext[k][2] + 1))
    return sq(c)


ALTERNATIVES = [
    ("second-largest solid block's color", second_largest),
    ("smallest solid block's color", smallest),
    ("most frequent non-background color overall, noise included", most_frequent_nonbg),
    ("topmost solid block's color", topmost),
    ("bottommost solid block's color", bottommost),
    ("tallest solid block's color", tallest),
    ("widest solid block's color, leftmost on ties", widest_leftmost_tiebreak),
    ("correct color but 1x1 output", size_1),
    ("correct color but 4x4 output (off-by-one size)", size_4),
    ("correct 3x3 with center cell left as background", hollow),
    ("3x3 filled with the background color", background_fill),
    ("crop of the biggest block's bounding box instead of a 3x3", crop_block),
    ("color with the largest bounding-box extent over all its cells, noise included", bbox_span_with_noise),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/3194b014.json')))
    pairs = t["train"]
    print(len(pairs), "train pairs")
    for p in pairs:
        print([(s, c) for s, c, _ in real_blocks(p["input"])], "->", p["output"][0][0])
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
