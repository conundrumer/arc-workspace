"""Near-miss readings for ARC task 9841fdad.

Rule: lines of one color span the grid and cut it into panels. One panel holds
rectangles on a ground color. Each rectangle is copied into every other panel.
On each axis a rectangle keeps its margin from the nearer side of its panel;
where both margins are equal it stretches to span the target panel with that
margin.
"""
import json
from collections import Counter
from pathlib import Path


def _runs(flags):
    runs, start = [], None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        if not f and start is not None:
            runs.append((start, i - 1))
            start = None
    return runs


def _analyze(inp):
    h, w = len(inp), len(inp[0])
    c = inp[0][0]
    rows = _runs([not all(v == c for v in inp[r]) for r in range(h)])
    cols = _runs([not all(inp[r][x] == c for r in range(h)) for x in range(w)])
    panels = [(r0, r1, c0, c1) for (r0, r1) in rows for (c0, c1) in cols]
    info = []
    for (r0, r1, c0, c1) in panels:
        cnt = Counter(inp[r][x] for r in range(r0, r1 + 1) for x in range(c0, c1 + 1))
        ground = cnt.most_common(1)[0][0]
        seen, rects = set(), []
        for r in range(r0, r1 + 1):
            for x in range(c0, c1 + 1):
                if inp[r][x] == ground or (r, x) in seen:
                    continue
                col = inp[r][x]
                stack, comp = [(r, x)], []
                seen.add((r, x))
                while stack:
                    a, b = stack.pop()
                    comp.append((a, b))
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        na, nb = a + da, b + db
                        if (r0 <= na <= r1 and c0 <= nb <= c1 and (na, nb) not in seen
                                and inp[na][nb] == col):
                            seen.add((na, nb))
                            stack.append((na, nb))
                rects.append((min(a for a, _ in comp), max(a for a, _ in comp),
                              min(b for _, b in comp), max(b for _, b in comp), col))
        info.append(((r0, r1, c0, c1), ground, sorted(rects)))
    return c, info


# axis policies: (lo, hi, size, tlen, slen) -> (start, end) relative to target low side
def _true(lo, hi, size, tlen, slen):
    if lo == hi:
        return lo, tlen - 1 - hi
    if lo < hi:
        return lo, lo + size - 1
    return tlen - hi - size, tlen - 1 - hi


def _no_stretch(lo, hi, size, tlen, slen):
    if lo == hi:
        return lo, lo + size - 1
    return _true(lo, hi, size, tlen, slen)


def _always_lo(lo, hi, size, tlen, slen):
    return lo, lo + size - 1


def _always_hi(lo, hi, size, tlen, slen):
    return tlen - hi - size, tlen - 1 - hi


def _farther(lo, hi, size, tlen, slen):
    if lo == hi:
        return _true(lo, hi, size, tlen, slen)
    if lo < hi:
        return tlen - hi - size, tlen - 1 - hi
    return lo, lo + size - 1


def _stretch_all(lo, hi, size, tlen, slen):
    m = min(lo, hi)
    return m, tlen - 1 - m


def _short_stretch(lo, hi, size, tlen, slen):
    if lo == hi:
        return lo, tlen - 2 - hi
    return _true(lo, hi, size, tlen, slen)


def _scaled(lo, hi, size, tlen, slen):
    s = lo * tlen // slen
    e = s + max(1, size * tlen // slen) - 1
    return s, e


def _render(inp, pol_v=_true, pol_h=_true, color=None, erase_source=False,
            keep=None, include_source_noop=False):
    line, info = _analyze(inp)
    srcs = [p for p in info if p[2]]
    if len(srcs) != 1 or len(info) < 2:
        return None
    (sp, sground, rects) = srcs[0]
    g = [row[:] for row in inp]
    for (tp, tground, _) in info:
        if tp == sp:
            continue
        for idx, (r0, r1, c0, c1, col) in enumerate(rects):
            if keep is not None and not keep(idx, rects, sp):
                continue
            s_rows, s_cols = sp[1] - sp[0] + 1, sp[3] - sp[2] + 1
            t_rows, t_cols = tp[1] - tp[0] + 1, tp[3] - tp[2] + 1
            vs, ve = pol_v(r0 - sp[0], sp[1] - r1, r1 - r0 + 1, t_rows, s_rows)
            hs, he = pol_h(c0 - sp[2], sp[3] - c1, c1 - c0 + 1, t_cols, s_cols)
            if vs < 0 or hs < 0 or ve >= t_rows or he >= t_cols or ve < vs or he < hs:
                return None
            paint = col if color is None else color(col, line, sground, tground)
            for r in range(vs, ve + 1):
                for x in range(hs, he + 1):
                    g[tp[0] + r][tp[2] + x] = paint
    if erase_source:
        for (r0, r1, c0, c1, col) in rects:
            for r in range(r0, r1 + 1):
                for x in range(c0, c1 + 1):
                    g[r][x] = sground
    return g


def _is_stretched(rect, sp):
    r0, r1, c0, c1, _ = rect
    return r0 - sp[0] == sp[1] - r1 or c0 - sp[2] == sp[3] - c1


def true_output(inp, out):
    return _render(inp)


def no_stretch(inp, out):
    return _render(inp, _no_stretch, _no_stretch)


def always_low_side(inp, out):
    return _render(inp, _always_lo, _always_lo)


def always_high_side(inp, out):
    return _render(inp, _always_hi, _always_hi)


def farther_side(inp, out):
    return _render(inp, _farther, _farther)


def stretch_everything(inp, out):
    return _render(inp, _stretch_all, _stretch_all)


def stretch_one_short(inp, out):
    return _render(inp, _true, _short_stretch)


def scaled_with_panel(inp, out):
    return _render(inp, _scaled, _scaled)


def only_stretched(inp, out):
    return _render(inp, keep=lambda i, rs, sp: _is_stretched(rs[i], sp))


def only_unstretched(inp, out):
    return _render(inp, keep=lambda i, rs, sp: not _is_stretched(rs[i], sp))


def only_first_rect(inp, out):
    return _render(inp, keep=lambda i, rs, sp: i == 0)


def line_color_paint(inp, out):
    return _render(inp, color=lambda col, line, sg, tg: line)


def moved_not_copied(inp, out):
    return _render(inp, erase_source=True)


def horizontal_by_farther_side(inp, out):
    return _render(inp, _true, _farther)


ALTERNATIVES = [
    ("a tie of margins is not stretched: the rectangle keeps its size at the low side", no_stretch),
    ("every rectangle keeps its margin from the top and left side, never the nearer side", always_low_side),
    ("every rectangle keeps its margin from the bottom and right side", always_high_side),
    ("a rectangle keeps its margin from the farther side instead of the nearer side", farther_side),
    ("every rectangle stretches across the target panel on both axes", stretch_everything),
    ("a stretched rectangle ends one cell short of the far margin", stretch_one_short),
    ("a rectangle scales in position and size with the panel size", scaled_with_panel),
    ("only the stretched rectangles are copied", only_stretched),
    ("only the rectangles that are not stretched are copied", only_unstretched),
    ("only the first rectangle in reading order is copied", only_first_rect),
    ("copies take the color of the dividing lines", line_color_paint),
    ("rectangles move to the other panel and leave the source panel empty", moved_not_copied),
    ("horizontal position follows the farther side; vertical follows the nearer side", horizontal_by_farther_side),
]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/9841fdad.json"))
    pairs = task["train"]
    print("pairs:", len(pairs))
    t = [true_output(p["input"], p["output"]) == p["output"] for p in pairs]
    print("sanity (true reading reproduces output):", t)
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(p["input"], p["output"]), p["output"]) for p in pairs)
        print(f"{n}/{len(pairs)}  {desc}")
