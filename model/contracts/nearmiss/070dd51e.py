import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _spans(inp, extend=0, to_edge=False, orients="HV"):
    """Segments between same-colored marks sharing a row (H) or column (V)."""
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    marks = [(r, c, inp[r][c]) for r in range(h) for c in range(w) if inp[r][c] != bg]
    segs = []
    for col in set(m[2] for m in marks):
        pts = [(r, c) for r, c, v in marks if v == col]
        if "H" in orients:
            rows = {}
            for r, c in pts:
                rows.setdefault(r, []).append(c)
            for r, cs in rows.items():
                if len(cs) > 1:
                    lo, hi = min(cs), max(cs)
                    if to_edge:
                        lo, hi = 0, w - 1
                    lo, hi = max(0, lo - extend), min(w - 1, hi + extend)
                    segs.append(("H", col, [(r, c) for c in range(lo, hi + 1)]))
        if "V" in orients:
            cols = {}
            for r, c in pts:
                cols.setdefault(c, []).append(r)
            for c, rs in cols.items():
                if len(rs) > 1:
                    lo, hi = min(rs), max(rs)
                    if to_edge:
                        lo, hi = 0, h - 1
                    lo, hi = max(0, lo - extend), min(h - 1, hi + extend)
                    segs.append(("V", col, [(r, c) for r in range(lo, hi + 1)]))
    return segs


def _render(inp, segs, key, keep_marks=True):
    """Paint segments in ascending key order, so the highest key wins a crossing."""
    g = [row[:] for row in inp]
    for o, col, cells in sorted(segs, key=key):
        for r, c in cells:
            g[r][c] = col
    return g


def horiz_wins(inp, out):
    return _render(inp, _spans(inp), lambda s: (s[0] == "H", s[1]))


def only_vertical(inp, out):
    return _render(inp, _spans(inp, orients="V"), lambda s: s[1])


def only_horizontal(inp, out):
    return _render(inp, _spans(inp, orients="H"), lambda s: s[1])


def low_color_wins(inp, out):
    return _render(inp, _spans(inp), lambda s: -s[1])


def high_color_wins(inp, out):
    return _render(inp, _spans(inp), lambda s: s[1])


def shorter_wins(inp, out):
    return _render(inp, _spans(inp), lambda s: (-len(s[2]), s[1]))


def crossing_left_empty(inp, out):
    segs = _spans(inp)
    cnt = Counter(p for s in segs for p in s[2])
    g = [row[:] for row in inp]
    bg = _bg(inp)
    for o, col, cells in segs:
        for r, c in cells:
            g[r][c] = bg if cnt[(r, c)] > 1 else col
    return g


def extend_one_past_ends(inp, out):
    return _render(inp, _spans(inp, extend=1), lambda s: (s[0] == "V", s[1]))


def span_to_grid_edge(inp, out):
    return _render(inp, _spans(inp, to_edge=True), lambda s: (s[0] == "V", s[1]))


def endpoints_erased(inp, out):
    bg = _bg(inp)
    g = [row[:] for row in out]
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if inp[r][c] != bg:
                g[r][c] = bg
    return g


def spans_skip_interior_marks_row(inp, out):
    """Horizontal spans drawn only on the top half of the grid."""
    h = len(inp)
    segs = [s for s in _spans(inp) if s[0] == "V" or s[2][0][0] < h // 2]
    return _render(inp, segs, lambda s: (s[0] == "V", s[1]))


def crop_to_span_bbox(inp, out):
    segs = _spans(inp)
    rs = [r for s in segs for r, c in s[2]]
    cs = [c for s in segs for r, c in s[2]]
    g = _render(inp, segs, lambda s: (s[0] == "V", s[1]))
    return [row[min(cs):max(cs) + 1] for row in g[min(rs):max(rs) + 1]]


ALTERNATIVES = [
    ("Horizontal spans win over vertical ones where they cross", horiz_wins),
    ("Only vertical spans are drawn; horizontal pairs are ignored", only_vertical),
    ("Only horizontal spans are drawn; vertical pairs are ignored", only_horizontal),
    ("At a crossing, the span of the lower color number wins", low_color_wins),
    ("At a crossing, the span of the higher color number wins", high_color_wins),
    ("At a crossing, the shorter span wins", shorter_wins),
    ("Crossing cells of two spans are left background", crossing_left_empty),
    ("Each span is drawn one cell past both of its end marks", extend_one_past_ends),
    ("Each span is drawn as a full line to both grid edges", span_to_grid_edge),
    ("The original mark cells are erased to background", endpoints_erased),
    ("Horizontal spans are drawn only in the top half of the grid", spans_skip_interior_marks_row),
    ("Output is cropped to the bounding box of all spans", crop_to_span_bbox),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/070dd51e.json"))
    pairs = task["train"]
    print("pairs:", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(n, desc)
    print("sanity (vertical-wins reference reproduces output):",
          all(_render(p["input"], _spans(p["input"]), lambda s: (s[0] == "V", s[1])) == p["output"] for p in pairs))
