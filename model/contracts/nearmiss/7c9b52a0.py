import json
from collections import Counter
from pathlib import Path


def _frame(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _panels(inp):
    """4-connected non-frame components: list of (r0, c0, r1, c1, cells), reading order."""
    f = _frame(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    res = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] == f or (i, j) in seen:
                continue
            st = [(i, j)]
            seen.add((i, j))
            cells = []
            while st:
                a, b = st.pop()
                cells.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    x, y = a + da, b + db
                    if 0 <= x < h and 0 <= y < w and inp[x][y] != f and (x, y) not in seen:
                        seen.add((x, y))
                        st.append((x, y))
            rs = [a for a, _ in cells]
            cs = [b for _, b in cells]
            res.append((min(rs), min(cs), max(rs), max(cs), cells))
    res.sort()
    return res


def _crop(inp, p):
    r0, c0, r1, c1, _ = p
    return [row[c0:c1 + 1] for row in inp[r0:r1 + 1]]


def _bg(inp):
    # color shared by all panels
    ps = _panels(inp)
    sets = [set(c for r in _crop(inp, p) for c in r) for p in ps]
    s = set.intersection(*sets)
    return min(s)


def _overlay(inp, panels):
    bg = _bg(inp)
    ps = _panels(inp)
    h = max(p[2] - p[0] + 1 for p in ps)
    w = max(p[3] - p[1] + 1 for p in ps)
    g = [[bg] * w for _ in range(h)]
    for p in panels:
        for i, row in enumerate(_crop(inp, p)):
            for j, v in enumerate(row):
                if v != bg:
                    g[i][j] = v
    return g


def only_first(inp, out):
    return _overlay(inp, _panels(inp)[:1])


def only_last(inp, out):
    return _overlay(inp, _panels(inp)[-1:])


def drop_last(inp, out):
    return _overlay(inp, _panels(inp)[:-1])


def frame_border(inp, out):
    f = _frame(inp)
    w = len(out[0])
    return [[f] * (w + 2)] + [[f] + r + [f] for r in out] + [[f] * (w + 2)]


def bg_as_frame(inp, out):
    f, bg = _frame(inp), _bg(inp)
    return [[f if c == bg else c for c in r] for r in out]


def stack_vertical(inp, out):
    bg = _bg(inp)
    g = []
    for p in _panels(inp):
        g += _crop(inp, p)
    return g


def stack_horizontal(inp, out):
    ps = _panels(inp)
    crops = [_crop(inp, p) for p in ps]
    h = max(len(c) for c in crops)
    return [sum((c[i] for c in crops), []) for i in range(h)] if all(len(c) == h for c in crops) else None


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def flipped_lr(inp, out):
    return [r[::-1] for r in out]


def flipped_ud(inp, out):
    return out[::-1]


def keep_commonest_ink(inp, out):
    bg = _bg(inp)
    cnt = Counter(c for r in out for c in r if c != bg)
    if len(cnt) < 2:
        return None
    k = cnt.most_common(1)[0][0]
    return [[c if c == k else bg for c in r] for r in out]


def drop_rarest_ink(inp, out):
    bg = _bg(inp)
    cnt = Counter(c for r in out for c in r if c != bg)
    if len(cnt) < 2:
        return None
    k = min(cnt, key=lambda c: (cnt[c], c))
    return [[bg if c == k else c for c in r] for r in out]


def shift_right_wrap(inp, out):
    return [[r[-1]] + r[:-1] for r in out]


def crop_one_short(inp, out):
    return [r[:-1] for r in out[:-1]]


ALTERNATIVES = [
    ("only the first panel in reading order is drawn", only_first),
    ("only the last panel in reading order is drawn", only_last),
    ("the last panel is left out of the overlay", drop_last),
    ("output is padded with a one-cell frame-color border (crop one cell too wide)", frame_border),
    ("background cells are drawn in the frame color", bg_as_frame),
    ("panels are stacked vertically instead of overlaid", stack_vertical),
    ("panels are placed side by side instead of overlaid", stack_horizontal),
    ("overlay is transposed", transposed),
    ("overlay is mirrored left-right", flipped_lr),
    ("only the most common ink color is kept", keep_commonest_ink),
    ("the rarest ink color is erased", drop_rarest_ink),
    ("overlay is shifted one column to the right with wrap-around", shift_right_wrap),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/7c9b52a0.json').read_text())
    train = task['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, len(train), desc)
