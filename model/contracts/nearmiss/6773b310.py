import json
from pathlib import Path


def tile_counts(inp):
    """Marker (color 6) count in each 3x3 tile; tiles are separated by lines of 8."""
    n = (len(inp) + 1) // 4
    m = (len(inp[0]) + 1) // 4
    return [[sum(1 for r in range(4 * i, 4 * i + 3) for c in range(4 * j, 4 * j + 3) if inp[r][c] == 6)
             for j in range(m)] for i in range(n)]


def from_counts(inp, pred, on=1, off=0):
    return [[on if pred(v) else off for v in row] for row in tile_counts(inp)]


def top_two_rows_only(inp, out):
    # Counts markers only in the top two rows of each tile.
    res = []
    for i in range((len(inp) + 1) // 4):
        row = []
        for j in range((len(inp[0]) + 1) // 4):
            k = sum(1 for r in range(4 * i, 4 * i + 2) for c in range(4 * j, 4 * j + 3) if inp[r][c] == 6)
            row.append(1 if k == 2 else 0)
        res.append(row)
    return res


def at_least_one(inp, out):
    return from_counts(inp, lambda v: v >= 1)


def exactly_one(inp, out):
    return from_counts(inp, lambda v: v == 1)


def exactly_three(inp, out):
    return from_counts(inp, lambda v: v == 3)


def odd_count(inp, out):
    return from_counts(inp, lambda v: v % 2 == 1)


def inverted(inp, out):
    return [[1 - v for v in row] for row in out]


def wrong_mark_color(inp, out):
    return [[6 if v == 1 else v for v in row] for row in out]


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def flipped_horizontal(inp, out):
    return [row[::-1] for row in out]


def flipped_vertical(inp, out):
    return out[::-1]


def full_size_fill(inp, out):
    # Paints the whole 3x3 tile area instead of one output cell per tile.
    g = [row[:] for row in inp]
    for i, row in enumerate(out):
        for j, v in enumerate(row):
            if v == 1:
                for r in range(4 * i, 4 * i + 3):
                    for c in range(4 * j, 4 * j + 3):
                        g[r][c] = 1
    return g


def band_count(inp, out):
    # Counts markers over the whole row of tiles and marks every tile of a band with 2 markers.
    return [[1 if sum(row) == 2 else 0 for _ in row] for row in tile_counts(inp)]


def tile_4_stride(inp, out):
    # Tile cell includes the separator line, so the last tile is cut short in the count.
    res = []
    for i in range((len(inp) + 1) // 4):
        row = []
        for j in range((len(inp[0]) + 1) // 4):
            k = sum(1 for r in range(4 * i, 4 * i + 3) for c in range(4 * j + 1, 4 * j + 4)
                    if c < len(inp[0]) and inp[r][c] == 6)
            row.append(1 if k == 2 else 0)
        res.append(row)
    return res


def _diff(fn):
    def w(inp, out):
        g = fn(inp, out)
        if g is None or g == out:
            return None
        return g
    return w


ALTERNATIVES = [
    ("counts markers in the top two rows of each tile only", _diff(top_two_rows_only)),
    ("marks a tile with at least one marker", _diff(at_least_one)),
    ("marks a tile with exactly one marker", _diff(exactly_one)),
    ("marks a tile with an odd marker count", _diff(odd_count)),
    ("mark and background swapped in the output", _diff(inverted)),
    ("tiles marked with the marker color 6 instead of a new color", _diff(wrong_mark_color)),
    ("output transposed", _diff(transposed)),
    ("output mirrored left to right", _diff(flipped_horizontal)),
    ("output mirrored top to bottom", _diff(flipped_vertical)),
    ("paints the whole tile area of the input instead of one cell per tile", _diff(full_size_fill)),
    ("counts markers over the whole row of tiles instead of per tile", _diff(band_count)),
    ("tile window shifted one column right, overlapping the separator", _diff(tile_4_stride)),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/6773b310.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
