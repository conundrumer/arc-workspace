import json
from collections import Counter
from pathlib import Path


def _parse(inp):
    h, w = len(inp), len(inp[0])
    cnt = Counter(c for r in inp for c in r)
    bg = cnt.most_common(1)[0][0]
    seen = set()
    comps = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] != bg and (i, j) not in seen:
                st = [(i, j)]
                seen.add((i, j))
                cells = []
                while st:
                    a, b = st.pop()
                    cells.append((a, b))
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        x, y = a + da, b + db
                        if 0 <= x < h and 0 <= y < w and inp[x][y] != bg and (x, y) not in seen:
                            seen.add((x, y))
                            st.append((x, y))
                comps.append(sorted(cells))
    bar_color = Counter(inp[a][b] for c in comps for a, b in c).most_common(1)[0][0]
    mark = None
    gauge = None
    for c in comps:
        ms = [(a, b) for a, b in c if inp[a][b] != bar_color]
        if ms:
            gauge = c
            mark = ms
            mark_color = inp[ms[0][0]][ms[0][1]]
    return bg, bar_color, mark_color, comps, gauge, mark


def _rows(c):
    return sorted(set(a for a, b in c))


def _info(inp):
    bg, bc, mc, comps, gauge, mark = _parse(inp)
    glen = len(_rows(gauge))
    top = min(a for a, b in mark) == min(a for a, b in gauge)
    return bg, bc, mc, comps, gauge, mark, glen, top


def _paint(inp, target, n, top, mc, bc, bg, erase_gauge="bar", keep_mark=False, whole=False):
    """Draw n mark cells at the end of target; gauge handled per erase_gauge."""
    bg_, bc_, mc_, comps, gauge, mark = _parse(inp)
    g = [r[:] for r in inp]
    if not keep_mark:
        for a, b in mark:
            g[a][b] = bc if erase_gauge == "bar" else bg
        if erase_gauge == "bg":
            for a, b in gauge:
                g[a][b] = bg
    rows = sorted(target)
    cells = rows if whole else (rows[:n] if top else rows[len(rows) - n:])
    for a, b in cells:
        g[a][b] = mc
    return g


def _true(inp):
    bg, bc, mc, comps, gauge, mark, glen, top = _info(inp)
    longer = [c for c in comps if len(_rows(c)) > glen]
    t = min(longer, key=lambda c: len(_rows(c)))
    return _paint(inp, t, len(t) // 2, top, mc, bc, bg)


def _bars_by_len(inp):
    bg, bc, mc, comps, gauge, mark, glen, top = _info(inp)
    others = [c for c in comps if c is not gauge]
    return bg, bc, mc, gauge, mark, glen, top, others


def longest_bar(inp, out):
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    t = max(others, key=lambda c: len(c))
    return _paint(inp, t, len(t) // 2, top, mc, bc, bg)


def next_shorter(inp, out):
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    sh = [c for c in others if len(c) < glen]
    if not sh:
        return None
    t = max(sh, key=lambda c: len(c))
    return _paint(inp, t, len(t) // 2, top, mc, bc, bg)


def whole_bar(inp, out):
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    t = min([c for c in others if len(c) > glen], key=len)
    return _paint(inp, t, 0, top, mc, bc, bg, whole=True)


def opposite_end(inp, out):
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    t = min([c for c in others if len(c) > glen], key=len)
    return _paint(inp, t, len(t) // 2, not top, mc, bc, bg)


def mark_length_fill(inp, out):
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    t = min([c for c in others if len(c) > glen], key=len)
    return _paint(inp, t, len(mark), top, mc, bc, bg)


def half_plus_one(inp, out):
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    t = min([c for c in others if len(c) > glen], key=len)
    return _paint(inp, t, len(t) // 2 + 1, top, mc, bc, bg)


def half_minus_one(inp, out):
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    t = min([c for c in others if len(c) > glen], key=len)
    return _paint(inp, t, len(t) // 2 - 1, top, mc, bc, bg)


def keep_original_mark(inp, out):
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    t = min([c for c in others if len(c) > glen], key=len)
    return _paint(inp, t, len(t) // 2, top, mc, bc, bg, keep_mark=True)


def erase_gauge_bar(inp, out):
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    t = min([c for c in others if len(c) > glen], key=len)
    return _paint(inp, t, len(t) // 2, top, mc, bc, bg, erase_gauge="bg")


def at_least_as_long(inp, out):
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    ge = [c for c in others if len(c) >= glen]
    t = min(ge, key=lambda c: (len(c), c[0]))
    return _paint(inp, t, len(t) // 2, top, mc, bc, bg)


def mark_always_at_top(inp, out):
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    t = min([c for c in others if len(c) > glen], key=len)
    return _paint(inp, t, len(t) // 2, True, mc, bc, bg)


def gauge_cleared_only(inp, out):
    """Mark removed from the gauge bar but never placed on another bar."""
    bg, bc, mc, gauge, mark, glen, top, others = _bars_by_len(inp)
    g = [r[:] for r in inp]
    for a, b in mark:
        g[a][b] = bc
    return g


ALTERNATIVES = [
    ("mark moves to the longest bar instead of the next longer bar", longest_bar),
    ("mark moves to the next shorter bar", next_shorter),
    ("whole target bar is filled instead of half", whole_bar),
    ("half fill starts from the opposite end of the target bar", opposite_end),
    ("fill length equals the original mark length", mark_length_fill),
    ("fill is half the bar length plus one cell", half_plus_one),
    ("fill is half the bar length minus one cell", half_minus_one),
    ("original mark stays in the gauge bar as well", keep_original_mark),
    ("whole gauge bar is erased to background", erase_gauge_bar),
    ("target is the next bar at least as long, so equal-length bars qualify", at_least_as_long),
    ("fill always starts at the top of the target bar", mark_always_at_top),
    ("mark is cleared from the gauge bar and not placed anywhere", gauge_cleared_only),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/48634b99.json"))
    pairs = task["train"]

    def valid(g, out):
        return (
            isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len(set(len(r) for r in g)) == 1
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
            and g != out
        )

    for p in pairs:
        assert _true(p["input"]) == p["output"], "reference reading mismatch"
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
