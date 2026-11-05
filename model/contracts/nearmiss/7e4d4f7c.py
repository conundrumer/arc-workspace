import json
from collections import Counter
from pathlib import Path

MARK = 6


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _rows(g):
    return [list(r) for r in g]


def _mark_row(inp, rule):
    bg = _bg(inp)
    return [MARK if rule(v, bg, i) else inp[2][i] for i, v in enumerate(inp[0])]


def too_short(inp, out):
    return _rows(out[:2])


def too_tall(inp, out):
    return _rows(out) + [list(inp[3])]


def header_copy(inp, out):
    g = _rows(out)
    g[2] = list(inp[0])
    return g


def inverted_columns(inp, out):
    g = _rows(out)
    g[2] = _mark_row(inp, lambda v, bg, i: v == bg)
    return g


def tail_unmarked(inp, out):
    g = _rows(out)
    g[2] = list(inp[2])
    return g


def tail_all_marker(inp, out):
    g = _rows(out)
    g[2] = [MARK] * len(g[2])
    return g


def shifted_one_column(inp, out):
    g = _rows(out)
    row = g[2]
    g[2] = row[1:] + row[:1]
    return g


def bg_from_corner(inp, out):
    g = _rows(out)
    bg = inp[0][0]
    g[2] = _mark_row(inp, lambda v, b, i: v != bg)
    return g


def full_size_last_row(inp, out):
    g = _rows(inp)
    g[-1] = _mark_row(inp, lambda v, bg, i: v != bg)
    return g


def transposed(inp, out):
    return [list(c) for c in zip(*out)]


def marker_in_header_row(inp, out):
    g = _rows(out)
    g[0] = _mark_row(inp, lambda v, bg, i: v != bg)
    g[2] = list(inp[2])
    return g


def rows_swapped(inp, out):
    g = _rows(out)
    g[1], g[2] = g[2], g[1]
    return g


ALTERNATIVES = [
    ("output only the header and the stub row (height 2)", too_short),
    ("output four rows, one stub row too many", too_tall),
    ("tail row copies the header instead of marking it", header_copy),
    ("mark the background columns instead of the non-background ones", inverted_columns),
    ("leave the tail row unmarked", tail_unmarked),
    ("fill the whole tail row with the marker color", tail_all_marker),
    ("tail row marks are shifted one column left", shifted_one_column),
    ("background taken as the header's first cell", bg_from_corner),
    ("keep the input size and mark only its last row", full_size_last_row),
    ("output is transposed", transposed),
    ("mark the header row in place, leave the tail row as in the input", marker_in_header_row),
    ("stub row and tail row swapped", rows_swapped),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/7e4d4f7c.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
