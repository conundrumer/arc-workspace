"""Near-miss readings for ARC task 97a05b5b.

Rule: the largest shape (the board) has holes. Smaller pieces lie around it.
Each piece is turned so that its board-colored cells fit one hole region.
The piece's other cells land on the board. The output is the board's
bounding box with every piece painted in.
"""
import json
from pathlib import Path


def _board(inp):
    """Return (bbox r0, r1, c0, c1, board color) of the largest 8-connected non-zero shape."""
    h, w = len(inp), len(inp[0])
    seen = set()
    best = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] and (r, c) not in seen:
                comp = []
                stack = [(r, c)]
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    comp.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if (0 <= ny < h and 0 <= nx < w and inp[ny][nx]
                                    and (ny, nx) not in seen):
                                seen.add((ny, nx))
                                stack.append((ny, nx))
                if len(comp) > len(best):
                    best = comp
    rs = [p[0] for p in best]
    cs = [p[1] for p in best]
    counts = {}
    for y, x in best:
        counts[inp[y][x]] = counts.get(inp[y][x], 0) + 1
    color = max(counts, key=counts.get)
    return min(rs), max(rs), min(cs), max(cs), color


def _crop(g, r0, r1, c0, c1):
    return [row[c0:c1 + 1] for row in g[r0:r1 + 1]]


def _changed(inp, out):
    r0, r1, c0, c1, _ = _board(inp)
    base = _crop(inp, r0, r1, c0, c1)
    if len(base) != len(out) or len(base[0]) != len(out[0]):
        return base, set()
    ch = {(r, c) for r in range(len(out)) for c in range(len(out[0]))
          if out[r][c] != base[r][c]}
    return base, ch


def _components(cells):
    cells = set(cells)
    comps = []
    while cells:
        start = cells.pop()
        comp = [start]
        stack = [start]
        while stack:
            y, x = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    n = (y + dy, x + dx)
                    if n in cells:
                        cells.remove(n)
                        comp.append(n)
                        stack.append(n)
        comps.append(comp)
    return comps


def unfilled(inp, out):
    r0, r1, c0, c1, _ = _board(inp)
    return _crop(inp, r0, r1, c0, c1)


def unchanged(inp, out):
    return [row[:] for row in inp]


def pad_one(inp, out):
    w = len(out[0])
    return [[0] * (w + 2)] + [[0] + row[:] + [0] for row in out] + [[0] * (w + 2)]


def trim_last(inp, out):
    return [row[:-1] for row in out[:-1]]


def holes_board_color(inp, out):
    r0, r1, c0, c1, color = _board(inp)
    base = _crop(inp, r0, r1, c0, c1)
    return [[color if v == 0 else v for v in row] for row in base]


def shift_down(inp, out):
    base, ch = _changed(inp, out)
    g = [row[:] for row in base]
    h = len(g)
    for r, c in ch:
        if r + 1 < h:
            g[r + 1][c] = out[r][c]
    return g


def first_piece_only(inp, out):
    base, ch = _changed(inp, out)
    comps = _components(ch)
    if len(comps) < 2:
        return None
    first = min(comps, key=lambda comp: min(comp))
    g = [row[:] for row in base]
    for r, c in first:
        g[r][c] = out[r][c]
    return g


def mirrored_patches(inp, out):
    base, ch = _changed(inp, out)
    g = [row[:] for row in base]
    for comp in _components(ch):
        lo = min(c for _, c in comp)
        hi = max(c for _, c in comp)
        for r, c in comp:
            g[r][lo + hi - c] = out[r][c]
    return g


def fill_in_place(inp, out):
    r0, r1, c0, c1, _ = _board(inp)
    g = [row[:] for row in inp]
    for r in range(len(out)):
        for c in range(len(out[0])):
            g[r0 + r][c0 + c] = out[r][c]
    return g


def all_nonzero_crop(inp, out):
    rows = [r for r, row in enumerate(inp) if any(row)]
    cols = [c for c in range(len(inp[0])) if any(row[c] for row in inp)]
    return _crop(inp, min(rows), max(rows), min(cols), max(cols))


def window_shifted(inp, out):
    r0, r1, c0, c1, _ = _board(inp)
    g = [row[:] for row in inp]
    for r in range(len(out)):
        for c in range(len(out[0])):
            g[r0 + r][c0 + c] = out[r][c]
    h, w = len(g), len(g[0])
    return [[g[r][c] if r < h and c < w else 0
             for c in range(c0 + 1, c1 + 2)] for r in range(r0 + 1, r1 + 2)]


ALTERNATIVES = [
    ("board cropped, holes left empty (pieces never placed)", unfilled),
    ("input returned unchanged", unchanged),
    ("output has an extra 1-cell background margin around the board", pad_one),
    ("crop is one row and one column short (last row and column dropped)", trim_last),
    ("holes filled with the board color only; the pieces' other colors are dropped", holes_board_color),
    ("every placed piece sits one row too low", shift_down),
    ("only the first piece is placed", first_piece_only),
    ("each placed piece is mirrored left to right", mirrored_patches),
    ("pieces placed but no crop: whole input kept with the board painted", fill_in_place),
    ("crop is the bounding box of all non-background cells, pieces unplaced", all_nonzero_crop),
    ("crop window offset one row and one column from the board", window_shifted),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/97a05b5b.json"))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
