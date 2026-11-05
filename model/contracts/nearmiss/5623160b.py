import json
from collections import Counter
from pathlib import Path

DIRS = [(-1, 0), (0, 1), (1, 0), (0, -1)]


def _setup(inp, out):
    h, w = len(inp), len(inp[0])
    cnt = Counter(v for r in inp for v in r)
    bg = cnt.most_common(1)[0][0]
    cells = {}
    for r in range(h):
        for c in range(w):
            if inp[r][c] != bg:
                cells.setdefault(inp[r][c], set()).add((r, c))
    anchors = set()
    for col, s in cells.items():
        if all(out[r][c] == col for r, c in s) and sum(v == col for row in out for v in row) == len(s):
            anchors.add(col)
    return h, w, bg, cells, anchors


def _dir_for(cellset, inp, anchors, h, w):
    # direction of travel: away from the anchor cell that touches the piece
    for (r, c) in sorted(cellset):
        for dr, dc in DIRS:
            a, b = r + dr, c + dc
            if 0 <= a < h and 0 <= b < w and inp[a][b] in anchors:
                return (-dr, -dc)
    return None


def _margin(cellset, d, h, w):
    dr, dc = d
    best = None
    for r, c in cellset:
        if dr == 1:
            m = h - 1 - r
        elif dr == -1:
            m = r
        elif dc == 1:
            m = w - 1 - c
        else:
            m = c
        best = m if best is None else min(best, m)
    return best


def _components(cellset):
    left, comps = set(cellset), []
    while left:
        st = [left.pop()]
        comp = set(st)
        while st:
            r, c = st.pop()
            for dr, dc in DIRS:
                n = (r + dr, c + dc)
                if n in left:
                    left.discard(n)
                    comp.add(n)
                    st.append(n)
        comps.append(comp)
    return comps


def _pieces(inp, out):
    """list of (color, cellset, direction) for pieces that move."""
    h, w, bg, cells, anchors = _setup(inp, out)
    res = []
    for col, s in cells.items():
        if col in anchors:
            continue
        d = _dir_for(s, inp, anchors, h, w)
        if d:
            res.append((col, s, d))
    return h, w, bg, anchors, res


def _render(inp, out, move, keep_anchor=True, trail=False, only=None):
    """move(col, cellset, d, h, w) -> list of (r,c) new positions or None."""
    h, w, bg, anchors, pcs = _pieces(inp, out)
    g = [[bg] * w for _ in range(h)]
    for r in range(h):
        for c in range(w):
            if inp[r][c] in anchors and keep_anchor:
                g[r][c] = inp[r][c]
    if trail:
        for col, s, d in pcs:
            for r, c in s:
                g[r][c] = col
    for i, (col, s, d) in enumerate(pcs):
        if only is not None and i not in only:
            for r, c in s:
                g[r][c] = col
            continue
        for r, c in move(col, s, d, h, w):
            if 0 <= r < h and 0 <= c < w:
                g[r][c] = col
    return g


def _shift(s, d, k):
    return [(r + d[0] * k, c + d[1] * k) for r, c in s]


def toward_anchor(inp, out):
    return _render(inp, out, lambda col, s, d, h, w: _shift(s, (-d[0], -d[1]), _margin(s, (-d[0], -d[1]), h, w)))


def one_step(inp, out):
    return _render(inp, out, lambda col, s, d, h, w: _shift(s, d, 1))


def short_by_one(inp, out):
    return _render(inp, out, lambda col, s, d, h, w: _shift(s, d, max(_margin(s, d, h, w) - 1, 0)))


def anchor_erased(inp, out):
    return _render(inp, out, lambda col, s, d, h, w: _shift(s, d, _margin(s, d, h, w)), keep_anchor=False)


def copy_with_trail(inp, out):
    return _render(inp, out, lambda col, s, d, h, w: _shift(s, d, _margin(s, d, h, w)), trail=True)


def cellwise_collapse(inp, out):
    def mv(col, s, d, h, w):
        res = []
        for r, c in s:
            res += _shift([(r, c)], d, _margin([(r, c)], d, h, w))
        return res
    return _render(inp, out, mv)


def all_fall_down(inp, out):
    return _render(inp, out, lambda col, s, d, h, w: _shift(s, (1, 0), _margin(s, (1, 0), h, w)))


def turned_direction(inp, out):
    def mv(col, s, d, h, w):
        t = (d[1], -d[0])
        return _shift(s, t, _margin(s, t, h, w))
    return _render(inp, out, mv)


def only_largest_moves(inp, out):
    h, w, bg, anchors, pcs = _pieces(inp, out)
    i = max(range(len(pcs)), key=lambda i: len(pcs[i][1]))
    return _render(inp, out, lambda col, s, d, h, w: _shift(s, d, _margin(s, d, h, w)), only={i})


def common_distance(inp, out):
    h, w, bg, anchors, pcs = _pieces(inp, out)
    k = min(_margin(s, d, h, w) for col, s, d in pcs)
    return _render(inp, out, lambda col, s, d, h_, w_: _shift(s, d, k))


def anchor_side_wrong(inp, out):
    # direction decided by the first anchor contact only for all pieces of the grid
    h, w, bg, anchors, pcs = _pieces(inp, out)
    d0 = pcs[0][2]
    return _render(inp, out, lambda col, s, d, h, w: _shift(s, d0, _margin(s, d0, h, w)))


def mirrored_output(inp, out):
    return [row[::-1] for row in out]


ALTERNATIVES = [
    ("pieces slide toward the anchor instead of away from it", toward_anchor),
    ("pieces move one cell only", one_step),
    ("pieces stop one cell short of the edge", short_by_one),
    ("anchor cells are erased from the output", anchor_erased),
    ("pieces are copied to the edge and leave the original in place", copy_with_trail),
    ("each cell slides to the edge on its own, shapes collapse", cellwise_collapse),
    ("all pieces fall down regardless of anchor", all_fall_down),
    ("pieces slide perpendicular to the anchor direction", turned_direction),
    ("only the largest piece moves", only_largest_moves),
    ("all pieces move by the smallest edge distance among the pieces", common_distance),
    ("all pieces use the direction of the first piece", anchor_side_wrong),
    ("output is horizontally mirrored", mirrored_output),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/5623160b.json'))
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings', len(pairs), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
