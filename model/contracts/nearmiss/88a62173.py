"""Near-miss readings for 88a62173.

Rule: a 0 separator row and column cut the grid into four equal tiles.
Three tiles share one pattern; the output is the one tile that differs.
"""
import json
from collections import Counter
from pathlib import Path


def _tiles(inp):
    n = len(inp)
    k = (n - 1) // 2
    spans = {
        "TL": (0, 0), "TR": (0, k + 1),
        "BL": (k + 1, 0), "BR": (k + 1, k + 1),
    }
    tiles = {}
    for name, (r, c) in spans.items():
        tiles[name] = [row[c:c + k] for row in inp[r:r + k]]
    return tiles, k


def _key(t):
    return tuple(map(tuple, t))


def _odd_name(inp):
    tiles, _ = _tiles(inp)
    cnt = Counter(_key(t) for t in tiles.values())
    for name, t in tiles.items():
        if cnt[_key(t)] == 1:
            return name
    return None


def _odd(inp):
    return _tiles(inp)[0][_odd_name(inp)]


def _color(inp):
    return max(v for row in inp for v in row)


def _nz(t):
    return sum(1 for row in t for v in row if v)


def common_tile(inp, out):
    tiles, _ = _tiles(inp)
    cnt = Counter(_key(t) for t in tiles.values())
    key = cnt.most_common(1)[0][0]
    return [list(r) for r in key]


def top_left(inp, out):
    return _tiles(inp)[0]["TL"]


def bottom_right(inp, out):
    return _tiles(inp)[0]["BR"]


def flipped(inp, out):
    return [row[::-1] for row in _odd(inp)]


def rotated(inp, out):
    t = _odd(inp)
    k = len(t)
    return [[t[k - 1 - c][r] for c in range(k)] for r in range(k)]


def inverted(inp, out):
    col = _color(inp)
    return [[col if v == 0 else 0 for v in row] for row in out]


def diagonal_opposite(inp, out):
    opp = {"TL": "BR", "TR": "BL", "BL": "TR", "BR": "TL"}
    return _tiles(inp)[0][opp[_odd_name(inp)]]


def row_neighbour(inp, out):
    nb = {"TL": "TR", "TR": "TL", "BL": "BR", "BR": "BL"}
    return _tiles(inp)[0][nb[_odd_name(inp)]]


def union_of_tiles(inp, out):
    tiles, k = _tiles(inp)
    return [[int(any(t[r][c] for t in tiles.values())) * _color(inp)
             for c in range(k)] for r in range(k)]


def intersection_of_tiles(inp, out):
    tiles, k = _tiles(inp)
    return [[int(all(t[r][c] for t in tiles.values())) * _color(inp)
             for c in range(k)] for r in range(k)]


def fullest_tile(inp, out):
    tiles, _ = _tiles(inp)
    best = max(_nz(t) for t in tiles.values())
    names = [n for n, t in tiles.items() if _nz(t) == best]
    return tiles[names[0]]


def crop_with_separator(inp, out):
    """Crop one cell too large: the odd tile plus the adjoining separator row and column."""
    name = _odd_name(inp)
    k = len(out)
    r = 0 if name[0] == "T" else k
    c = 0 if name[1] == "L" else k
    return [row[c:c + k + 1] for row in inp[r:r + k + 1]]


def odd_tile_placed_in_grid(inp, out):
    """Keep the full grid, erase everything outside the odd tile."""
    name = _odd_name(inp)
    k = len(out)
    r0 = 0 if name[0] == "T" else k + 1
    c0 = 0 if name[1] == "L" else k + 1
    return [[inp[r][c] if r0 <= r < r0 + k and c0 <= c < c0 + k else 0
             for c in range(len(inp[0]))] for r in range(len(inp))]


ALTERNATIVES = [
    ("outputs the pattern shared by most tiles instead of the odd one", common_tile),
    ("always outputs the top-left tile", top_left),
    ("always outputs the bottom-right tile", bottom_right),
    ("outputs the odd tile mirrored left to right", flipped),
    ("outputs the odd tile rotated a quarter turn", rotated),
    ("outputs the odd tile with colored and empty cells swapped", inverted),
    ("outputs the tile diagonally opposite the odd tile", diagonal_opposite),
    ("outputs the tile next to the odd tile in the same row", row_neighbour),
    ("overlays all tiles and outputs their union", union_of_tiles),
    ("outputs the cells set in every tile", intersection_of_tiles),
    ("picks the tile with the most colored cells", fullest_tile),
    ("crops one cell too large, including a separator row and column", crop_with_separator),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/88a62173.json").read_text())
    pairs = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(pairs)} pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
