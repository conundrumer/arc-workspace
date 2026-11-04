from pathlib import Path
import json
from collections import Counter


def analyze(inp):
    H, W = len(inp), len(inp[0])
    bg = Counter(v for r in inp for v in r).most_common(1)[0][0]
    seen = set()
    comps = []
    for r in range(H):
        for c in range(W):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            col = inp[r][c]
            st = [(r, c)]
            seen.add((r, c))
            cells = []
            while st:
                y, x = st.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and (ny, nx) not in seen and inp[ny][nx] == col:
                        seen.add((ny, nx))
                        st.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            box = (min(ys), min(xs), max(ys), max(xs))
            area = (box[2] - box[0] + 1) * (box[3] - box[1] + 1)
            comps.append(dict(cells=cells, box=box, col=col, rect=(area == len(cells))))
    rects = [c for c in comps if c["rect"]]
    marks = [c for c in comps if not c["rect"]]
    mcol = marks[0]["col"] if marks else None
    return bg, rects, marks, mcol


def copy(g):
    return [list(r) for r in g]


def erase_marks(inp):
    bg, rects, marks, mcol = analyze(inp)
    g = copy(inp)
    for m in marks:
        for y, x in m["cells"]:
            g[y][x] = bg
    return g


def dims(r):
    b = r["box"]
    return b[2] - b[0] + 1, b[3] - b[1] + 1


def paint_centers(g, rects, col, pred=lambda h, w: h % 2 and w % 2, off=(0, 0)):
    for r in rects:
        h, w = dims(r)
        if pred(h, w):
            y = r["box"][0] + h // 2 + off[0]
            x = r["box"][1] + w // 2 + off[1]
            if 0 <= y < len(g) and 0 <= x < len(g[0]):
                g[y][x] = col
    return g


def no_erase(inp, out):
    bg, rects, marks, mcol = analyze(inp)
    g = copy(out)
    for m in marks:
        for y, x in m["cells"]:
            g[y][x] = mcol
    return g


def center_bg(inp, out):
    bg, rects, marks, mcol = analyze(inp)
    return paint_centers(erase_marks(inp), rects, bg)


def squares_only(inp, out):
    bg, rects, marks, mcol = analyze(inp)
    return paint_centers(erase_marks(inp), rects, mcol, lambda h, w: h == w and h % 2)


def largest_only(inp, out):
    bg, rects, marks, mcol = analyze(inp)
    odd = [r for r in rects if dims(r)[0] % 2 and dims(r)[1] % 2]
    if not odd:
        return None
    best = max(odd, key=lambda r: dims(r)[0] * dims(r)[1])
    return paint_centers(erase_marks(inp), [best], mcol)


def fill_interior(inp, out):
    bg, rects, marks, mcol = analyze(inp)
    g = erase_marks(inp)
    for r in rects:
        h, w = dims(r)
        if h % 2 and w % 2 and h > 1 and w > 1:
            for y in range(r["box"][0] + 1, r["box"][2]):
                for x in range(r["box"][1] + 1, r["box"][3]):
                    g[y][x] = mcol
    return g


def skip_singles(inp, out):
    bg, rects, marks, mcol = analyze(inp)
    return paint_centers(erase_marks(inp), rects, mcol,
                         lambda h, w: h % 2 and w % 2 and h * w > 1)


def shifted(inp, out):
    bg, rects, marks, mcol = analyze(inp)
    return paint_centers(erase_marks(inp), rects, mcol, off=(0, 1))


def even_floor(inp, out):
    bg, rects, marks, mcol = analyze(inp)
    return paint_centers(erase_marks(inp), rects, mcol, lambda h, w: True)


def middle_line(inp, out):
    # rects with one odd side get the middle line of cells painted
    bg, rects, marks, mcol = analyze(inp)
    g = erase_marks(inp)
    paint_centers(g, rects, mcol)
    for r in rects:
        h, w = dims(r)
        b = r["box"]
        if h % 2 and not w % 2:
            for x in range(b[1], b[3] + 1):
                g[b[0] + h // 2][x] = mcol
        elif w % 2 and not h % 2:
            for y in range(b[0], b[2] + 1):
                g[y][b[1] + w // 2] = mcol
    return g


def stamp_marker(inp, out):
    bg, rects, marks, mcol = analyze(inp)
    if not marks:
        return None
    m = marks[0]
    b = m["box"]
    cy, cx = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
    g = erase_marks(inp)
    for r in rects:
        h, w = dims(r)
        if h % 2 and w % 2:
            ry, rx = r["box"][0] + h // 2, r["box"][1] + w // 2
            for y, x in m["cells"]:
                ny, nx = ry + y - cy, rx + x - cx
                if 0 <= ny < len(g) and 0 <= nx < len(g[0]):
                    g[ny][nx] = mcol
    return g


def only_erase(inp, out):
    return erase_marks(inp)


def corner_instead(inp, out):
    bg, rects, marks, mcol = analyze(inp)
    g = erase_marks(inp)
    for r in rects:
        h, w = dims(r)
        if h % 2 and w % 2:
            g[r["box"][0]][r["box"][1]] = mcol
    return g


_RAW = [
    ("marker shape left in place, centers still painted", no_erase),
    ("centers painted with the background color", center_bg),
    ("only square rectangles get a center mark", squares_only),
    ("only the largest odd rectangle gets a center mark", largest_only),
    ("whole interior of each odd rectangle is filled with the marker color", fill_interior),
    ("single-cell rectangles are skipped", skip_singles),
    ("center mark is one column right of the true center", shifted),
    ("even-sized rectangles also get a (floor) center mark", even_floor),
    ("rectangles with one odd side get their middle line painted", middle_line),
    ("marker shape is stamped at each odd rectangle's center", stamp_marker),
    ("marker erased but no center marks painted", only_erase),
    ("mark is painted at the top-left corner of each odd rectangle instead of its center", corner_instead),
]


def _wrap(f):
    def g(inp, out):
        res = f(inp, out)
        if res is None or res == out:
            return None
        return res
    return g


ALTERNATIVES = [(d, _wrap(f)) for d, f in _RAW]


def valid(g, out):
    if g is None or not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/22806e14.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for d, f in ALTERNATIVES:
        n = sum(valid(f(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, d)
