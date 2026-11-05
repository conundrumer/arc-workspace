"""Near-miss readings for ARC task 782b5218.

Rule: the rarest color forms a barrier. Every non-barrier cell below a barrier
cell in its column takes the fill color (the color that is neither 0 nor the barrier). Every other
non-barrier cell becomes 0 (background). Barrier cells stay.
"""
import json
from collections import Counter
from pathlib import Path


def _colors(inp):
    cnt = Counter(v for r in inp for v in r)
    bg = 0
    bar = min(cnt, key=lambda c: (cnt[c], c))
    fill = [c for c in cnt if c not in (bg, bar)][0]
    return bg, bar, fill


def _below_mask(inp, bar, up=False):
    h, w = len(inp), len(inp[0])
    mask = [[False] * w for _ in range(h)]
    for c in range(w):
        rows = [r for r in range(h) if inp[r][c] == bar]
        if not rows:
            continue
        if up:
            for r in range(min(rows)):
                mask[r][c] = True
        else:
            for r in range(max(rows) + 1, h):
                mask[r][c] = True
    return mask


def _render(inp, mask, bg, bar, fill, barrier_color=None):
    return [[(barrier_color if barrier_color is not None else bar) if inp[r][c] == bar
             else (fill if mask[r][c] else bg)
             for c in range(len(inp[0]))] for r in range(len(inp))]


def fill_up(inp, out):
    bg, bar, fill = _colors(inp)
    return _render(inp, _below_mask(inp, bar, up=True), bg, bar, fill)


def fill_right_of_barrier(inp, out):
    bg, bar, fill = _colors(inp)
    h, w = len(inp), len(inp[0])
    mask = [[False] * w for _ in range(h)]
    for r in range(h):
        cols = [c for c in range(w) if inp[r][c] == bar]
        if cols:
            for c in range(max(cols) + 1, w):
                mask[r][c] = True
    return _render(inp, mask, bg, bar, fill)


def fill_one_cell_only(inp, out):
    bg, bar, fill = _colors(inp)
    h, w = len(inp), len(inp[0])
    mask = [[False] * w for _ in range(h)]
    for c in range(w):
        rows = [r for r in range(h) if inp[r][c] == bar]
        if rows and max(rows) + 1 < h:
            mask[max(rows) + 1][c] = True
    return _render(inp, mask, bg, bar, fill)


def fill_below_lowest_barrier_row(inp, out):
    bg, bar, fill = _colors(inp)
    h, w = len(inp), len(inp[0])
    low = max(r for r in range(h) if bar in inp[r])
    mask = [[r > low for _ in range(w)] for r in range(h)]
    return _render(inp, mask, bg, bar, fill)


def fill_below_highest_barrier_row(inp, out):
    bg, bar, fill = _colors(inp)
    h, w = len(inp), len(inp[0])
    top = min(r for r in range(h) if bar in inp[r])
    mask = [[r > top for _ in range(w)] for r in range(h)]
    return _render(inp, mask, bg, bar, fill)


def skip_cell_below_barrier(inp, out):
    bg, bar, fill = _colors(inp)
    mask = _below_mask(inp, bar)
    h, w = len(inp), len(inp[0])
    for c in range(w):
        rows = [r for r in range(h) if inp[r][c] == bar]
        if rows and max(rows) + 1 < h:
            mask[max(rows) + 1][c] = False
    return _render(inp, mask, bg, bar, fill)


def include_cell_above_barrier(inp, out):
    bg, bar, fill = _colors(inp)
    mask = _below_mask(inp, bar)
    h, w = len(inp), len(inp[0])
    for c in range(w):
        rows = [r for r in range(h) if inp[r][c] == bar]
        if rows and min(rows) > 0 and inp[min(rows) - 1][c] != bar:
            mask[min(rows) - 1][c] = True
    return _render(inp, mask, bg, bar, fill)


def barrier_erased(inp, out):
    bg, bar, fill = _colors(inp)
    return _render(inp, _below_mask(inp, bar), bg, bar, fill, barrier_color=bg)


def barrier_recolored_as_fill(inp, out):
    bg, bar, fill = _colors(inp)
    return _render(inp, _below_mask(inp, bar), bg, bar, fill, barrier_color=fill)


def swap_fill_and_background(inp, out):
    bg, bar, fill = _colors(inp)
    return [[bar if inp[r][c] == bar else (bg if out[r][c] == fill else fill)
             for c in range(len(inp[0]))] for r in range(len(inp))]


def keep_input_outside_fill(inp, out):
    bg, bar, fill = _colors(inp)
    return [[out[r][c] if (out[r][c] == fill or inp[r][c] == bar) else inp[r][c]
             for c in range(len(inp[0]))] for r in range(len(inp))]


def fill_only_columns_without_extra_fill(inp, out):
    """Fill is the input's own fill-colored cells below the barrier; bg cells below stay bg."""
    bg, bar, fill = _colors(inp)
    mask = _below_mask(inp, bar)
    return [[bar if inp[r][c] == bar else (fill if mask[r][c] and inp[r][c] == fill else bg)
             for c in range(len(inp[0]))] for r in range(len(inp))]


ALTERNATIVES = [
    ("fill the cells above the barrier instead of below", fill_up),
    ("fill to the right of the barrier in each row instead of below", fill_right_of_barrier),
    ("fill only the single cell under each column's barrier", fill_one_cell_only),
    ("fill every row under the lowest barrier row, across all columns", fill_below_lowest_barrier_row),
    ("fill every row under the highest barrier row, across all columns", fill_below_highest_barrier_row),
    ("fill starts two cells under the barrier (cell right below stays background)", skip_cell_below_barrier),
    ("fill also takes the cell just above each column's barrier", include_cell_above_barrier),
    ("barrier cells are erased to background", barrier_erased),
    ("barrier cells are painted in the fill color", barrier_recolored_as_fill),
    ("fill color and background color are swapped", swap_fill_and_background),
    ("cells outside the filled region keep their input colors", keep_input_outside_fill),
    ("only cells below the barrier that already had the fill color are kept", fill_only_columns_without_extra_fill),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/782b5218.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
