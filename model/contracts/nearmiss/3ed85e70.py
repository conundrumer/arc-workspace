"""Near-miss readings for ARC task 3ed85e70.

A legend panel (flat background, reaching the grid edge) holds framed shapes.
Each field clue (a block matching a legend shape's core) gets the whole
legend shape drawn around/over it.
"""
import json
from collections import Counter
from pathlib import Path


def _dominant(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _components(cells):
    cells = set(cells)
    seen = set()
    comps = []
    for c in sorted(cells):
        if c in seen:
            continue
        stack = [c]
        seen.add(c)
        comp = []
        while stack:
            r, q = stack.pop()
            comp.append((r, q))
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (r + d[0], q + d[1])
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
        comps.append(comp)
    return comps


def _panel_box(inp):
    h, w = len(inp), len(inp[0])
    dom = _dominant(inp)
    border = {(r, c) for r in range(h) for c in range(w)
              if r in (0, h - 1) or c in (0, w - 1)}
    best = []
    for v in set(x for row in inp for x in row) - {dom}:
        cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == v]
        for comp in _components(cells):
            if any(p in border for p in comp) and len(comp) > len(best):
                best = comp
    rs = [p[0] for p in best]
    cs = [p[1] for p in best]
    return min(rs), max(rs), min(cs), max(cs)


def _in_box(box, r, c):
    return box[0] <= r <= box[1] and box[2] <= c <= box[3]


def _clues(inp):
    h, w = len(inp), len(inp[0])
    dom = _dominant(inp)
    box = _panel_box(inp)
    comps = []
    for v in set(x for row in inp for x in row) - {dom}:
        cells = [(r, c) for r in range(h) for c in range(w)
                 if inp[r][c] == v and not _in_box(box, r, c)]
        comps.extend(_components(cells))
    return sorted(comps, key=lambda comp: min(comp))


def _changed(inp, out):
    return [(r, c) for r in range(len(out)) for c in range(len(out[0]))
            if inp[r][c] != out[r][c]]


def _by_clue(inp, out):
    """Map clue index -> changed cells that lie nearest that clue."""
    clues = _clues(inp)
    groups = {}
    for (r, c) in _changed(inp, out):
        best = None
        for i, comp in enumerate(clues):
            d = min(max(abs(r - a), abs(c - b)) for a, b in comp)
            if best is None or d < best[0]:
                best = (d, i)
        if best is not None:
            groups.setdefault(best[1], []).append((r, c))
    return clues, groups


def _revert(inp, out, cells):
    g = [row[:] for row in out]
    for r, c in cells:
        g[r][c] = inp[r][c]
    return g


def revert_top_color(inp, out):
    cnt = Counter(out[r][c] for r, c in _changed(inp, out))
    v = cnt.most_common(1)[0][0]
    return _revert(inp, out, [(r, c) for r, c in _changed(inp, out) if out[r][c] == v])


def rotate_colors(inp, out):
    ch = _changed(inp, out)
    vals = sorted(set(out[r][c] for r, c in ch))
    if len(vals) < 2:
        return None
    m = {v: vals[(i + 1) % len(vals)] for i, v in enumerate(vals)}
    g = [row[:] for row in out]
    for r, c in ch:
        g[r][c] = m[out[r][c]]
    return g


def _shift(inp, out, dr, dc):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for r, c in _changed(inp, out):
        if 0 <= r + dr < h and 0 <= c + dc < w:
            g[r + dr][c + dc] = out[r][c]
    return g


def shift_right(inp, out):
    return _shift(inp, out, 0, 1)


def shift_down(inp, out):
    return _shift(inp, out, 1, 0)


def shift_up_left(inp, out):
    return _shift(inp, out, -1, -1)


def only_first_clue(inp, out):
    clues, groups = _by_clue(inp, out)
    keys = sorted(groups)
    if len(keys) < 2:
        return None
    drop = [p for k in keys[1:] for p in groups[k]]
    return _revert(inp, out, drop)


def skip_last_clue(inp, out):
    clues, groups = _by_clue(inp, out)
    keys = sorted(groups)
    if not keys:
        return None
    return _revert(inp, out, groups[keys[-1]])


def only_largest_clue(inp, out):
    clues, groups = _by_clue(inp, out)
    if len(groups) < 2:
        return None
    big = max(groups, key=lambda k: (len(clues[k]), -k))
    drop = [p for k in groups if k != big for p in groups[k]]
    return _revert(inp, out, drop)


def erase_legend(inp, out):
    box = _panel_box(inp)
    dom = _dominant(inp)
    g = [row[:] for row in out]
    for r in range(len(g)):
        for c in range(len(g[0])):
            if _in_box(box, r, c):
                g[r][c] = dom
    return g


def crop_field(inp, out):
    r0, r1, c0, c1 = _panel_box(inp)
    h, w = len(out), len(out[0])
    if r1 - r0 + 1 < h and c1 - c0 + 1 == w:
        rows = [r for r in range(h) if not r0 <= r <= r1]
        return [out[r][:] for r in rows]
    if c1 - c0 + 1 < w and r1 - r0 + 1 == h:
        return [[out[r][c] for c in range(w) if not c0 <= c <= c1] for r in range(h)]
    return None


def erase_clues(inp, out):
    clues, groups = _by_clue(inp, out)
    dom = _dominant(inp)
    g = [row[:] for row in out]
    for k in groups:
        for r, c in clues[k]:
            if inp[r][c] == out[r][c]:
                g[r][c] = dom
    return g


def solid_fill(inp, out):
    ch = _changed(inp, out)
    cnt = Counter(out[r][c] for r, c in ch)
    if len(cnt) < 2:
        return None
    v = cnt.most_common(1)[0][0]
    g = [row[:] for row in out]
    for r, c in ch:
        g[r][c] = v
    return g


ALTERNATIVES = [
    ("leave the most common stamped color unpainted", revert_top_color),
    ("assign each stamped color to the next legend color", rotate_colors),
    ("stamps placed one column to the right", shift_right),
    ("stamps placed one row down", shift_down),
    ("stamps placed one row up and one column left", shift_up_left),
    ("only the first clue in reading order is stamped", only_first_clue),
    ("the last clue in reading order is left unstamped", skip_last_clue),
    ("only the largest clue is stamped", only_largest_clue),
    ("legend panel is treated as field and erased", erase_legend),
    ("output is the field region only, panel cropped away", crop_field),
    ("clue blocks are consumed: cells of stamped clues erased", erase_clues),
    ("every stamped cell drawn in one color", solid_fill),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / "data/tasks/3ed85e70.json"
    train = json.load(open(path))["train"]
    print(f"pairs: {len(train)}")
    for name, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {name}")
