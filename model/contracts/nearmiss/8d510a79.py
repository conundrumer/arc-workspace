import json
from collections import Counter
from pathlib import Path


def _tr(g):
    return [list(r) for r in zip(*g)]


def _analyse(inp):
    """Return (grid oriented so the divider is a row, transposed flag, divider row,
    marks [(r, c, color, side)], toward color, away color) or None."""
    g = [list(r) for r in inp]
    flip = False
    d = _divider(g)
    if d is None:
        g = _tr(g)
        flip = True
        d = _divider(g)
        if d is None:
            return None
    marks = []
    cnt = Counter()
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v and r != d:
                marks.append((r, c, v, -1 if r < d else 1))
                cnt[v] += 1
    cols = sorted(cnt, key=lambda k: (cnt[k], -k))
    toward = cols[0]
    away = cols[1] if len(cols) > 1 else cols[0]
    return g, flip, d, marks, toward, away


def _divider(g):
    for r, row in enumerate(g):
        if row[0] and all(v == row[0] for v in row):
            return r
    return None


def _ray(g, r, c, dr, dc, color, limit=None, through=None, paint_through=False):
    h, w = len(g), len(g[0])
    n = 0
    r += dr
    c += dc
    while 0 <= r < h and 0 <= c < w:
        if limit is not None and n >= limit:
            break
        if g[r][c] == 0:
            g[r][c] = color
        elif through is not None and (r, c) in through:
            if paint_through:
                g[r][c] = color
        else:
            break
        n += 1
        r += dr
        c += dc


def _cast(inp, dir_fn, base=None, side_filter=None, color_filter=None,
          limit_fn=None, horizontal=False, pierce=False, overwrite_div=False):
    a = _analyse(inp)
    if a is None:
        return None
    g, flip, d, marks, toward, away = a
    res = [list(r) for r in (base if base is not None else g)]
    if base is not None and flip:
        res = _tr(base)
    divcells = {(d, c) for c in range(len(g[0]))}
    for r, c, col, side in marks:
        if side_filter is not None and side != side_filter:
            continue
        if color_filter is not None and col not in color_filter(toward, away):
            continue
        dv = dir_fn(col, side, toward, away)
        if dv is None:
            continue
        lim = limit_fn(r, c, side, d, g) if limit_fn else None
        if horizontal:
            for dc in (dv,):
                _ray(res, r, c, 0, dc, col, lim)
        else:
            _ray(res, r, c, dv, 0, col, lim,
                 through=divcells if (pierce or overwrite_div) else None,
                 paint_through=overwrite_div)
    return _tr(res) if flip else res


def _correct_dir(col, side, toward, away):
    return -side if col == toward else side


def _from_input(inp, **kw):
    return _cast(inp, kw.pop("dir_fn"), **kw)


def swap_colors(inp, out):
    return _cast(inp, lambda col, s, t, a: s if col == t else -s)


def all_away(inp, out):
    return _cast(inp, lambda col, s, t, a: s)


def all_toward(inp, out):
    return _cast(inp, lambda col, s, t, a: -s)


def pierce_divider(inp, out):
    return _cast(inp, _correct_dir, pierce=True)


def horizontal_cast(inp, out):
    return _cast(inp, lambda col, s, t, a: 1 if col == t else -1, horizontal=True)


def only_toward_color(inp, out):
    return _cast(inp, _correct_dir, color_filter=lambda t, a: {t})


def only_away_color(inp, out):
    return _cast(inp, _correct_dir, color_filter=lambda t, a: {a})


def one_step(inp, out):
    return _cast(inp, _correct_dir, limit_fn=lambda r, c, s, d, g: 1)


def overwrite_divider(inp, out):
    return _cast(inp, _correct_dir, overwrite_div=True)


def side_decides(inp, out):
    # above the divider marks cast away, below the divider marks cast toward
    return _cast(inp, lambda col, s, t, a: s if s < 0 else -s)


def only_first_side(inp, out):
    return _cast(inp, _correct_dir, side_filter=-1)


def only_second_side(inp, out):
    return _cast(inp, _correct_dir, side_filter=1)


ALTERNATIVES = [
    ("the two mark colors swap roles: the rarer color casts away from the divider, the other toward it", swap_colors),
    ("every mark casts away from the divider", all_away),
    ("every mark casts toward the divider", all_toward),
    ("the divider does not block: toward-casting rays continue through it", pierce_divider),
    ("marks cast along their row (wrong axis), the rarer color rightward and the other leftward", horizontal_cast),
    ("only the rarer color casts; the other color's marks stay as dots", only_toward_color),
    ("only the more frequent color casts; the rarer color's marks stay as dots", only_away_color),
    ("each cast covers one cell only", one_step),
    ("toward-casting rays also overwrite the divider cell they reach", overwrite_divider),
    ("direction depends on the side only: marks before the divider cast away, marks after it cast toward", side_decides),
    ("the rule is applied only to marks before the divider (top or left)", only_first_side),
    ("the rule is applied only to marks after the divider (bottom or right)", only_second_side),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if any(len(r) != len(g[0]) or len(r) == 0 for r in g):
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/8d510a79.json'))
    pairs = task["train"]
    print("pairs:", len(pairs))
    # the true rule must reproduce the output
    for i, p in enumerate(pairs):
        assert _cast(p["input"], _correct_dir) == p["output"], i
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
