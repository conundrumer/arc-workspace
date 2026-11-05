"""Near-miss readings for ARC task 83302e8f.

Rule: wall lines divide the grid into tiles. A background cell inside a wall
line is a gap. A tile touching a gap is leaky (4); every other tile is sealed (3).
Gaps are leaky (4) and walls stay.
"""
import json
from pathlib import Path

SEALED, LEAKY = 3, 4


def _structure(inp):
    h, w = len(inp), len(inp[0])
    rdiv = [r for r in range(h) if sum(1 for v in inp[r] if v) * 2 > w]
    cdiv = [c for c in range(w) if sum(1 for r in range(h) if inp[r][c]) * 2 > h]
    gaps = [(r, c) for r in range(h) for c in range(w)
            if inp[r][c] == 0 and (r in rdiv or c in cdiv)]
    gapset = set(gaps)
    tile = {}
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 and (r, c) not in gapset:
                tile[(r, c)] = (sum(1 for x in rdiv if x < r), sum(1 for x in cdiv if x < c))
    return h, w, rdiv, cdiv, gapset, tile


def _nbrs(r, c):
    return [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]


def _build(inp, gaps_used, gap_color=LEAKY, leaky_tiles=None, cell_only=False):
    h, w, rdiv, cdiv, gapset, tile = _structure(inp)
    leaky = set()
    touching = set()
    for g in gaps_used:
        for n in _nbrs(*g):
            if n in tile:
                touching.add(n)
                leaky.add(tile[n])
    if leaky_tiles is not None:
        leaky = leaky_tiles(leaky, tile)
    res = [row[:] for row in inp]
    for (r, c), t in tile.items():
        if cell_only:
            res[r][c] = LEAKY if (r, c) in touching else SEALED
        else:
            res[r][c] = LEAKY if t in leaky else SEALED
    for (r, c) in gapset:
        res[r][c] = gap_color if (r, c) in gaps_used else 0
    return res


def _true_like(inp):
    return _build(inp, _structure(inp)[4])


def swap_colors(inp, out):
    return [[SEALED if v == LEAKY and inp[r][c] == 0 else LEAKY if v == SEALED and inp[r][c] == 0 else v
             for c, v in enumerate(row)] for r, row in enumerate(out)]


def all_leaky(inp, out):
    return [[LEAKY if inp[r][c] == 0 else v for c, v in enumerate(row)] for r, row in enumerate(out)]


def all_sealed(inp, out):
    return [[SEALED if inp[r][c] == 0 else v for c, v in enumerate(row)] for r, row in enumerate(out)]


def gaps_unfilled(inp, out):
    gapset = _structure(inp)[4]
    return [[0 if (r, c) in gapset else v for c, v in enumerate(row)] for r, row in enumerate(out)]


def gaps_sealed_color(inp, out):
    gapset = _structure(inp)[4]
    return [[SEALED if (r, c) in gapset else v for c, v in enumerate(row)] for r, row in enumerate(out)]


def only_cells_next_to_gap(inp, out):
    return _build(inp, _structure(inp)[4], cell_only=True)


def one_sided_leak(inp, out):
    h, w, rdiv, cdiv, gapset, tile = _structure(inp)
    leaky = set()
    for (r, c) in gapset:
        # horizontal divider gap leaks only upward, vertical divider gap only leftward
        n = (r - 1, c) if r in rdiv else (r, c - 1)
        if n in tile:
            leaky.add(tile[n])
    res = [row[:] for row in inp]
    for (r, c), t in tile.items():
        res[r][c] = LEAKY if t in leaky else SEALED
    for g in gapset:
        res[g[0]][g[1]] = LEAKY
    return res


def walls_erased(inp, out):
    return [[0 if inp[r][c] != 0 else v for c, v in enumerate(row)] for r, row in enumerate(out)]


def need_two_gap_cells(inp, out):
    h, w, rdiv, cdiv, gapset, tile = _structure(inp)
    count = {}
    for g in gapset:
        for n in _nbrs(*g):
            if n in tile:
                count[tile[n]] = count.get(tile[n], 0) + 1
    res = [row[:] for row in inp]
    for (r, c), t in tile.items():
        res[r][c] = LEAKY if count.get(t, 0) >= 2 else SEALED
    for g in gapset:
        res[g[0]][g[1]] = LEAKY
    return res


def border_gaps_ignored(inp, out):
    h, w, rdiv, cdiv, gapset, tile = _structure(inp)
    used = {(r, c) for (r, c) in gapset if 0 < r < h - 1 and 0 < c < w - 1}
    return _build(inp, used)


def leak_spreads_along_band(inp, out):
    h, w, rdiv, cdiv, gapset, tile = _structure(inp)

    def spread(leaky, tile):
        rows = {t[0] for t in leaky}
        return {t for t in tile.values() if t[0] in rows}
    return _build(inp, gapset, leaky_tiles=spread)


def vertical_gaps_only(inp, out):
    h, w, rdiv, cdiv, gapset, tile = _structure(inp)
    used = {(r, c) for (r, c) in gapset if c in cdiv and r not in rdiv}
    return _build(inp, used)


def horizontal_gaps_only(inp, out):
    h, w, rdiv, cdiv, gapset, tile = _structure(inp)
    used = {(r, c) for (r, c) in gapset if r in rdiv}
    return _build(inp, used)


ALTERNATIVES = [
    ("sealed and leaky colors swapped", swap_colors),
    ("every background cell treated as leaky", all_leaky),
    ("every background cell treated as sealed", all_sealed),
    ("gap cells in the wall lines left as background", gaps_unfilled),
    ("gap cells given the sealed color", gaps_sealed_color),
    ("only tile cells touching a gap are leaky, rest of the tile sealed", only_cells_next_to_gap),
    ("a gap leaks only the tile above or left of it", one_sided_leak),
    ("wall cells erased", walls_erased),
    ("a tile needs two touching gap cells to be leaky", need_two_gap_cells),
    ("gaps on the grid border ignored", border_gaps_ignored),
    ("a leak spreads to every tile in the same tile row", leak_spreads_along_band),
    ("only gaps in vertical walls count as leaks", vertical_gaps_only),
]


def _valid(g, out):
    if g is None or not g or not isinstance(g, list):
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
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/83302e8f.json"))
    pairs = task["train"]
    # sanity: the structural model reproduces the true output
    print("model matches truth on", sum(_true_like(p["input"]) == p["output"] for p in pairs), "of", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
