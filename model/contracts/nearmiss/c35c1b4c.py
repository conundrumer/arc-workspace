from pathlib import Path
import json
from collections import Counter

def copy(g):
    return [r[:] for r in g]

def components(g, diag=False):
    h, w = len(g), len(g[0])
    seen = [[False] * w for _ in range(h)]
    comps = []
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diag:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    for i in range(h):
        for j in range(w):
            if seen[i][j]:
                continue
            col = g[i][j]
            st = [(i, j)]
            seen[i][j] = True
            cells = []
            while st:
                a, b = st.pop()
                cells.append((a, b))
                for da, db in steps:
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and not seen[x][y] and g[x][y] == col:
                        seen[x][y] = True
                        st.append((x, y))
            comps.append((col, cells))
    return comps

def blob(inp):
    """(color, cells of the largest 4-connected region)"""
    return max(components(inp), key=lambda c: len(c[1]))

def mirror_paint(inp, color, cells, mode, only_zero=False, shift=0, sources=None):
    h, w = len(inp), len(inp[0])
    o = copy(inp)
    for (i, j) in (cells if sources is None else sources):
        targets = []
        if mode == 'lr':
            targets = [(i, w - 1 - j + shift)]
        elif mode == 'tb':
            targets = [(h - 1 - i + shift, j)]
        elif mode == 'both':
            targets = [(i, w - 1 - j), (h - 1 - i, j), (h - 1 - i, w - 1 - j)]
        elif mode == 'diag':
            targets = [(j, i)]
        elif mode == 'rot180':
            targets = [(h - 1 - i, w - 1 - j)]
        for (x, y) in targets:
            if 0 <= x < h and 0 <= y < w:
                if only_zero and o[x][y] != 0:
                    continue
                o[x][y] = color
    return o

def all_of_color(inp):
    c, _ = blob(inp)
    return c, [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == c]

def tb_flip(inp, out):
    c, cells = all_of_color(inp)
    return mirror_paint(inp, c, cells, 'tb')

def both_axes(inp, out):
    c, cells = all_of_color(inp)
    return mirror_paint(inp, c, cells, 'both')

def diagonal(inp, out):
    c, cells = all_of_color(inp)
    return mirror_paint(inp, c, cells, 'diag')

def rot180(inp, out):
    c, cells = all_of_color(inp)
    return mirror_paint(inp, c, cells, 'rot180')

def commonest_color(inp, out):
    bc, _ = blob(inp)
    cnt = Counter(v for r in inp for v in r if v != bc)
    c = cnt.most_common(1)[0][0]
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == c]
    return mirror_paint(inp, c, cells, 'lr')

def left_to_right(inp, out):
    c, cells = all_of_color(inp)
    w = len(inp[0])
    return mirror_paint(inp, c, cells, 'lr', sources=[(i, j) for i, j in cells if i < len(inp) // 2])

def right_to_left(inp, out):
    c, cells = all_of_color(inp)
    w = len(inp[0])
    return mirror_paint(inp, c, cells, 'lr', sources=[(i, j) for i, j in cells if j >= w // 2])

def shifted_axis(inp, out):
    c, cells = all_of_color(inp)
    return mirror_paint(inp, c, cells, 'lr', shift=-1)

def every_colour_mirrors(inp, out):
    h, w = len(inp), len(inp[0])
    o = copy(inp)
    for i in range(h):
        for j in range(w):
            if inp[i][j] != 0:
                o[i][w - 1 - j] = inp[i][j]
    return o

def only_on_background(inp, out):
    c, cells = all_of_color(inp)
    return mirror_paint(inp, c, cells, 'lr', only_zero=True)

def move_not_copy(inp, out):
    c, cells = all_of_color(inp)
    o = copy(inp)
    for i, j in cells:
        o[i][j] = 0
    h, w = len(inp), len(inp[0])
    for i, j in cells:
        o[i][w - 1 - j] = c
    return o

def bounding_box(inp, out):
    c, cells = blob(inp)
    r0 = min(i for i, _ in cells); r1 = max(i for i, _ in cells)
    c0 = min(j for _, j in cells); c1 = max(j for _, j in cells)
    o = copy(inp)
    for i in range(r0, r1 + 1):
        for j in range(c0, c1 + 1):
            o[i][j] = c
    return o

def second_color_mirror(inp, out):
    # mirror the cells of the second-largest region's color instead
    comps = sorted(components(inp), key=lambda c: -len(c[1]))
    c0 = comps[0][0]
    for col, cells in comps:
        if col != c0:
            cc = col
            break
    cells = [(i, j) for i, r in enumerate(inp) for j, v in enumerate(r) if v == cc]
    return mirror_paint(inp, cc, cells, 'lr')

ALTERNATIVES = [
    ("mirror the blob colour top-to-bottom instead of left-to-right", tb_flip),
    ("mirror the blob colour across both axes", both_axes),
    ("mirror the blob colour across the main diagonal (transpose)", diagonal),
    ("mirror by 180-degree rotation about the centre", rot180),
    ("mirror the most common colour other than the blob colour", commonest_color),
    ("copy only top-half blob cells to their left-right mirror", left_to_right),
    ("copy only right-half blob cells onto the left half", right_to_left),
    ("mirror axis shifted by one column (c -> w-2-c)", shifted_axis),
    ("every non-zero cell is mirrored in its own colour, not just the blob colour", every_colour_mirrors),
    ("mirrored cells paint only onto background 0 cells, never overwrite", only_on_background),
    ("blob is moved to its mirror position, original cells cleared to 0", move_not_copy),
    ("fill the blob's bounding box with the blob colour", bounding_box),
]

if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/c35c1b4c.json')))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for name, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", name, e)
                g = None
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))
            if ok and g != p["output"]:
                n += 1
        print(n, name)
