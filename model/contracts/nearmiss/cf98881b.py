import json
from pathlib import Path


def tiles(inp, shift=0):
    """Split the input into three 4-wide tiles at columns 0, 5, 10."""
    return [[row[c + shift:c + shift + 4] + [0] * max(0, 4 - len(row[c + shift:c + shift + 4]))
             for row in inp] for c in (0, 5, 10)]


def overlay(ts, order):
    """order lists tile indexes from highest to lowest priority."""
    h, w = len(ts[0]), len(ts[0][0])
    res = [[0] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            for i in order:
                if ts[i][r][c] != 0:
                    res[r][c] = ts[i][r][c]
                    break
    return res


def right_on_top(inp, out):
    return overlay(tiles(inp), [2, 1, 0])


def middle_on_top(inp, out):
    return overlay(tiles(inp), [1, 0, 2])


def right_over_middle(inp, out):
    return overlay(tiles(inp), [0, 2, 1])


def left_only(inp, out):
    return tiles(inp)[0]


def ignore_right(inp, out):
    return overlay(tiles(inp), [0, 1])


def overlaps_blank(inp, out):
    ts = tiles(inp)
    res = overlay(ts, [0, 1, 2])
    for r in range(4):
        for c in range(4):
            if sum(1 for t in ts if t[r][c] != 0) > 1:
                res[r][c] = 0
    return res


def middle_shifted(inp, out):
    ts = tiles(inp)
    ts[1] = tiles(inp, 1)[1]
    return overlay(ts, [0, 1, 2])


def right_mirrored(inp, out):
    ts = tiles(inp)
    ts[2] = [row[::-1] for row in ts[2]]
    return overlay(ts, [0, 1, 2])


def background_is_separator(inp, out):
    res = overlay(tiles(inp), [0, 1, 2])
    return [[2 if v == 0 else v for v in row] for row in res]


def rows_flipped(inp, out):
    return [row[:] for row in out[::-1]]


def whole_input(inp, out):
    return [row[:] for row in inp]


def stacked_vertically(inp, out):
    # tiles read as stacked in a column: output is the three tiles one under another
    ts = tiles(inp)
    return [row[:] for t in ts for row in t]


def _none_if_same(fn):
    def wrapped(inp, out):
        g = fn(inp, out)
        return None if g == out else g
    return wrapped


ALTERNATIVES = [
    ("right tile has top priority (1 over 9 over 4)", right_on_top),
    ("middle tile has top priority (9 over 4 over 1)", middle_on_top),
    ("right tile outranks middle tile (4 over 1 over 9)", right_over_middle),
    ("output is only the left tile", left_only),
    ("right tile ignored in the overlay", ignore_right),
    ("cells where tiles overlap are left empty", overlaps_blank),
    ("middle tile read one column to the right", middle_shifted),
    ("right tile mirrored left-right before overlay", right_mirrored),
    ("empty cells take the separator color 2", background_is_separator),
    ("correct overlay flipped top-to-bottom", rows_flipped),
    ("tiles stacked vertically instead of overlaid", stacked_vertically),
    ("input returned unchanged", whole_input),
]
ALTERNATIVES = [(d, _none_if_same(f)) for d, f in ALTERNATIVES]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/cf98881b.json').read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
