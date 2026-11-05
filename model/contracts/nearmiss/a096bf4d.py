"""Near-miss readings for ARC task a096bf4d."""
import json
from collections import Counter
from pathlib import Path


def _runs(flags):
    runs, start = [], None
    for i, f in enumerate(flags + [True]):
        if not f and start is None:
            start = i
        elif f and start is not None:
            runs.append((start, i))
            start = None
    return runs


def _parse(g):
    """Return (row ranges, col ranges, tiles[r][c] as grids, common tile)."""
    s = g[0][0]
    rr = _runs([all(v == s for v in row) for row in g])
    cc = _runs([all(row[x] == s for row in g) for x in range(len(g[0]))])
    tiles = [[[row[c0:c1] for row in g[r0:r1]] for (c0, c1) in cc] for (r0, r1) in rr]
    return rr, cc, tiles


def _common(tiles, ref=None):
    h, w = len(tiles[0][0]), len(tiles[0][0][0])
    if ref is not None:
        return [row[:] for row in tiles[ref[0]][ref[1]]]
    com = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            cnt = Counter(t[y][x] for tr in tiles for t in tr)
            best = max(cnt.values())
            com[y][x] = min(c for c, n in cnt.items() if n == best)
    return com


def _marks(tiles, com):
    out = []
    for r, tr in enumerate(tiles):
        for c, t in enumerate(tr):
            for y, row in enumerate(t):
                for x, v in enumerate(row):
                    if v != com[y][x]:
                        out.append((r, c, y, x, v))
    return out


def _put(g, rr, cc, r, c, y, x, v):
    g[rr[r][0] + y][cc[c][0] + x] = v


def _fill(inp, rows=True, cols=True, widen=0, whole=False, key_pos=True, ref=None, to_edge=False, short=0, key_color=True):
    g = [row[:] for row in inp]
    rr, cc, tiles = _parse(inp)
    com = _common(tiles, ref)
    marks = _marks(tiles, com)
    nR, nC = len(rr), len(cc)
    groups = {}
    for (r, c, y, x, v) in marks:
        kv = v if key_color else None
        if rows:
            groups.setdefault(("r", r, kv, (y, x) if key_pos else None), []).append((r, c, y, x, v))
        if cols:
            groups.setdefault(("c", c, kv, (y, x) if key_pos else None), []).append((r, c, y, x, v))
    for (kind, idx, v, _), ms in groups.items():
        if len(ms) < 2:
            continue
        if kind == "r":
            lo, hi = min(m[1] for m in ms), max(m[1] for m in ms)
            if to_edge:
                hi = nC - 1
            hi -= short
            lo, hi = max(0, lo - widen), min(nC - 1, hi + widen)
            for (_, c0, y, x, v0) in ms:
                for c in range(lo, hi + 1):
                    _put(g, rr, cc, idx, c, y, x, ms[0][4])
        else:
            lo, hi = min(m[0] for m in ms), max(m[0] for m in ms)
            if to_edge:
                hi = nR - 1
            hi -= short
            lo, hi = max(0, lo - widen), min(nR - 1, hi + widen)
            for (_, _, y, x, v0) in ms:
                for r in range(lo, hi + 1):
                    _put(g, rr, cc, r, idx, y, x, ms[0][4])
    return g


def rows_only(inp, out):
    return _fill(inp, cols=False)


def cols_only(inp, out):
    return _fill(inp, rows=False)


def whole_line(inp, out):
    return _fill(inp, to_edge=True)


def stop_one_short(inp, out):
    return _fill(inp, short=2)


def step_one(inp, out):
    """Each mark paints only the tile next to it, toward its partner."""
    g = [row[:] for row in inp]
    rr, cc, tiles = _parse(inp)
    com = _common(tiles)
    marks = _marks(tiles, com)
    for (r, c, y, x, v) in marks:
        for (r2, c2, y2, x2, v2) in marks:
            if (y, x, v) == (y2, x2, v2) and (r, c) < (r2, c2):
                if r == r2:
                    _put(g, rr, cc, r, c + (1 if c2 > c else -1), y, x, v)
                elif c == c2:
                    _put(g, rr, cc, r + (1 if r2 > r else -1), c, y, x, v)
    return g


def ref_first_tile(inp, out):
    return _fill(inp, ref=(0, 0))


def erase_marks(inp, out):
    g = [row[:] for row in inp]
    rr, cc, tiles = _parse(inp)
    com = _common(tiles)
    for (r, c, y, x, v) in _marks(tiles, com):
        _put(g, rr, cc, r, c, y, x, com[y][x])
    return g


def copy_whole_tile(inp, out):
    g = [row[:] for row in inp]
    rr, cc, tiles = _parse(inp)
    com = _common(tiles)
    marks = _marks(tiles, com)
    groups = {}
    for (r, c, y, x, v) in marks:
        groups.setdefault(("r", r, v, y, x), []).append((r, c))
        groups.setdefault(("c", c, v, y, x), []).append((r, c))
    for (kind, idx, v, y, x), ms in groups.items():
        if len(ms) < 2:
            continue
        for (sr, sc) in ms[:1]:
            src = tiles[sr][sc]
            if kind == "r":
                targets = [(idx, c) for c in range(min(m[1] for m in ms), max(m[1] for m in ms) + 1)]
            else:
                targets = [(r, idx) for r in range(min(m[0] for m in ms), max(m[0] for m in ms) + 1)]
            for (tr, tc) in targets:
                for yy, row in enumerate(src):
                    for xx, val in enumerate(row):
                        _put(g, rr, cc, tr, tc, yy, xx, val)
    return g


def global_position(inp, out):
    g = [row[:] for row in inp]
    rr, cc, tiles = _parse(inp)
    com = _common(tiles)
    marks = _marks(tiles, com)
    seen = {}
    for (r, c, y, x, v) in marks:
        seen.setdefault((y, x, v), 0)
        seen[(y, x, v)] += 1
    for (y, x, v), n in seen.items():
        if n >= 2:
            for r in range(len(rr)):
                for c in range(len(cc)):
                    _put(g, rr, cc, r, c, y, x, v)
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


def common_tile_only(inp, out):
    rr, cc, tiles = _parse(inp)
    return _common(tiles)


def fill_with_common(inp, out):
    """Span fill, but the in-between tiles get the common color instead of the mark color."""
    g = [row[:] for row in out]
    rr, cc, tiles = _parse(inp)
    com = _common(tiles)
    for (r, c, y, x, v) in _marks(tiles, com):
        _put(g, rr, cc, r, c, y, x, com[y][x])
    ins = {(r, c, y, x) for (r, c, y, x, v) in _marks(tiles, com)}
    for r in range(len(rr)):
        for c in range(len(cc)):
            for y in range(len(com)):
                for x in range(len(com[0])):
                    if (r, c, y, x) not in ins and out[rr[r][0] + y][cc[c][0] + x] != com[y][x]:
                        _put(g, rr, cc, r, c, y, x, com[y][x])
    return g


ALTERNATIVES = [
    ("fill spans only along tile rows, ignoring tile columns", rows_only),
    ("fill spans only along tile columns, ignoring tile rows", cols_only),
    ("span runs from the first mark to the grid edge, not just to the last mark", whole_line),
    ("span leaves the tile just before the last mark unfilled", stop_one_short),
    ("the first mark of a pair paints only the one tile next to it, toward its partner", step_one),
    ("common tile taken as the top-left tile instead of the per-position majority", ref_first_tile),
    ("marks are removed (reset to common tile) and nothing is filled", erase_marks),
    ("the whole marked tile is copied into the tiles between, not just the mark cell", copy_whole_tile),
    ("a repeated mark paints its position in every tile of the grid", global_position),
    ("output is only the common tile", common_tile_only),
    ("spans are cleared to the common color: marks and between-cells all reset", fill_with_common),
    ("output equals the input unchanged", unchanged),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/a096bf4d.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
