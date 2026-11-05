import json
from pathlib import Path


def parse(inp):
    d = next(i for i, r in enumerate(inp) if all(v == 5 for v in r))
    top = inp[:d]
    bottom = [row[:] for row in inp[d + 1:]]
    cells = lambda g, pred: [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if pred(v)]
    pay_col = next(v for row in top for v in row if v not in (0, 1, 2, 5))
    pc = cells(top, lambda v: v == pay_col)
    pr0, pr1 = min(r for r, _ in pc), max(r for r, _ in pc)
    pc0, pc1 = min(c for _, c in pc), max(c for _, c in pc)
    payload = [[top[r][c] for c in range(pc0, pc1 + 1)] for r in range(pr0, pr1 + 1)]
    ch = cells(bottom, lambda v: v != 0)
    cr0, cr1 = min(r for r, _ in ch), max(r for r, _ in ch)
    cc0, cc1 = min(c for _, c in ch), max(c for _, c in ch)
    ac = cells(top, lambda v: v == 2)
    rows = sorted(set(r for r, _ in ac))
    cnt = [sum(1 for r, _ in ac if r == x) for x in rows]
    heading = 'down' if cnt[0] > cnt[-1] else 'up'
    return d, bottom, payload, (cr0, cr1, cc0, cc1), heading


def stamp(base, payload, r0, c0, color=None):
    g = [row[:] for row in base]
    for i, prow in enumerate(payload):
        for j, v in enumerate(prow):
            r, c = r0 + i, c0 + j
            if v and 0 <= r < len(g) and 0 <= c < len(g[0]):
                g[r][c] = v if color is None else color
    return g


def correct_r0(info):
    d, bottom, payload, (cr0, cr1, cc0, cc1), heading = info
    return cr0 - len(payload) if heading == 'up' else cr1 + 1


def opp_r0(info):
    d, bottom, payload, (cr0, cr1, cc0, cc1), heading = info
    return cr1 + 1 if heading == 'up' else cr0 - len(payload)


def wrong_side(inp, out):
    i = parse(inp)
    return stamp(i[1], i[2], opp_r0(i), i[3][2])


def gap_row(inp, out):
    i = parse(inp)
    r0 = correct_r0(i) + (-1 if i[4] == 'up' else 1)
    return stamp(i[1], i[2], r0, i[3][2])


def chart_color(inp, out):
    i = parse(inp)
    return stamp(i[1], i[2], correct_r0(i), i[3][2], color=1)


def on_chart(inp, out):
    i = parse(inp)
    return stamp(i[1], i[2], i[3][0], i[3][2])


def unchanged(inp, out):
    return [row[:] for row in inp]


def flipped_payload(inp, out):
    i = parse(inp)
    fl = [row[:] for row in reversed(i[2])]
    if fl == i[2]:
        return None
    return stamp(i[1], fl, correct_r0(i), i[3][2])


def left_side(inp, out):
    i = parse(inp)
    return stamp(i[1], i[2], i[3][0], i[3][2] - len(i[2][0]))


def no_chart(inp, out):
    i = parse(inp)
    blank = [[0] * len(r) for r in i[1]]
    return stamp(blank, i[2], correct_r0(i), i[3][2])


def both_sides(inp, out):
    i = parse(inp)
    g = stamp(i[1], i[2], correct_r0(i), i[3][2])
    return stamp(g, i[2], opp_r0(i), i[3][2])


def no_crop(inp, out):
    i = parse(inp)
    g = stamp(i[1], i[2], correct_r0(i), i[3][2])
    return [row[:] for row in inp[:i[0] + 1]] + g


def crop_with_divider(inp, out):
    i = parse(inp)
    g = stamp(i[1], i[2], correct_r0(i), i[3][2])
    return [row[:] for row in inp[i[0]:i[0] + 1]] + g


def overlap_one(inp, out):
    i = parse(inp)
    r0 = correct_r0(i) + (1 if i[4] == 'up' else -1)
    return stamp(i[1], i[2], r0, i[3][2])


ALTERNATIVES = [
    ("payload placed on the side of the chart opposite the arrow's heading", wrong_side),
    ("payload placed one row away from the chart, leaving a gap", gap_row),
    ("payload recolored to the chart's color", chart_color),
    ("payload stamped onto the chart's own position instead of beside it", on_chart),
    ("input returned unchanged", unchanged),
    ("payload flipped vertically before placing (only where it is not symmetric)", flipped_payload),
    ("payload placed to the left of the chart instead of in the heading direction", left_side),
    ("chart dropped, only the payload shown in its place", no_chart),
    ("payload attached on both sides of the chart", both_sides),
    ("whole input kept, top panels not cropped away", no_crop),
    ("crop starts at the divider row, one row too high", crop_with_divider),
    ("payload placed overlapping the chart by one row", overlap_one),
]


def valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/4c177718.json'))
    pairs = task['train']
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p['input'], p['output'])
            if g is not None and valid(g) and g != p['output']:
                n += 1
        print(n, desc)
