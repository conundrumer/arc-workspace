import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _comps(inp, bg):
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == bg or (r, c) in seen:
                continue
            col = inp[r][c]
            stack = [(r, c)]
            seen.add((r, c))
            cells = []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da in (-1, 0, 1):
                    for db in (-1, 0, 1):
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and (x, y) not in seen and inp[x][y] == col:
                            seen.add((x, y))
                            stack.append((x, y))
            res.append((col, cells))
    return res


def _hollow(inp, bg, cells):
    rows = {}
    for r, c in cells:
        rows.setdefault(r, []).append(c)
    hol = set()
    for r, cs in rows.items():
        for c in range(min(cs), max(cs) + 1):
            if inp[r][c] == bg:
                hol.add((r, c))
    return hol


def _info(inp, out):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    pieces = [(r, c) for r in range(h) for c in range(w) if inp[r][c] != bg and out[r][c] == bg]
    pc = inp[pieces[0][0]][pieces[0][1]]
    hollows = []
    for col, cells in _comps(inp, bg):
        hol = _hollow(inp, bg, cells)
        if hol:
            hollows.append((col, cells, hol))
    match = [x for x in hollows if len(x[2]) == len(pieces)]
    other = [x for x in hollows if len(x[2]) != len(pieces)]
    return bg, pieces, pc, hollows, match, other


def _paint(grid, cells, v):
    g = [row[:] for row in grid]
    for r, c in cells:
        g[r][c] = v
    return g


def _base(inp, bg, pieces):
    return _paint(inp, pieces, bg)


def fill_all_hollows(inp, out):
    bg, pieces, pc, hollows, match, other = _info(inp, out)
    cells = [p for x in hollows for p in x[2]]
    return _paint(_base(inp, bg, pieces), cells, pc)


def fill_keep_pieces(inp, out):
    bg, pieces, pc, hollows, match, other = _info(inp, out)
    cells = [p for x in match for p in x[2]]
    return _paint(inp, cells, pc)


def remove_only(inp, out):
    bg, pieces, pc, hollows, match, other = _info(inp, out)
    return _base(inp, bg, pieces)


def fill_container_color(inp, out):
    bg, pieces, pc, hollows, match, other = _info(inp, out)
    g = _base(inp, bg, pieces)
    for col, cells, hol in match:
        g = _paint(g, hol, col)
    return g


def recolor_container(inp, out):
    bg, pieces, pc, hollows, match, other = _info(inp, out)
    g = _base(inp, bg, pieces)
    for col, cells, hol in match:
        g = _paint(g, list(hol) + cells, pc)
    return g


def fill_extra_row_above(inp, out):
    bg, pieces, pc, hollows, match, other = _info(inp, out)
    g = _base(inp, bg, pieces)
    for col, cells, hol in match:
        cs = set(hol) | {(r - 1, c) for r, c in hol if r > 0 and inp[r - 1][c] == bg}
        g = _paint(g, cs, pc)
    return g


def fill_bbox(inp, out):
    bg, pieces, pc, hollows, match, other = _info(inp, out)
    g = _base(inp, bg, pieces)
    for col, cells, hol in match:
        r0, r1 = min(r for r, c in cells), max(r for r, c in cells)
        c0, c1 = min(c for r, c in cells), max(c for r, c in cells)
        cs = [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if inp[r][c] == bg]
        g = _paint(g, cs, pc)
    return g


def fill_wrong_container(inp, out):
    bg, pieces, pc, hollows, match, other = _info(inp, out)
    cells = [p for x in other for p in x[2]]
    return _paint(_base(inp, bg, pieces), cells, pc)


def fill_shifted_up(inp, out):
    bg, pieces, pc, hollows, match, other = _info(inp, out)
    g = _base(inp, bg, pieces)
    for col, cells, hol in match:
        cs = [(r - 1, c) for r, c in hol if r > 0 and inp[r - 1][c] == bg]
        g = _paint(g, cs, pc)
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("fills every container's hollow regardless of size, removes the pieces", fill_all_hollows),
    ("fills the matching hollow but leaves the pieces in place", fill_keep_pieces),
    ("removes the pieces but fills no hollow", remove_only),
    ("fills the matching hollow with the container color", fill_container_color),
    ("fills the matching hollow and recolors the container to the piece color", recolor_container),
    ("fills the hollow plus the row above it (off by one)", fill_extra_row_above),
    ("fills every background cell in the container's bounding box", fill_bbox),
    ("fills the hollow of the container whose size does not match the pieces", fill_wrong_container),
    ("fills the hollow shifted one row up", fill_shifted_up),
    ("returns the input unchanged", unchanged),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/7acdf6d3.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error", f.__name__, e)
                continue
            if (g is not None and isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                    and len({len(r) for r in g}) == 1
                    and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                    and g != p["output"]):
                n += 1
        print(n, desc)
