from pathlib import Path
import json
from collections import Counter

def bg_of(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]

def comps(g, bg, conn=4):
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    if conn == 4:
        nb = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    else:
        nb = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            col = g[r][c]
            st = [(r, c)]
            seen.add((r, c))
            cells = []
            while st:
                y, x = st.pop()
                cells.append((y, x))
                for dy, dx in nb:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and g[ny][nx] == col:
                        seen.add((ny, nx))
                        st.append((ny, nx))
            res.append((col, sorted(cells)))
    return res

def norm(cells):
    my = min(y for y, x in cells)
    mx = min(x for y, x in cells)
    return frozenset((y - my, x - mx) for y, x in cells)

def blank_color(inp, out):
    cnt = Counter()
    for a, b in zip(inp, out):
        for u, v in zip(a, b):
            if u != v:
                cnt[u] += 1
    return cnt.most_common(1)[0][0]

def copy(g):
    return [r[:] for r in g]

def split(inp, out, conn=4):
    bg = bg_of(inp)
    bl = blank_color(inp, out)
    cs = comps(inp, bg, conn)
    blanks = [c for c in cs if c[0] == bl]
    pats = [c for c in cs if c[0] != bl]
    return bg, bl, blanks, pats

def paint(g, cells, col):
    for y, x in cells:
        g[y][x] = col

def center(cells):
    return (sum(y for y, x in cells) / len(cells), sum(x for y, x in cells) / len(cells))

def matched_color(b, pats, key=norm):
    for col, cells in pats:
        if key(cells) == key(b[1]):
            return col
    return None

# 1. all blank shapes get the single most common other color
def single_color(inp, out):
    bg, bl, blanks, pats = split(inp, out)
    col = Counter(c for c, cells in pats for _ in cells).most_common(1)[0][0]
    g = copy(inp)
    for b in blanks:
        paint(g, b[1], col)
    return g

# 2. nearest other shape's color
def nearest(inp, out):
    bg, bl, blanks, pats = split(inp, out)
    g = copy(inp)
    for b in blanks:
        cy, cx = center(b[1])
        best = min(pats, key=lambda p: (center(p[1])[0] - cy) ** 2 + (center(p[1])[1] - cx) ** 2)
        paint(g, b[1], best[0])
    return g

# 3. largest other shape's color
def largest(inp, out):
    bg, bl, blanks, pats = split(inp, out)
    col = max(pats, key=lambda p: len(p[1]))[0]
    g = copy(inp)
    for b in blanks:
        paint(g, b[1], col)
    return g

# 4. wrong direction: the pattern shapes take the blank color
def reverse(inp, out):
    bg, bl, blanks, pats = split(inp, out)
    g = copy(inp)
    for b in blanks:
        for p in pats:
            if norm(p[1]) == norm(b[1]):
                paint(g, p[1], bl)
    return g

# 5. blank shapes erased to background
def erase(inp, out):
    bg, bl, blanks, pats = split(inp, out)
    g = copy(inp)
    for b in blanks:
        paint(g, b[1], bg)
    return g

# 6. matched color fills the whole bounding box of the blank shape
def fill_box(inp, out):
    bg, bl, blanks, pats = split(inp, out)
    g = copy(inp)
    for b in blanks:
        col = matched_color(b, pats)
        if col is None:
            return None
        ys = [y for y, x in b[1]]
        xs = [x for y, x in b[1]]
        for y in range(min(ys), max(ys) + 1):
            for x in range(min(xs), max(xs) + 1):
                g[y][x] = col
    return g

# 7. recolor shifted one column right (off-by-one offset)
def shifted(inp, out):
    bg, bl, blanks, pats = split(inp, out)
    g = [[bg] * len(inp[0]) for _ in inp]
    for y, row in enumerate(inp):
        for x, v in enumerate(row):
            if v != bl:
                g[y][x] = v
    w = len(inp[0])
    for b in blanks:
        col = matched_color(b, pats)
        if col is None:
            return None
        for y, x in b[1]:
            if x + 1 < w:
                g[y][x + 1] = col
    return g

# 8. match by bounding-box size only, first shape of that size wins
def match_bbox_size(inp, out):
    bg, bl, blanks, pats = split(inp, out)
    def dims(cells):
        n = norm(cells)
        return (max(y for y, x in n) + 1, max(x for y, x in n) + 1)
    g = copy(inp)
    for b in blanks:
        col = None
        for p in pats:
            if dims(p[1]) == dims(b[1]):
                col = p[0]
                break
        if col is None:
            col = pats[0][0]
        paint(g, b[1], col)
    return g

# 9. match by cell count only (ignores shape), pick the largest-count match
def match_count(inp, out):
    bg, bl, blanks, pats = split(inp, out)
    g = copy(inp)
    for b in blanks:
        cands = [p for p in pats if len(p[1]) == len(b[1])]
        col = cands[-1][0] if cands else pats[-1][0]
        paint(g, b[1], col)
    return g

# 10. only the first blank shape in reading order is recolored; the rest stay;
#     where there is just one blank shape, it is left blank instead
def first_only(inp, out):
    bg, bl, blanks, pats = split(inp, out)
    g = copy(inp)
    if len(blanks) == 1:
        return g
    b = blanks[0]
    col = matched_color(b, pats)
    if col is None:
        return None
    paint(g, b[1], col)
    return g

# 11. blank color taken to be the least frequent color instead of the changed one
def wrong_blank(inp, out):
    bg = bg_of(inp)
    cnt = Counter(v for r in inp for v in r if v != bg)
    bl = min(cnt, key=lambda c: (cnt[c], c))
    true_bl = blank_color(inp, out)
    if bl == true_bl:
        bl = max(cnt, key=lambda c: (cnt[c], -c))
    cs = comps(inp, bg)
    blanks = [c for c in cs if c[0] == bl]
    pats = [c for c in cs if c[0] != bl]
    g = copy(inp)
    for b in blanks:
        col = matched_color(b, pats)
        if col is not None:
            paint(g, b[1], col)
    return g

# 12. matched shape swaps colors with the blank shape (both recolored)
def swap_both(inp, out):
    bg, bl, blanks, pats = split(inp, out)
    g = copy(inp)
    for b in blanks:
        for p in pats:
            if norm(p[1]) == norm(b[1]):
                paint(g, b[1], p[0])
                paint(g, p[1], bl)
                break
    return g

ALTERNATIVES = [
    ("all blank shapes take the most common other color", single_color),
    ("blank shape takes the color of the nearest other shape", nearest),
    ("blank shapes take the color of the largest other shape", largest),
    ("direction reversed: matching shapes take the blank color", reverse),
    ("blank shapes are erased to background", erase),
    ("matched color fills the whole bounding box of the blank shape", fill_box),
    ("recolored shape drawn one column to the right of the blank shape", shifted),
    ("match by bounding-box size only, first such shape wins", match_bbox_size),
    ("match by cell count only, last such shape wins", match_count),
    ("only the first blank shape is recolored (none if only one)", first_only),
    ("blank color taken as the least frequent color", wrong_blank),
    ("blank and matched shape swap colors", swap_both),
]

def valid(res, out):
    if res is None or not isinstance(res, list) or not res:
        return False
    if not all(isinstance(r, list) and len(r) == len(res[0]) and len(r) > 0 for r in res):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in res for v in r):
        return False
    return res != out

if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/2a5f8217.json')))
    train = task["train"]
    print("pairs:", len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                r = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", fn.__name__, e)
                r = None
            n += valid(r, p["output"])
        print(n, desc)
