from pathlib import Path
import json

def panels(g):
    """Bounding boxes (r0, c0, r1, c1) of 4-connected non-zero regions, reading order."""
    h, w = len(g), len(g[0])
    seen = set()
    boxes = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == 0 or (r, c) in seen:
                continue
            st = [(r, c)]
            seen.add((r, c))
            r0 = r1 = r
            c0 = c1 = c
            while st:
                y, x = st.pop()
                r0, r1, c0, c1 = min(r0, y), max(r1, y), min(c0, x), max(c1, x)
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != 0 and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        st.append((ny, nx))
            boxes.append((r0, c0, r1, c1))
    return boxes

def crop(g, b):
    r0, c0, r1, c1 = b
    return [row[c0:c1 + 1] for row in g[r0:r1 + 1]]

def crosses(g, b, mark=3):
    r0, c0, r1, c1 = b
    n = 0
    for r in range(r0 + 1, r1):
        for c in range(c0 + 1, c1):
            if all(g[y][x] == mark for y, x in ((r, c), (r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))):
                n += 1
    return n

def count_cells(g, b, mark=3):
    return sum(row.count(mark) for row in crop(g, b))

def mark_components(g, b, mark=3):
    """Number of 4-connected mark components of size >= 3 (partial crosses count)."""
    r0, c0, r1, c1 = b
    seen = set()
    n = 0
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if g[r][c] != mark or (r, c) in seen:
                continue
            st = [(r, c)]
            seen.add((r, c))
            size = 0
            while st:
                y, x = st.pop()
                size += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if r0 <= ny <= r1 and c0 <= nx <= c1 and g[ny][nx] == mark and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        st.append((ny, nx))
            if size >= 3:
                n += 1
    return n

def vbars(g, b, mark=3):
    """Vertical runs of three mark cells inside the panel (ignores the horizontal arms)."""
    r0, c0, r1, c1 = b
    return sum(1 for r in range(r0, r1 - 1) for c in range(c0, c1 + 1)
               if g[r][c] == g[r + 1][c] == g[r + 2][c] == mark)

def best(g, key, reverse=True):
    bs = panels(g)
    vals = [key(b) for b in bs]
    t = max(vals) if reverse else min(vals)
    return bs[vals.index(t)]

def true_box(inp):
    return best(inp, lambda b: crosses(inp, b))

def fewest_crosses(inp, out):
    return crop(inp, best(inp, lambda b: crosses(inp, b), reverse=False))

def most_mark_cells(inp, out):
    return crop(inp, best(inp, lambda b: count_cells(inp, b)))

def largest_area(inp, out):
    return crop(inp, best(inp, lambda b: (b[2] - b[0] + 1) * (b[3] - b[1] + 1)))

def second_most_crosses(inp, out):
    bs = panels(inp)
    if len(bs) < 3:
        return None
    order = sorted(range(len(bs)), key=lambda i: -crosses(inp, bs[i]))
    return crop(inp, bs[order[1]])

def margin_crop(inp, out):
    r0, c0, r1, c1 = true_box(inp)
    h, w = len(inp), len(inp[0])
    return [row[max(c0 - 1, 0):min(c1 + 2, w)] for row in inp[max(r0 - 1, 0):min(r1 + 2, h)]]

def short_crop(inp, out):
    r0, c0, r1, c1 = true_box(inp)
    return [row[c0:c1] for row in inp[r0:r1]]

def swapped_colors(inp, out):
    sw = {3: 8, 8: 3}
    return [[sw.get(v, v) for v in row] for row in out]

def one_cross_only(inp, out):
    r0, c0, r1, c1 = true_box(inp)
    for r in range(r0 + 1, r1):
        for c in range(c0 + 1, c1):
            if all(inp[y][x] == 3 for y, x in ((r, c), (r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))):
                return [row[c - 1:c + 2] for row in inp[r - 1:r + 2]]
    return None

def transposed(inp, out):
    return [list(r) for r in zip(*out)]

def all_content_crop(inp, out):
    h, w = len(inp), len(inp[0])
    rs = [r for r in range(h) if any(inp[r])]
    cs = [c for c in range(w) if any(inp[r][c] for r in range(h))]
    return [row[cs[0]:cs[-1] + 1] for row in inp[rs[0]:rs[-1] + 1]]

def most_mark_components(inp, out):
    return crop(inp, best(inp, lambda b: count_cells(inp, b), reverse=False))

def first_panel(inp, out):
    return crop(inp, panels(inp)[0])

ALTERNATIVES = [
    ("panel with the fewest crosses", fewest_crosses),
    ("panel with the most mark-colored cells", most_mark_cells),
    ("largest panel by area", largest_area),
    ("panel with the second most crosses", second_most_crosses),
    ("correct panel cropped with a one-cell margin of background", margin_crop),
    ("correct panel cropped one row and one column short", short_crop),
    ("correct panel with the two colors swapped", swapped_colors),
    ("only a single 3x3 cross cut out of the right panel", one_cross_only),
    ("correct panel transposed", transposed),
    ("bounding box of all non-background content", all_content_crop),
    ("panel with the fewest mark-colored cells", most_mark_components),
    ("first panel in reading order", first_panel),
]

def valid(g, out):
    if not isinstance(g, list) or not g or not isinstance(g[0], list) or not g[0]:
        return False
    w = len(g[0])
    for row in g:
        if not isinstance(row, list) or len(row) != w:
            return False
        for v in row:
            if type(v) is not int or not 0 <= v <= 9:
                return False
    return g != out

if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/2c0b0aff.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
