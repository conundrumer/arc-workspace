import json
from pathlib import Path

BG = 7
CAP = 8
STEM = 1
REST = 9


def _info(inp):
    h, w = len(inp), len(inp[0])
    r_cap = next(r for r in range(h) if inp[r][0] == 2)
    r_stem = next(r for r in range(h) if inp[r][0] == 5)
    cols = [c for c in range(w) if any(inp[r][c] in (CAP, STEM) for r in range(h))]
    cap = {c: sum(inp[r][c] == CAP for r in range(h)) for c in cols}
    stem = {c: sum(inp[r][c] == STEM for r in range(h)) for c in cols}
    return h, w, r_cap, r_stem, cols, cap, stem


def _mode(vals):
    return max(set(vals), key=lambda v: (vals.count(v), v))


def _draw(inp, cap_len, stem_len, cap_up=True, cap_c=CAP, stem_c=STEM,
          rest_c=REST, cap_from=None, stem_from=None, tail_c=BG):
    h, w, r_cap, r_stem, cols, cap, stem = _info(inp)
    out = [row[:] for row in inp]
    for c in cols:
        for r in range(h):
            if r != r_cap and r != r_stem and out[r][c] in (CAP, STEM):
                out[r][c] = BG
        out[r_cap][c] = BG
        out[r_stem][c] = BG
    for c in cols:
        a = r_cap if cap_from is None else cap_from
        b = r_stem if stem_from is None else stem_from
        n = cap_len(c)
        m = stem_len(c)
        if cap_up:
            for k in range(a + 1):
                if a - k >= 0:
                    out[a - k][c] = cap_c if k < n else tail_c
            for k in range(h - b):
                out[b + k][c] = stem_c if k < m else rest_c
        else:
            for k in range(h - b):
                out[b + k][c] = cap_c if k < n else tail_c
            for k in range(a + 1):
                out[a - k][c] = stem_c if k < m else rest_c
    return out


def _true_cap(inp):
    _, _, _, _, cols, cap, _ = _info(inp)
    return _mode([cap[c] for c in cols])


def _same(a, b):
    return a == b


def tallest_only(inp, out):
    return _draw(inp, lambda c: _true_cap(inp) + 1, lambda c: _info(inp)[6][c])


def own_cap(inp, out):
    cap = _info(inp)[5]
    return _draw(inp, lambda c: cap[c], lambda c: _info(inp)[6][c])


def shortest_cap(inp, out):
    _, _, _, _, cols, cap, _ = _info(inp)
    m = min(cap[c] for c in cols)
    k = _true_cap(inp)
    return _draw(inp, lambda c: m if m != k else k - 1, lambda c: _info(inp)[6][c])


def cap_above_line(inp, out):
    # Cap starts above the cap line; the cap line row keeps its input cells.
    h, w, r_cap, r_stem, cols, cap, stem = _info(inp)
    res = [row[:] for row in out]
    k = _true_cap(inp)
    for c in cols:
        res[r_cap][c] = inp[r_cap][c]
        for i in range(1, k + 1):
            if r_cap - i >= 0:
                res[r_cap - i][c] = CAP
    return res


def stem_rest_background(inp, out):
    return [[BG if v == REST else v for v in row] for row in out]


def stem_common_length(inp, out):
    _, _, _, _, cols, cap, stem = _info(inp)
    m = _mode([stem[c] for c in cols])
    return _draw(inp, lambda c: _true_cap(inp), lambda c: m)


def stem_length_off_by_one(inp, out):
    stem = _info(inp)[6]
    return _draw(inp, lambda c: _true_cap(inp), lambda c: stem[c] + 1)


def swapped_colors(inp, out):
    return [[STEM if v == CAP else CAP if v == STEM else v for v in row]
            for row in out]


def directions_swapped(inp, out):
    stem = _info(inp)[6]
    return _draw(inp, lambda c: _true_cap(inp), lambda c: stem[c], cap_up=False)


def lines_not_extended(inp, out):
    h, w, r_cap, r_stem, cols, cap, stem = _info(inp)
    res = [row[:] for row in out]
    for c in cols:
        res[r_cap][c] = inp[r_cap][c]
        res[r_stem][c] = inp[r_stem][c]
    return res


def stem_from_below_line(inp, out):
    # Stem starts one row below the stem line; the stem line row stays background.
    h, w, r_cap, r_stem, cols, cap, stem = _info(inp)
    return _draw(inp, lambda c: _true_cap(inp), lambda c: stem[c],
                 stem_from=r_stem + 1)


def stems_reversed_order(inp, out):
    # Rest color first, then the stem, i.e. stem hangs from the far end.
    h, w, r_cap, r_stem, cols, cap, stem = _info(inp)
    res = [row[:] for row in out]
    for c in cols:
        n = h - r_stem
        s = stem[c]
        for k in range(n):
            res[r_stem + k][c] = REST if k < n - s else STEM
    return res


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("cap one row taller than the common cap length", tallest_only),
    ("each bar's cap keeps its own length instead of one shared height", own_cap),
    ("cap height is the shortest bar's cap length", shortest_cap),
    ("cap starts above the cap line; the line row keeps its input cell", cap_above_line),
    ("rest of each stem column left as background instead of the new color", stem_rest_background),
    ("every stem gets the most common stem length", stem_common_length),
    ("each stem one cell too long", stem_length_off_by_one),
    ("cap and stem colors swapped", swapped_colors),
    ("cap grows below the stem line and stem grows above the cap line", directions_swapped),
    ("line rows are not filled by the bars", lines_not_extended),
    ("stem starts one row below the stem line", stem_from_below_line),
    ("stem is drawn from the far end of the column, rest color near the line", stems_reversed_order),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/41ace6b5.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
