import json
from pathlib import Path


def _bg(inp):
    from collections import Counter
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _ink(inp):
    bg = _bg(inp)
    return [(r, c) for r, row in enumerate(inp) for c, v in enumerate(row) if v != bg]


def _build(inp, offsets, color=2, wrap=True, overwrite=False, ink=None, tiles=None):
    """Tile the input with marks placed at the given (dr, dc) offsets from ink."""
    n, m = len(inp), len(inp[0])
    bg = _bg(inp)
    ink = _ink(inp) if ink is None else ink
    tile = [row[:] for row in inp]
    for r, c in ink:
        for dr, dc in offsets:
            rr, cc = r + dr, c + dc
            if wrap:
                rr, cc = rr % n, cc % m
            elif not (0 <= rr < n and 0 <= cc < m):
                continue
            if tile[rr][cc] == bg or overwrite:
                if color == "ink":
                    tile[rr][cc] = inp[r][c]
                else:
                    tile[rr][cc] = color
    k = 3 if tiles is None else tiles
    return [tile[r % n] * k for r in range(n * k)]


def mark_up_right(inp, out):
    return _build(inp, [(-1, 1)])


def mark_down_left(inp, out):
    return _build(inp, [(1, -1)])


def mark_down_right(inp, out):
    return _build(inp, [(1, 1)])


def mark_up(inp, out):
    return _build(inp, [(-1, 0)])


def mark_left(inp, out):
    return _build(inp, [(0, -1)])


def mark_both_diagonals(inp, out):
    return _build(inp, [(-1, -1), (1, 1)])


def mark_no_wrap(inp, out):
    return _build(inp, [(-1, -1)], wrap=False)


def mark_overwrites_ink(inp, out):
    return _build(inp, [(-1, -1)], overwrite=True)


def mark_takes_ink_color(inp, out):
    return _build(inp, [(-1, -1)], color="ink")


def mark_two_steps(inp, out):
    return _build(inp, [(-2, -2)])


def mark_first_ink_only(inp, out):
    ink = _ink(inp)
    return _build(inp, [(-1, -1)], ink=ink[:1])


def tiles_equal_ink_count(inp, out):
    return _build(inp, [(-1, -1)], tiles=len(_ink(inp)))


def tiles_one_more(inp, out):
    return _build(inp, [(-1, -1)], tiles=4)


def no_marks(inp, out):
    return _build(inp, [])


ALTERNATIVES = [
    ("mark goes up-right of each ink cell instead of up-left", mark_up_right),
    ("mark goes down-left of each ink cell", mark_down_left),
    ("mark goes down-right of each ink cell", mark_down_right),
    ("mark goes straight above each ink cell", mark_up),
    ("mark goes straight left of each ink cell", mark_left),
    ("marks on both the up-left and down-right diagonals", mark_both_diagonals),
    ("mark position does not wrap around the tile edge", mark_no_wrap),
    ("mark is painted over ink cells it lands on", mark_overwrites_ink),
    ("mark takes the color of its ink cell instead of 2", mark_takes_ink_color),
    ("mark is two diagonal steps from the ink cell", mark_two_steps),
    ("only the first ink cell gets a mark", mark_first_ink_only),
    ("tile count per side is the number of ink cells", tiles_equal_ink_count),
    ("tile count per side is 4 instead of 3", tiles_one_more),
    ("tiling only, no marks", no_marks),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/310f3251.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                ok += 1
        print(ok, len(pairs), desc)
