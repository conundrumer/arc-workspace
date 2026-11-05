"""Near-miss readings for ARC task 780d0b14 (tiles split by all-0 lines -> one ink color per tile)."""
import json
from collections import Counter
from pathlib import Path

DIV = 0


def _bands(flags):
    """Maximal runs of indices where flags is False."""
    runs, start = [], None
    for i, f in enumerate(flags + [True]):
        if not f and start is None:
            start = i
        elif f and start is not None:
            runs.append((start, i))
            start = None
    return runs


def _split(inp):
    h, w = len(inp), len(inp[0])
    rflags = [all(v == DIV for v in row) for row in inp]
    cflags = [all(inp[r][c] == DIV for r in range(h)) for c in range(w)]
    return _bands(rflags), _bands(cflags), rflags, cflags


def _tile_cells(inp, rb, cb):
    return [inp[r][c] for r in range(*rb) for c in range(*cb)]


def _ink(inp, rb, cb):
    cells = [v for v in _tile_cells(inp, rb, cb) if v != DIV]
    return Counter(cells).most_common(1)[0][0] if cells else DIV


def _tilegrid(inp):
    rbs, cbs, _, _ = _split(inp)
    return [[_ink(inp, rb, cb) for cb in cbs] for rb in rbs]


def _transpose(g):
    return [list(r) for r in zip(*g)]


def transposed(inp, out):
    return _transpose(out)


def mirror_cols(inp, out):
    return [r[::-1] for r in out]


def mirror_rows(inp, out):
    return out[::-1]


def corner_cell(inp, out):
    rbs, cbs, _, _ = _split(inp)
    return [[inp[rb[0]][cb[0]] for cb in cbs] for rb in rbs]


def only_row_dividers(inp, out):
    rbs, _, _, _ = _split(inp)
    w = len(inp[0])
    return [[_ink(inp, rb, (0, w))] for rb in rbs]


def only_col_dividers(inp, out):
    _, cbs, _, _ = _split(inp)
    h = len(inp)
    return [[_ink(inp, (0, h), cb) for cb in cbs]]


def dividers_as_cells(inp, out):
    rbs, cbs, _, _ = _split(inp)
    n, m = 2 * len(rbs) - 1, 2 * len(cbs) - 1
    g = [[DIV] * m for _ in range(n)]
    for i, rb in enumerate(rbs):
        for j, cb in enumerate(cbs):
            g[2 * i][2 * j] = _ink(inp, rb, cb)
    return g


def flattened(inp, out):
    return [[v for row in out for v in row]]


def global_ink(inp, out):
    cnt = Counter(v for row in out for v in row)
    col = cnt.most_common(1)[0][0]
    return [[col] * len(out[0]) for _ in out]


def drop_last_row(inp, out):
    return out[:-1]


def drop_last_col(inp, out):
    return [r[:-1] for r in out]


def rolled_rows(inp, out):
    return out[1:] + out[:1]


ALTERNATIVES = [
    ("Output transposed: tile rows and columns swapped", transposed),
    ("Output mirrored left-right", mirror_cols),
    ("Output mirrored top-bottom", mirror_rows),
    ("Tile colored by its top-left cell, so noise zeros win", corner_cell),
    ("Only horizontal divider lines split tiles; one column of tiles", only_row_dividers),
    ("Only vertical divider lines split tiles; one row of tiles", only_col_dividers),
    ("Divider lines kept as 0 cells between tile cells", dividers_as_cells),
    ("Tile colors listed in a single row in reading order", flattened),
    ("Every tile gets the single most common output color", global_ink),
    ("Last tile row dropped (off by one in tile count)", drop_last_row),
    ("Last tile column dropped (off by one in tile count)", drop_last_col),
    ("Tile rows cyclically shifted by one", rolled_rows),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/780d0b14.json").read_text())
    pairs = task["train"]
    # sanity: reference tile grid reproduces the true output
    assert all(_tilegrid(p["input"]) == p["output"] for p in pairs), "reference mismatch"
    for desc, fn in ALTERNATIVES:
        ok = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is None:
                continue
            good = (
                isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
                and len({len(r) for r in g}) == 1
                and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                and g != p["output"]
            )
            ok += good
        print(f"{ok}/{len(pairs)}  {desc}")
