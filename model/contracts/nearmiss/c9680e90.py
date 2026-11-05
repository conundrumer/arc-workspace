import json
from collections import Counter
from pathlib import Path

DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _analyze(g, tail=None):
    """g has a full horizontal divider row. Returns the structure of the pair."""
    h, w = len(g), len(g[0])
    cnt = Counter(c for r in g for c in r)
    bg = cnt.most_common(1)[0][0]
    d = next(r for r in range(h) if len(set(g[r])) == 1 and g[r][0] != bg)
    div = g[d][0]
    others = [c for c in cnt if c not in (bg, div)]
    # the half with heads/tails has three colors; the mark color alone fills the other half
    top = {c for r in range(d) for c in g[r]} - {bg}
    bot = {c for r in range(d + 1, h) for c in g[r]} - {bg}
    if len(top) <= len(bot):
        far, near, side = top, bot, 'bot'
    else:
        far, near, side = bot, top, 'top'
    mark = next(iter(far))
    cells = {c: [(r, k) for r in range(h) for k in range(w) if g[r][k] == c] for c in near}
    # head color: the color whose cells touch the other color's cells in a run start
    best = None
    for hc in near:
        for tc in near:
            if hc == tc:
                continue
            ok = any(0 <= r + dr < h and 0 <= k + dc < w and g[r + dr][k + dc] == tc
                     for (r, k) in cells[hc] for dr, dc in DIRS)
            if ok and (tail is None or tc == tail):
                best = (hc, tc)
    hc, tc = best
    moves = []
    for (r, k) in sorted(cells[hc]):
        for dr, dc in DIRS:
            rr, kk = r + dr, k + dc
            run = []
            while 0 <= rr < h and 0 <= kk < w and g[rr][kk] == tc:
                run.append((rr, kk))
                rr, kk = rr + dr, kk + dc
            if run:
                moves.append(dict(head=(r, k), dir=(dr, dc), run=run))
    marks = cells[mark] if mark in cells else [(r, k) for r in range(h) for k in range(w) if g[r][k] == mark]
    return dict(h=h, w=w, bg=bg, d=d, div=div, hc=hc, tc=tc, mc=mark, moves=moves, marks=marks)


def _sim(g, tail=None, move='full', clear_tail=True, clear_old=True, marks='mirror',
         head_color=None, only_first=False, clear_divider=False):
    a = _analyze(g, tail)
    h, w, bg, d = a['h'], a['w'], a['bg'], a['d']
    res = [r[:] for r in g]
    mv = a['moves'][:1] if only_first else a['moves']
    if marks in ('mirror', 'erase', 'rot180'):
        for (r, k) in a['marks']:
            res[r][k] = bg
    for m in mv:
        hr, hk = m['head']
        run = m['run']
        if clear_tail:
            for (r, k) in run:
                res[r][k] = bg
        if move == 'full':
            end = run[-1]
        elif move == 'one':
            end = run[0]
        elif move == 'none':
            end = m['head']
        else:  # beyond
            end = (run[-1][0] + m['dir'][0], run[-1][1] + m['dir'][1])
            if not (0 <= end[0] < h and 0 <= end[1] < w):
                return None
    for m in mv:
        hr, hk = m['head']
        run = m['run']
        if clear_old:
            res[hr][hk] = bg
    for m in mv:
        run = m['run']
        if move == 'full':
            end = run[-1]
        elif move == 'one':
            end = run[0]
        elif move == 'none':
            end = m['head']
        else:
            end = (run[-1][0] + m['dir'][0], run[-1][1] + m['dir'][1])
        res[end[0]][end[1]] = a['hc'] if head_color is None else (a['tc'] if head_color == 'tail' else head_color)
        if marks == 'mirror':
            res[2 * d - end[0]][end[1]] = a['mc']
        elif marks == 'rot180':
            res[2 * d - end[0]][w - 1 - end[1]] = a['mc']
    if marks == 'stay':
        for (r, k) in a['marks']:
            res[r][k] = a['mc']
    if marks == 'erase':
        pass
    if clear_divider:
        res[d] = [bg] * w
    return res


def _tail(inp, out):
    """The tail color is the one color that is in the input and gone from the output."""
    gone = {c for r in inp for c in r} - {c for r in out for c in r}
    return next(iter(gone))


def _wrap(**kw):
    def f(inp, out):
        vertical = not any(len(set(r)) == 1 and r[0] != Counter(c for q in inp for c in q).most_common(1)[0][0] for r in inp)
        g = _transpose(inp) if vertical else inp
        try:
            res = _sim(g, tail=_tail(inp, out), **kw)
        except Exception:
            return None
        if res is None:
            return None
        return _transpose(res) if vertical else res
    return f


def _mark_shift(inp, out):
    """Twin placed one row too close to the divider (off-by-one mirror)."""
    vertical = not any(len(set(r)) == 1 and r[0] != Counter(c for q in inp for c in q).most_common(1)[0][0] for r in inp)
    g = _transpose(inp) if vertical else inp
    tail = _tail(inp, out)
    a = _analyze(g, tail)
    res = _sim(g, tail=tail)
    if res is None:
        return None
    d = a['d']
    bg = a['bg']
    cells = [(r, k) for r in range(a['h']) for k in range(a['w']) if res[r][k] == a['mc']]
    if any(r == d or r >= a['h'] for r, k in cells):
        return None
    for r, k in cells:
        res[r][k] = bg
    for r, k in cells:
        nr = r + 1 if r < d else r - 1
        res[nr][k] = a['mc']
    return _transpose(res) if vertical else res


ALTERNATIVES = [
    ("marks stay where they were; they do not follow the heads", _wrap(marks='stay')),
    ("marks are deleted instead of moved", _wrap(marks='erase')),
    ("marks placed by 180-degree rotation of the head cell, not a mirror across the divider", _wrap(marks='rot180')),
    ("marks placed one row closer to the divider than the true mirror image", _mark_shift),
    ("head moves only one cell, onto the first tail cell", _wrap(move='one')),
    ("head moves one cell beyond the end of its tail", _wrap(move='beyond')),
    ("head does not move; only the tail is erased (marks follow the unmoved head)", _wrap(move='none')),
    ("head reaches the tail end but the tail cells stay", _wrap(clear_tail=False)),
    ("head reaches the tail end but its old cell is not cleared", _wrap(clear_old=False)),
    ("moved head takes the tail color", _wrap(head_color='tail')),
    ("only the first head in reading order moves", _wrap(only_first=True)),
    ("divider line is erased to background", _wrap(clear_divider=True)),
]


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/c9680e90.json').read_text())
    pairs = task['train']
    # sanity: the full correct simulation reproduces the true output
    for p in pairs:
        inp, out = p['input'], p['output']
        assert _wrap()(inp, out) == out, 'reference simulation mismatch'
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            inp, out = p['input'], p['output']
            g = fn(inp, out)
            if g is None:
                continue
            ok = (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
                  and len({len(r) for r in g}) == 1 and len(g[0]) > 0
                  and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 9 for r in g for c in r))
            if ok and g != out:
                n += 1
        print(f'{n}/{len(pairs)}  {desc}')
