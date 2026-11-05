"""Near-miss readings for ARC task 2a28add5.

Rule: background 7, marker color 6, fill color 8. In each row that holds a 6,
all non-background cells pack into one contiguous bar of 8s around the 6
(ink on each side stays on that side); rows without a 6 become empty.
"""
import json
from pathlib import Path

BG, MK, FILL = 7, 6, 8


def _h(g):
    return len(g), len(g[0])


def _bg_grid(inp):
    return [[BG] * len(inp[0]) for _ in inp]


def _row_info(row, mk=MK):
    """(marker col, ink cols left of it, ink cols right of it) or None."""
    ms = [c for c, v in enumerate(row) if v == mk]
    if len(ms) != 1:
        return None
    m = ms[0]
    left = [c for c in range(m) if row[c] != BG]
    right = [c for c in range(m + 1, len(row)) if row[c] != BG]
    return m, left, right


def _apply_rows(inp, bar_fn, all_rows=False, mk=MK):
    g = _bg_grid(inp)
    for r, row in enumerate(inp):
        info = _row_info(row, mk)
        if info is None:
            if not all_rows:
                continue
            ink = [c for c, v in enumerate(row) if v != BG]
            if not ink:
                continue
            info = (None, ink, [])
        for c in bar_fn(info, len(row)):
            g[r][c] = FILL
    return g


def _true_bar(info, w):
    m, l, rt = info
    return range(m - len(l), m + len(rt) + 1)


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _pad_free(g):
    return g


def alt_marker_excluded(inp, out):
    g = [r[:] for r in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == MK:
                g[r][c] = BG
    return g


def alt_all_ink_rows(inp, out):
    def bar(info, w):
        m, l, rt = info
        if m is None:
            # no marker: pack ink flush to the left edge
            return range(0, len(l))
        return _true_bar(info, w)
    return _apply_rows(inp, bar, all_rows=True)


def alt_columns(inp, out):
    t = _transpose(inp)
    g = _apply_rows(t, _true_bar)
    return _transpose(g)


def alt_marker_most_common_ink(inp, out):
    counts = {}
    for row in inp:
        for v in row:
            if v != BG:
                counts[v] = counts.get(v, 0) + 1
    mk = max(counts, key=lambda k: (counts[k], k))
    if mk == MK:
        return None
    return _apply_rows(inp, _true_bar, mk=mk)


def alt_bar_one_short(inp, out):
    g = [r[:] for r in out]
    for r, row in enumerate(g):
        cols = [c for c, v in enumerate(row) if v == FILL]
        if cols:
            row[cols[-1]] = BG
    return g


def alt_fill_color_marker(inp, out):
    return [[MK if v == FILL else v for v in row] for row in out]


def alt_span_fill(inp, out):
    def bar(info, w):
        m, l, rt = info
        cols = l + [m] + rt
        return range(min(cols), max(cols) + 1)
    return _apply_rows(inp, bar)


def alt_all_ink_left_of_marker(inp, out):
    def bar(info, w):
        m, l, rt = info
        n = len(l) + len(rt)
        return range(max(0, m - n), m + 1)
    return _apply_rows(inp, bar)


def alt_only_left_ink_moves(inp, out):
    def bar(info, w):
        m, l, rt = info
        return list(range(m - len(l), m + 1)) + rt
    return _apply_rows(inp, bar)


def alt_unmarked_rows_kept(inp, out):
    g = [r[:] for r in out]
    for r, row in enumerate(out):
        if all(v == BG for v in row):
            g[r] = inp[r][:]
    return g


def alt_bar_centered_on_marker(inp, out):
    def bar(info, w):
        m, l, rt = info
        n = len(l) + len(rt) + 1
        s = max(0, m - n // 2)
        return range(s, min(w, s + n))
    return _apply_rows(inp, bar)


def alt_stack_to_marker_ignoring_side(inp, out):
    # ink cells are counted per row but bar starts at the marker and extends right
    def bar(info, w):
        m, l, rt = info
        n = len(l) + len(rt) + 1
        return range(m, min(w, m + n))
    return _apply_rows(inp, bar)


ALTERNATIVES = [
    ("marker cell itself left as background in the bar", alt_marker_excluded),
    ("rows with ink but no marker are also packed (flush left)", alt_all_ink_rows),
    ("rule applied to columns instead of rows", alt_columns),
    ("marker taken as the most common ink color", alt_marker_most_common_ink),
    ("bar one cell too short", alt_bar_one_short),
    ("bar drawn in the marker color instead of the fill color", alt_fill_color_marker),
    ("bar spans from leftmost to rightmost ink in the row", alt_span_fill),
    ("all ink packs onto the left side of the marker", alt_all_ink_left_of_marker),
    ("only ink left of the marker moves; right ink stays put", alt_only_left_ink_moves),
    ("rows without a marker keep their input cells", alt_unmarked_rows_kept),
    ("bar of right length centered on the marker", alt_bar_centered_on_marker),
    ("bar starts at the marker and extends right", alt_stack_to_marker_ignoring_side),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) and r for r in g):
        return False
    if len({len(r) for r in g}) != 1:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/2a28add5.json").read_text())
    pairs = task["train"]
    print(f"readings={len(ALTERNATIVES)} pairs={len(pairs)}")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
