import json
from collections import Counter
from pathlib import Path

D8 = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
D4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _info(inp):
    cnt = Counter(c for r in inp for c in r)
    bg = cnt.most_common(1)[0][0]
    mark = min(cnt, key=lambda c: cnt[c])
    return bg, mark


def _comps(inp, bg, mark, dirs):
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] in (bg, mark) or (i, j) in seen:
                continue
            st = [(i, j)]
            seen.add((i, j))
            comp = []
            while st:
                a, b = st.pop()
                comp.append((a, b))
                for da, db in dirs:
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and (x, y) not in seen and inp[x][y] not in (bg, mark):
                        seen.add((x, y))
                        st.append((x, y))
            comps.append(comp)
    return comps


def _mark_pos(inp, mark):
    for i, r in enumerate(inp):
        for j, c in enumerate(r):
            if c == mark:
                return i, j


def _touching(inp, comps, mp):
    for comp in comps:
        if any(max(abs(a - mp[0]), abs(b - mp[1])) == 1 for a, b in comp):
            return comp
    return None


def _bbox(cells):
    return (min(a for a, _ in cells), max(a for a, _ in cells),
            min(b for _, b in cells), max(b for _, b in cells))


def _crop(inp, r0, r1, c0, c1, bg):
    h, w = len(inp), len(inp[0])
    return [[inp[i][j] if 0 <= i < h and 0 <= j < w else bg for j in range(c0, c1 + 1)]
            for i in range(r0, r1 + 1)]


def _ctx(inp):
    bg, mark = _info(inp)
    comps = _comps(inp, bg, mark, D8)
    mp = _mark_pos(inp, mark)
    own = _touching(inp, comps, mp)
    return bg, mark, comps, mp, own


def other_shape(inp, out):
    bg, mark, comps, mp, own = _ctx(inp)
    others = [c for c in comps if c is not own]
    if not others:
        return None
    c = max(others, key=len)
    return _crop(inp, *_bbox(c), bg)


def with_mark_in_box(inp, out):
    bg, mark, comps, mp, own = _ctx(inp)
    r0, r1, c0, c1 = _bbox(own + [mp])
    return _crop(inp, r0, r1, c0, c1, bg)


def four_connected(inp, out):
    bg, mark = _info(inp)
    comps = _comps(inp, bg, mark, D4)
    mp = _mark_pos(inp, mark)
    own = _touching(inp, comps, mp)
    if own is None:
        return None
    return _crop(inp, *_bbox(own), bg)


def flip_h(inp, out):
    return [r[::-1] for r in out]


def transpose(inp, out):
    return [list(r) for r in zip(*out)]


def recolor_mark(inp, out):
    bg, mark = _info(inp)
    return [[mark if c != bg else bg for c in r] for r in out]


def window_at_mark(inp, out):
    bg, mark, comps, mp, own = _ctx(inp)
    return _crop(inp, mp[0] - 1, mp[0] + 1, mp[1] - 1, mp[1] + 1, bg)


def all_shapes_box(inp, out):
    bg, mark, comps, mp, own = _ctx(inp)
    cells = [p for c in comps for p in c]
    return _crop(inp, *_bbox(cells), bg)


def shifted_up(inp, out):
    bg, mark, comps, mp, own = _ctx(inp)
    r0, r1, c0, c1 = _bbox(own)
    return _crop(inp, r0 - 1, r1 - 1, c0, c1, bg)


def shifted_right(inp, out):
    bg, mark, comps, mp, own = _ctx(inp)
    r0, r1, c0, c1 = _bbox(own)
    return _crop(inp, r0, r1, c0 + 1, c1 + 1, bg)


def margin_one(inp, out):
    bg, mark, comps, mp, own = _ctx(inp)
    r0, r1, c0, c1 = _bbox(own)
    return _crop(inp, r0 - 1, r1 + 1, c0 - 1, c1 + 1, bg)


def largest_shape(inp, out):
    bg, mark, comps, mp, own = _ctx(inp)
    c = max(comps, key=len)
    return _crop(inp, *_bbox(c), bg)


ALTERNATIVES = [
    ("crop the box of the largest other shape, not the one the mark touches", other_shape),
    ("box includes the mark cell, so the crop grows and keeps the mark color", with_mark_in_box),
    ("shape found with 4-connectivity instead of 8", four_connected),
    ("correct crop, mirrored left-right", flip_h),
    ("correct crop, transposed", transpose),
    ("shape recolored with the mark color", recolor_mark),
    ("3x3 window centered on the mark", window_at_mark),
    ("box around every non-background shape in the grid", all_shapes_box),
    ("box offset one row up", shifted_up),
    ("box offset one column right", shifted_right),
    ("box grown by a one-cell margin", margin_one),
    ("crop the largest shape in the grid", largest_shape),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/48d8fb45.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
