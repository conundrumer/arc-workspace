import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(c for r in inp for c in r).most_common(1)[0][0]


def _changed(inp, out):
    return [(r, c) for r in range(len(out)) for c in range(len(out[0])) if out[r][c] != inp[r][c]]


def _info(inp, out):
    bg = _bg(inp)
    ch = _changed(inp, out)
    rows = [r for r, _ in ch]
    cols = [c for _, c in ch]
    r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
    line_rows = (r0, r1)
    line = Counter(out[r0][c] for r, c in ch if r == r0).most_common(1)[0][0]
    rail = Counter(out[r][c] for r, c in ch if c == c0).most_common(1)[0][0]
    cnt = Counter(c for r in inp for c in r if c != bg)
    block = cnt.most_common(1)[0][0]
    return dict(bg=bg, ch=ch, r0=r0, r1=r1, c0=c0, c1=c1, line_rows=line_rows,
                line=line, rail=rail, block=block)


def _revert(inp, out, cells):
    g = [row[:] for row in out]
    for r, c in cells:
        g[r][c] = inp[r][c]
    return g


def no_line(inp, out):
    i = _info(inp, out)
    return _revert(inp, out, [(r, c) for r, c in i['ch'] if r in i['line_rows'] and out[r][c] == i['line']])


def no_rail(inp, out):
    i = _info(inp, out)
    return _revert(inp, out, [(r, c) for r, c in i['ch'] if out[r][c] == i['rail']])


def rail_wrong_color(inp, out):
    i = _info(inp, out)
    g = [row[:] for row in out]
    for r, c in i['ch']:
        if out[r][c] == i['rail']:
            g[r][c] = i['line']
    return g


def line_wrong_color(inp, out):
    i = _info(inp, out)
    g = [row[:] for row in out]
    for r, c in i['ch']:
        if r in i['line_rows'] and out[r][c] == i['line']:
            g[r][c] = i['rail']
    return g


def flip_v(inp, out):
    return [row[:] for row in out[::-1]]


def flip_h(inp, out):
    return [row[::-1] for row in out]


def rail_off_by_one(inp, out):
    i = _info(inp, out)
    g = [row[:] for row in out]
    cells = [(r, c) for r, c in i['ch'] if out[r][c] == i['rail'] and c in (i['c0'], i['c1'])]
    for r, c in cells:
        g[r][c] = inp[r][c]
    for r, c in cells:
        g[r][c + 1 if c == i['c0'] else c - 1] = i['rail']
    return g


def no_block_copy(inp, out):
    i = _info(inp, out)
    return _revert(inp, out, [(r, c) for r, c in i['ch'] if out[r][c] == i['block']])


def one_repeat_only(inp, out):
    i = _info(inp, out)
    arm = [(r, c) for r, c in i['ch']
           if r not in i['line_rows'] and out[r][c] not in (i['block'], i['rail'])]
    cols = sorted({c for _, c in arm})
    return _revert(inp, out, [(r, c) for r, c in arm if c != cols[0]])


def one_side_only(inp, out):
    i = _info(inp, out)
    mid = (i['r0'] + i['r1']) // 2
    return _revert(inp, out, [(r, c) for r, c in i['ch'] if r > mid])


def drop_last_row(inp, out):
    return [row[:] for row in out[:-1]]


def solid_fill(inp, out):
    i = _info(inp, out)
    g = [row[:] for row in out]
    for r in range(i['r0'] + 1, i['r1']):
        for c in range(i['c0'], i['c1'] + 1):
            if g[r][c] == i['bg']:
                g[r][c] = i['rail']
    return g


ALTERNATIVES = [
    ("the plain line one cell outside the arms is not drawn", no_line),
    ("the rail along the far side of the figure is not drawn", no_rail),
    ("the rail is drawn in the arm line color", rail_wrong_color),
    ("the plain outer line is drawn in the rail color", line_wrong_color),
    ("the figure is drawn flipped top to bottom", flip_v),
    ("the figure is drawn flipped left to right", flip_h),
    ("the rail columns sit one cell too far inward", rail_off_by_one),
    ("the block is not copied to the other corner", no_block_copy),
    ("the arms repeat only once, not over the full span", one_repeat_only),
    ("only the upper half of the figure is drawn", one_side_only),
    ("the output is cut one row short", drop_last_row),
    ("the area inside the rails is filled with the rail color", solid_fill),
]


def _valid(g, true):
    if not isinstance(g, list) or not g or not isinstance(g[0], list):
        return False
    w = len(g[0])
    if any(not isinstance(r, list) or len(r) != w for r in g):
        return False
    if any(type(c) is not int or not 0 <= c <= 9 for r in g for c in r):
        return False
    return g != true


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/34cfa167.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p['input'], p['output'])
            except Exception as e:
                print('  error', f.__name__, e)
                g = None
            if g is not None and _valid(g, p['output']):
                n += 1
        print(f'{n}/{len(pairs)}  {desc}')
