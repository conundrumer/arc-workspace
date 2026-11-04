from pathlib import Path
import json
from collections import Counter


def _w(out):
    return len(out[0])


def half_width(inp, out):
    w = len(inp[0])
    return [r[: w // 2] for r in inp]


def tile_one_too_wide(inp, out):
    return [r[: _w(out) + 1] for r in inp]


def tile_one_too_narrow(inp, out):
    return [r[: _w(out) - 1] for r in out]


def crop_offset_by_one(inp, out):
    w = _w(out)
    return [r[1 : w + 1] for r in inp]


def mirrored_tile(inp, out):
    return [r[::-1] for r in out]


def flipped_vertically(inp, out):
    return [list(r) for r in out[::-1]]


def unchanged_input(inp, out):
    return [list(r) for r in inp]


def tile_twice(inp, out):
    return [r + r for r in out]


def split_vertically(inp, out):
    h = len(inp)
    return [list(r) for r in inp[: max(1, h // 2)]]


def commonest_color_erased(inp, out):
    c = Counter(v for r in out for v in r).most_common(1)[0][0]
    return [[0 if v == c else v for v in r] for r in out]


def last_tile_columns_dropped_first_col_kept(inp, out):
    w = _w(out)
    return [r[w:2 * w][::-1] for r in inp]


ALTERNATIVES = [
    ("tile is half the input width", half_width),
    ("tile width is one column too wide", tile_one_too_wide),
    ("tile width is one column too narrow", tile_one_too_narrow),
    ("tile crop starts one column late", crop_offset_by_one),
    ("tile is mirrored left to right", mirrored_tile),
    ("tile is flipped top to bottom", flipped_vertically),
    ("rule not applied: input returned", unchanged_input),
    ("tile count off: tile repeated twice", tile_twice),
    ("tile axis wrong: input split into top half", split_vertically),
    ("most common color of tile erased to 0", commonest_color_erased),
    ("second tile taken and mirrored", last_tile_columns_dropped_first_col_kept),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    t = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/2dee498d.json')))
    pairs = t["train"]
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("ERR", desc, e)
                g = None
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
