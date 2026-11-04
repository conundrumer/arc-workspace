from pathlib import Path
import json


def tiles(inp, n=4):
    h = len(inp) // n
    return [inp[i * h:(i + 1) * h] for i in range(n)]


def overlay(ts, order):
    """order: tile indices, foremost first."""
    h, w = len(ts[0]), len(ts[0][0])
    res = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            for i in order:
                if ts[i][r][c] != 0:
                    res[r][c] = ts[i][r][c]
                    break
    return res


def infer_order(inp, out):
    """Tile order, foremost first, read off the true output."""
    ts = tiles(inp)
    n = len(ts)
    wins = [0] * n
    for r in range(len(out)):
        for c in range(len(out[0])):
            ink = [i for i in range(n) if ts[i][r][c] != 0]
            for i in ink:
                if ts[i][r][c] == out[r][c]:
                    wins[i] += len(ink) - 1
    return sorted(range(n), key=lambda i: -wins[i])


def first_wins(inp, out):
    return overlay(tiles(inp), [0, 1, 2, 3])


def last_wins(inp, out):
    return overlay(tiles(inp), [3, 2, 1, 0])


def high_color_wins(inp, out):
    ts = tiles(inp)
    order = sorted(range(4), key=lambda i: -max(max(r) for r in ts[i]))
    return overlay(ts, order)


def low_color_wins(inp, out):
    ts = tiles(inp)
    order = sorted(range(4), key=lambda i: max(max(r) for r in ts[i]))
    return overlay(ts, order)


def most_ink_wins(inp, out):
    ts = tiles(inp)
    order = sorted(range(4), key=lambda i: -sum(v != 0 for r in ts[i] for v in r))
    return overlay(ts, order)


def least_ink_wins(inp, out):
    ts = tiles(inp)
    order = sorted(range(4), key=lambda i: sum(v != 0 for r in ts[i] for v in r))
    return overlay(ts, order)


def first_tile_only(inp, out):
    return [row[:] for row in tiles(inp)[0]]


def top_two_swapped(inp, out):
    order = infer_order(inp, out)
    order[0], order[1] = order[1], order[0]
    return overlay(tiles(inp), order)


def last_two_swapped(inp, out):
    order = infer_order(inp, out)
    order[-1], order[-2] = order[-2], order[-1]
    return overlay(tiles(inp), order)


def drop_winning_tile_rank_two(inp, out):
    # the second-ranked tile is treated as not inking at all
    order = infer_order(inp, out)
    return overlay(tiles(inp), [order[0], order[2], order[3]])


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def flipped_vertical(inp, out):
    return [row[:] for row in out[::-1]]


def crop_one_row_short(inp, out):
    return [row[:] for row in out[:-1]]


def columns_as_tiles(inp, out):
    # splits the width into three strips and overlays them, first wins
    w = len(inp[0]) // 3
    strips = [[row[i * w:(i + 1) * w] for row in inp] for i in range(3)]
    h = len(inp)
    res = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            for s in strips:
                if s[r][c] != 0:
                    res[r][c] = s[r][c]
                    break
    return res


ALTERNATIVES = [
    ("top tile always wins overlaps (fixed top-to-bottom order)", first_wins),
    ("bottom tile always wins overlaps (fixed bottom-to-top order)", last_wins),
    ("tile with the highest color value wins overlaps", high_color_wins),
    ("tile with the lowest color value wins overlaps", low_color_wins),
    ("tile with the most ink wins overlaps", most_ink_wins),
    ("output is just the first tile, no overlay", first_tile_only),
    ("two foremost tiles swapped in precedence", top_two_swapped),
    ("second-ranked tile is left out of the overlay", drop_winning_tile_rank_two),
    ("output transposed", transposed),
    ("output flipped top to bottom", flipped_vertical),
    ("output one row too short", crop_one_row_short),
    ("tiles cut along the wrong axis (three column strips)", columns_as_tiles),
]


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/3d31c5b3.json')))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error", desc, e)
                g = None
            if g is None:
                continue
            ok = (
                isinstance(g, list) and len(g) > 0
                and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
                and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
                and g != p["output"]
            )
            n += ok
        print(n, desc)
