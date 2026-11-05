"""Near-miss readings for 54dc2872.

Rule: each L piece has an arm color (commonest color of its cells) and one tag
cell of another color. If a single mark cell of the tag color exists on the
diagonal beyond the L's bend, the whole L (tag included) moves so that the bend
lands on the mark. The old L and the mark are erased.
"""
import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def _comps(g, bg):
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg or (r, c) in seen:
                continue
            st = [(r, c)]
            seen.add((r, c))
            comp = []
            while st:
                y, x = st.pop()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != bg and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        st.append((ny, nx))
            res.append(comp)
    return res


def _pieces(g):
    """Return (bg, list of piece dicts). Single-cell comps are marks."""
    bg = _bg(g)
    pieces = []
    marks = []
    for comp in _comps(g, bg):
        if len(comp) == 1:
            marks.append(comp[0])
            continue
        cnt = Counter(g[y][x] for y, x in comp)
        arm_col = cnt.most_common(1)[0][0]
        arm = [p for p in comp if g[p[0]][p[1]] == arm_col]
        tag = [p for p in comp if g[p[0]][p[1]] != arm_col]
        if len(tag) != 1:
            continue
        arms = set(arm)
        bend = None
        for y, x in arm:
            h = any((y, x + d) in arms for d in (-1, 1))
            v = any((y + d, x) in arms for d in (-1, 1))
            if h and v:
                bend = (y, x)
        if bend is None:
            continue
        pieces.append(dict(cells=comp, arm=arm, arm_col=arm_col, tag=tag[0],
                           tag_col=g[tag[0][0]][tag[0][1]], bend=bend))
    for p in pieces:
        p['target'] = None
        for m in marks:
            if g[m[0]][m[1]] == p['tag_col']:
                p['target'] = m
    return bg, pieces


def _sgn(v):
    return (v > 0) - (v < 0)


def _render(inp, anchor=lambda p: p['bend'], shift=None, select=lambda i, p: True,
            move_tag=True, erase_old=True, erase_unmatched=False, recolor=False,
            erase_tags=False):
    bg, pieces = _pieces(inp)
    g = [row[:] for row in inp]
    moves = []
    for i, p in enumerate(pieces):
        if p['target'] is None:
            if erase_unmatched:
                for y, x in p['cells']:
                    g[y][x] = bg
            continue
        if not select(i, p):
            continue
        a = anchor(p)
        t = p['target']
        d = (t[0] - a[0], t[1] - a[1])
        if shift is not None:
            d = shift(p, d)
        moves.append((p, d))
    for p, d in moves:
        if erase_old:
            for y, x in p['cells']:
                g[y][x] = bg
        g[p['target'][0]][p['target'][1]] = bg
    h, w = len(g), len(g[0])
    for p, d in moves:
        for y, x in p['cells']:
            v = inp[y][x]
            if (y, x) == p['tag']:
                if not move_tag:
                    g[y][x] = v
                    continue
                if recolor:
                    v = p['arm_col']
            elif recolor:
                v = p['tag_col']
            ny, nx = y + d[0], x + d[1]
            if 0 <= ny < h and 0 <= nx < w:
                g[ny][nx] = v
    if erase_tags:
        for p in pieces:
            y, x = p['tag']
            if g[y][x] == p['tag_col']:
                g[y][x] = bg
    return g


def _farthest(p):
    b = p['bend']
    return max(p['arm'], key=lambda c: abs(c[0] - b[0]) + abs(c[1] - b[1]))


def _topleft(p):
    return min(p['cells'])


def _centroid(p):
    n = len(p['cells'])
    return (round(sum(c[0] for c in p['cells']) / n), round(sum(c[1] for c in p['cells']) / n))


def alt_tag_anchor(inp, out):
    return _render(inp, anchor=lambda p: p['tag'])


def alt_arm_end_anchor(inp, out):
    return _render(inp, anchor=_farthest)


def alt_topleft_anchor(inp, out):
    return _render(inp, anchor=_topleft)


def alt_centroid_anchor(inp, out):
    return _render(inp, anchor=_centroid)


def alt_tag_stays(inp, out):
    return _render(inp, move_tag=False)


def alt_copy_not_move(inp, out):
    return _render(inp, erase_old=False)


def alt_one_short(inp, out):
    def sh(p, d):
        return (d[0] - _sgn(d[0]), d[1] - _sgn(d[1]))
    return _render(inp, shift=sh)


def alt_opposite_direction(inp, out):
    return _render(inp, shift=lambda p, d: (-d[0], -d[1]))


def alt_vertical_only(inp, out):
    return _render(inp, shift=lambda p, d: (d[0], 0))


def alt_horizontal_only(inp, out):
    return _render(inp, shift=lambda p, d: (0, d[1]))


def alt_recolor_to_tag(inp, out):
    return _render(inp, recolor=True)


def alt_unmatched_deleted(inp, out):
    return _render(inp, erase_unmatched=True)


def alt_first_only(inp, out):
    return _render(inp, select=lambda i, p: i == 0)


def alt_no_tags(inp, out):
    return _render(inp, erase_tags=True)


def alt_unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("anchor the tag cell, not the bend, on the mark", alt_tag_anchor),
    ("anchor the far end of the long arm on the mark", alt_arm_end_anchor),
    ("anchor the top-left cell of the piece on the mark", alt_topleft_anchor),
    ("anchor the piece centroid on the mark", alt_centroid_anchor),
    ("arm moves to the mark but the tag cell stays behind", alt_tag_stays),
    ("piece is copied to the mark and the original is not erased", alt_copy_not_move),
    ("piece stops one diagonal step short of the mark", alt_one_short),
    ("piece moves the mirrored way, away from the mark", alt_opposite_direction),
    ("piece moves only vertically toward the mark", alt_vertical_only),
    ("piece moves only horizontally toward the mark", alt_horizontal_only),
    ("moved piece is recolored with the tag color", alt_recolor_to_tag),
    ("pieces without a matching mark are deleted", alt_unmatched_deleted),
    ("only the first piece in reading order moves", alt_first_only),
    ("tag cells are dropped from the output", alt_no_tags),
    ("nothing moves: output equals input", alt_unchanged),
]
# keep within 8-12 readings
ALTERNATIVES = [ALTERNATIVES[i] for i in (0, 1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 14)]


def _valid(g, out):
    if g is None or not isinstance(g, list) or not g:
        return False
    w = len(g[0])
    for r in g:
        if not isinstance(r, list) or len(r) != w:
            return False
        for v in r:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9:
                return False
    return g != out


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/54dc2872.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    # sanity: the true rule reproduces the outputs
    for pr in pairs:
        assert _render(pr['input']) == pr['output'], 'true rule mismatch'
    for desc, fn in ALTERNATIVES:
        n = sum(_valid(fn(pr['input'], pr['output']), pr['output']) for pr in pairs)
        print(n, desc)
