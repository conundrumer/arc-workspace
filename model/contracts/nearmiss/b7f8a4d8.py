"""Near-miss rules for ARC task b7f8a4d8."""
import json
from collections import Counter
from pathlib import Path


def _info(inp):
    h, w = len(inp), len(inp[0])
    bg = Counter(inp[0]).most_common(1)[0][0]
    frame = set()
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v == bg:
                continue
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w and inp[rr][cc] == bg:
                    frame.add(v)
    interior = Counter(v for r in inp for v in r if v != bg and v not in frame)
    common = interior.most_common(1)[0][0]
    odd = [v for v in interior if v != common]
    return bg, frame, common, odd


def _bridge(inp, colors, horiz=True, vert=True, over=None, shift=0,
            edge=False, wide=False):
    """Fill the line between same-colored interior cells.

    over: None paints bg cells only; "all" paints every cell on the line
    except interior cells of the color set.
    """
    h, w = len(inp), len(inp[0])
    bg, frame, common, odd = _info(inp)
    g = [row[:] for row in inp]
    paint = []
    for col in colors:
        cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == col]
        if horiz:
            for r in sorted({r for r, _ in cells}):
                cs = [c for rr, c in cells if rr == r]
                if len(cs) >= 2 or (edge and cs):
                    lo, hi = (0, w - 1) if edge and len(cs) >= 2 else (min(cs), max(cs))
                    for c in range(lo, hi + 1):
                        paint.append((r + shift, c, col))
        if vert:
            for c in sorted({c for _, c in cells}):
                rs = [r for r, cc in cells if cc == c]
                if len(rs) >= 2 or (edge and rs):
                    lo, hi = (0, h - 1) if edge and len(rs) >= 2 else (min(rs), max(rs))
                    for r in range(lo, hi + 1):
                        paint.append((r, c + shift, col))
    if wide:
        extra = []
        for r, c, col in paint:
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                extra.append((r + dr, c + dc, col))
        paint = paint + extra
    for r, c, col in paint:
        if not (0 <= r < h and 0 <= c < w):
            continue
        if over == "all":
            if inp[r][c] in (bg,) or inp[r][c] in frame:
                g[r][c] = col
        elif inp[r][c] == bg:
            g[r][c] = col
    return g


def correct(inp):
    return _bridge(inp, _info(inp)[3])


def h_only(inp, out):
    return _bridge(inp, _info(inp)[3], vert=False)


def v_only(inp, out):
    return _bridge(inp, _info(inp)[3], horiz=False)


def overwrite_frames(inp, out):
    return _bridge(inp, _info(inp)[3], over="all")


def adjacent_only(inp, out):
    """Join only neighbouring odd tiles; no bridge passes over a tile between."""
    h, w = len(inp), len(inp[0])
    bg, frame, common, odd = _info(inp)
    interior = set(v for r in inp for v in r if v != bg and v not in frame)
    g = [row[:] for row in inp]
    for col in odd:
        cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == col]
        for r, c in cells:
            for r2, c2 in cells:
                if (r2, c2) <= (r, c):
                    continue
                if r == r2:
                    line = [(r, k) for k in range(c + 1, c2)]
                elif c == c2:
                    line = [(k, c) for k in range(r + 1, r2)]
                else:
                    continue
                if any(inp[a][b] in interior for a, b in line):
                    continue
                for a, b in line:
                    if inp[a][b] == bg:
                        g[a][b] = col
    return g


def common_color_paint(inp, out):
    bg, frame, common, odd = _info(inp)
    g = _bridge(inp, odd)
    return [[common if (g[r][c] != inp[r][c]) else g[r][c] for c in range(len(g[0]))]
            for r in range(len(g))]


def tile_wide(inp, out):
    return _bridge(inp, _info(inp)[3], wide=True)


def to_edge(inp, out):
    return _bridge(inp, _info(inp)[3], edge=True)


def bbox_fill(inp, out):
    h, w = len(inp), len(inp[0])
    bg, frame, common, odd = _info(inp)
    g = [row[:] for row in inp]
    for col in odd:
        cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == col]
        r0, r1 = min(r for r, _ in cells), max(r for r, _ in cells)
        c0, c1 = min(c for _, c in cells), max(c for _, c in cells)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if inp[r][c] == bg:
                    g[r][c] = col
    return g


def shifted_line(inp, out):
    return _bridge(inp, _info(inp)[3], shift=1)


def bridge_common(inp, out):
    bg, frame, common, odd = _info(inp)
    return _bridge(inp, [common])


def bridge_one_color(inp, out):
    """Bridge only the odd color with the smallest value."""
    odd = _info(inp)[3]
    if len(odd) < 2:
        return None
    return _bridge(inp, [min(odd)])


ALTERNATIVES = [
    ("bridge only along tile rows, never along tile columns", h_only),
    ("bridge only along tile columns, never along tile rows", v_only),
    ("bridge paints over frame cells too, not only the bg cells", overwrite_frames),
    ("join only neighbouring odd tiles; skip pairs with a tile between them", adjacent_only),
    ("bridge cells take the common interior color instead of the odd color", common_color_paint),
    ("bridge is as wide as a whole tile, frame rows included, not only the interior", tile_wide),
    ("bridge continues past the outermost odd tiles to the grid edge", to_edge),
    ("fill the whole bounding box of each odd color, not only the lines between tiles", bbox_fill),
    ("bridge line is offset by one cell from the tile interiors", shifted_line),
    ("bridge the common-color tiles instead of the odd ones", bridge_common),
    ("bridge only the odd color with the smallest color value", bridge_one_color),
]


def _valid(g, truth):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != truth


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/b7f8a4d8.json"))
    pairs = task["train"]
    print("pairs:", len(pairs))
    print("base reproduces truth:", [correct(p["input"]) == p["output"] for p in pairs])
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
