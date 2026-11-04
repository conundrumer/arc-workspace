from pathlib import Path
import json
from collections import Counter

ORTH = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def block(inp):
    cells = [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v]
    r0 = min(r for r, c in cells); r1 = max(r for r, c in cells)
    c0 = min(c for r, c in cells); c1 = max(c for r, c in cells)
    return r0, r1, c0, c1


def cast(inp, dirs, color_of=None, start=1, maxlen=None, trim_end=0, flip=False):
    """Draw rays from the 8 neighbours of the block center, starting from the input."""
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    r0, r1, c0, c1 = block(inp)
    cr, cc = (r0 + r1) // 2, (c0 + c1) // 2
    for dr, dc in dirs:
        sr, sc = (-dr, -dc) if flip else (dr, dc)
        col = inp[cr + sr][cc + sc]
        if color_of:
            col = color_of(inp, dr, dc, col)
        if col == 0:
            continue
        cells = []
        r, c = cr + dr * 2, cc + dc * 2
        while 0 <= r < h and 0 <= c < w:
            cells.append((r, c))
            r += dr; c += dc
        cells = cells[start - 1:]
        if trim_end:
            cells = cells[:-trim_end]
        if maxlen is not None:
            cells = cells[:maxlen]
        for r, c in cells:
            g[r][c] = col
    return g


ALL = ORTH + DIAG


def orth_only(inp, out):
    return cast(inp, ORTH)


def diag_only(inp, out):
    return cast(inp, DIAG)


def center_color(inp, out):
    r0, r1, c0, c1 = block(inp)
    cc = inp[(r0 + r1) // 2][(c0 + c1) // 2]
    return cast(inp, ALL, color_of=lambda i, dr, dc, col: cc if col else 0)


def short_rays(inp, out):
    return cast(inp, ALL, maxlen=3)


def diag_takes_orth_color(inp, out):
    r0, r1, c0, c1 = block(inp)
    cr, cc = (r0 + r1) // 2, (c0 + c1) // 2
    def f(i, dr, dc, col):
        if dr and dc:
            return i[cr + dr][cc]
        return col
    return cast(inp, ALL, color_of=f)


def opposite_color(inp, out):
    return cast(inp, ALL, flip=True)


def skip_first_cell(inp, out):
    return cast(inp, ALL, start=2)


def dominant_block_color(inp, out):
    r0, r1, c0, c1 = block(inp)
    cnt = Counter(inp[r][c] for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if inp[r][c])
    top = cnt.most_common(1)[0][0]
    return cast(inp, ALL, color_of=lambda i, dr, dc, col: top if col else 0)


def up_left_only(inp, out):
    return cast(inp, [d for d in ALL if d[0] < 0 or d[1] < 0])


def one_short_at_edge(inp, out):
    return cast(inp, ALL, trim_end=1)


def down_right_only(inp, out):
    return cast(inp, [d for d in ALL if d[0] > 0 or d[1] > 0])


ALTERNATIVES = [
    ("only the four orthogonal neighbours cast rays", orth_only),
    ("only the four diagonal neighbours cast rays", diag_only),
    ("every ray takes the center cell's color", center_color),
    ("rays stop after 3 cells instead of reaching the grid edge", short_rays),
    ("each diagonal ray takes the color of the vertical neighbour next to it", diag_takes_orth_color),
    ("each ray has the color of the neighbour on the opposite side", opposite_color),
    ("rays start one cell too far out, leaving a gap after the block", skip_first_cell),
    ("every ray takes the most common block color", dominant_block_color),
    ("only neighbours facing up or left cast rays", up_left_only),
    ("rays stop one cell before the grid edge", one_short_at_edge),
    ("only neighbours facing down or right cast rays", down_right_only),
]


def valid(g, out):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r) and g != out)


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/1d398264.json')))
    pairs = t["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", e)
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, desc)
