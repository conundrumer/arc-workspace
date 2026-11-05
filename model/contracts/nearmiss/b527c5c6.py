import json
from collections import Counter
from pathlib import Path


def bars_of(inp):
    h, w = len(inp), len(inp[0])
    seen = set()
    bars = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] == 0 or (r, c) in seen:
                continue
            stack, cells = [(r, c)], []
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and inp[ny][nx] != 0 and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            cnt = Counter(inp[y][x] for y, x in cells)
            body = cnt.most_common(1)[0][0]
            mark_c = min(cnt, key=lambda k: cnt[k])
            mark = next(p for p in cells if inp[p[0]][p[1]] == mark_c)
            rs = [y for y, _ in cells]
            cs = [x for _, x in cells]
            r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
            hh, ww = r1 - r0 + 1, c1 - c0 + 1
            if ww > hh:
                side = 'up' if mark[0] == r0 else 'down'
            else:
                side = 'left' if mark[1] == c0 else 'right'
            bars.append(dict(box=(r0, r1, c0, c1), mark=mark, body=body, mcol=mark_c,
                             side=side, t=min(hh, ww), long=max(hh, ww),
                             horiz=ww > hh, area=hh * ww))
    return bars


VEC = {'up': (-1, 0), 'down': (1, 0), 'left': (0, -1), 'right': (0, 1)}
OPP = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}


def render(inp, bars, dirs=None, half=None, core=None, cc=None, fc=None,
           length=None, flanks=True, only=None):
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for b in bars:
        if only is not None and not only(b):
            continue
        r0, r1, c0, c1 = b['box']
        ds = dirs(b) if dirs else [b['side']]
        hw = half(b) if half else b['t'] - 1
        ccol = cc(b) if cc else b['mcol']
        fcol = fc(b) if fc else b['body']
        for d in ds:
            dy, dx = VEC[d]
            vert = dy != 0
            line = core(b, d) if core else (b['mark'][1] if vert else b['mark'][0])
            # first cell outside bar
            start = (r1 + 1 if dy > 0 else r0 - 1) if vert else (c1 + 1 if dx > 0 else c0 - 1)
            n = 0
            p = start
            while 0 <= p < (h if vert else w):
                if length is not None and n >= length(b):
                    break
                offs = range(-hw, hw + 1) if flanks else [0]
                for o in offs:
                    q = line + o
                    y, x = (p, q) if vert else (q, p)
                    if 0 <= y < h and 0 <= x < w:
                        g[y][x] = ccol if o == 0 else fcol
                p += dy if vert else dx
                n += 1
    return g


def alt_opposite(inp, out):
    return render(inp, bars_of(inp), dirs=lambda b: [OPP[b['side']]])


def alt_wide(inp, out):
    return render(inp, bars_of(inp), half=lambda b: b['t'])


def alt_narrow(inp, out):
    return render(inp, bars_of(inp), half=lambda b: max(b['t'] - 2, 0))


def alt_core_only(inp, out):
    return render(inp, bars_of(inp), flanks=False)


def alt_all_body(inp, out):
    return render(inp, bars_of(inp), cc=lambda b: b['body'])


def alt_flank_mark(inp, out):
    return render(inp, bars_of(inp), fc=lambda b: b['mcol'])


def alt_both_ways(inp, out):
    return render(inp, bars_of(inp), dirs=lambda b: [b['side'], OPP[b['side']]])


def alt_along_axis(inp, out):
    def d(b):
        r0, r1, c0, c1 = b['box']
        m = b['mark']
        if b['horiz']:
            return ['left' if m[1] - c0 <= c1 - m[1] else 'right']
        return ['up' if m[0] - r0 <= r1 - m[0] else 'down']

    def core(b, dd):
        return b['mark'][1] if dd in ('left', 'right') and False else (
            b['mark'][0] if dd in ('left', 'right') else b['mark'][1])
    return render(inp, bars_of(inp), dirs=d, core=core)


def alt_largest_only(inp, out):
    bars = bars_of(inp)
    m = max(b['area'] for b in bars)
    return render(inp, bars, only=lambda b: b['area'] == m)


def alt_centered(inp, out):
    def core(b, d):
        r0, r1, c0, c1 = b['box']
        return (c0 + c1) // 2 if d in ('up', 'down') else (r0 + r1) // 2
    return render(inp, bars_of(inp), core=core)


def alt_short_beam(inp, out):
    return render(inp, bars_of(inp), length=lambda b: b['t'])


def alt_half_mark_line_only_body(inp, out):
    # beam drawn with width t (full thickness, core offset to one side): flanks only on one side
    bars = bars_of(inp)
    g = render(inp, bars, flanks=False)
    for b in bars:
        r0, r1, c0, c1 = b['box']
        dy, dx = VEC[b['side']]
        h, w = len(inp), len(inp[0])
        vert = dy != 0
        p = (r1 + 1 if dy > 0 else r0 - 1) if vert else (c1 + 1 if dx > 0 else c0 - 1)
        while 0 <= p < (h if vert else w):
            for o in range(1, b['t']):
                q = (b['mark'][1] if vert else b['mark'][0]) + o
                y, x = (p, q) if vert else (q, p)
                if 0 <= y < h and 0 <= x < w:
                    g[y][x] = b['body']
            p += dy if vert else dx
    return g


ALTERNATIVES = [
    ("beam leaves the side opposite the marked side", alt_opposite),
    ("flanks one cell wider than the correct width (as wide as the thickness)", alt_wide),
    ("flanks one cell narrower than the correct width", alt_narrow),
    ("beam is only the one-cell center line, with no flanks", alt_core_only),
    ("whole beam, center line included, takes the bar color", alt_all_body),
    ("flanks take the mark color instead of the bar color", alt_flank_mark),
    ("beam leaves both the marked side and the opposite side", alt_both_ways),
    ("beam runs along the bar's long axis toward the nearer end, from the mark's line", alt_along_axis),
    ("only the largest bar shoots a beam", alt_largest_only),
    ("beam is centered on the bar's middle line instead of the mark's line", alt_centered),
    ("beam stops after as many cells as the bar is thick instead of reaching the grid edge", alt_short_beam),
    ("flanks only on one side of the center line", alt_half_mark_line_only_body),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and all(len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/b527c5c6.json'))
    train = task['train']
    # sanity: reference renderer reproduces the true outputs
    ok = all(render(p['input'], bars_of(p['input'])) == p['output'] for p in train)
    print('reference render matches outputs:', ok)
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g) and g != p['output']:
                n += 1
        print(f'{n}/{len(train)}  {desc}')
