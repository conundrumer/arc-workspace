import json
from pathlib import Path


def _runs(seq):
    """Group consecutive equal items: list of [value, length]."""
    res = []
    for v in seq:
        if res and res[-1][0] == v:
            res[-1][1] += 1
        else:
            res.append([v, 1])
    return res


def _dedupe_rows(g):
    return [list(r) for r, _ in _runs([tuple(r) for r in g])]


def _transpose(g):
    return [list(c) for c in zip(*g)]


def _dedupe_cols(g):
    return _transpose(_dedupe_rows(_transpose(g)))


def rows_only(inp, out):
    return _dedupe_rows(inp)


def cols_only(inp, out):
    return _dedupe_cols(inp)


def transposed(inp, out):
    return _transpose(out)


def flip_h(inp, out):
    return [r[::-1] for r in out]


def flip_v(inp, out):
    return [list(r) for r in out[::-1]]


def drop_last_band(inp, out):
    g = [r[:-1] for r in out[:-1]]
    return g if g and g[0] else None


def drop_first_band(inp, out):
    g = [r[1:] for r in out[1:]]
    return g if g and g[0] else None


def subsample3(inp, out):
    return [r[::3] for r in inp[::3]]


def merge_last_row(inp, out):
    g = [list(r) for r in out]
    g[-1] = list(g[-2]) if len(g) > 1 else g[-1]
    return g


def cap_band_width(inp, out):
    def cap(seq):
        res = []
        for v, n in _runs(seq):
            res.extend([v] * min(n, 2))
        return res
    rows = [tuple(r) for r in inp]
    rr = []
    for v, n in _runs(rows):
        rr.extend([v] * min(n, 2))
    g = [list(r) for r in rr]
    return [cap(r) for r in g]


def band_per_cell_dedupe_all(inp, out):
    """Keep only the first cell of each band in each row, but keep all rows."""
    return [[v for v, _ in _runs(r)] for r in inp]


def pad_border(inp, out):
    """Compressed grid wrongly kept the band lengths of the first band."""
    g = [list(r) for r in out]
    g[0] = [g[0][0]] + g[0]
    return [r if len(r) == len(g[0]) else [r[0]] + r for r in g]


ALTERNATIVES = [
    ("Collapse only repeated rows; leave columns uncompressed", rows_only),
    ("Collapse only repeated columns; leave rows uncompressed", cols_only),
    ("Right band colors, but rows and columns swapped (transposed)", transposed),
    ("Right band colors, but mirrored left to right", flip_h),
    ("Right band colors, but mirrored top to bottom", flip_v),
    ("Off by one: last band in each direction dropped", drop_last_band),
    ("Off by one: first band in each direction dropped", drop_first_band),
    ("Sample every third input cell instead of collapsing bands", subsample3),
    ("Last row band merged into the row band before it", merge_last_row),
    ("Each band kept as at most two cells wide or tall", cap_band_width),
    ("Each row collapsed to its bands but all input rows kept", band_per_cell_dedupe_all),
    ("First column band duplicated as an extra band", pad_border),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/e1baa8a4.json'))
    pairs = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
