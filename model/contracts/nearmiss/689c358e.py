import json
from collections import Counter
from pathlib import Path


def shapes(inp):
    """Return list of dicts: color, center (r, c), bbox, pointing side."""
    n, m = len(inp), len(inp[0])
    frame = inp[0][0]
    inner = Counter(inp[r][c] for r in range(1, n - 1) for c in range(1, m - 1))
    bg = inner.most_common(1)[0][0]
    cells = {}
    for r in range(1, n - 1):
        for c in range(1, m - 1):
            v = inp[r][c]
            if v != bg and v != frame:
                cells.setdefault(v, set()).add((r, c))
    res = []
    for col, cs in sorted(cells.items()):
        center = None
        for (r, c) in sorted(cs):
            if all((r + dr, c + dc) in cs for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                center = (r, c)
                break
        if center is None:
            continue
        r0 = min(r for r, _ in cs); r1 = max(r for r, _ in cs)
        c0 = min(c for _, c in cs); c1 = max(c for _, c in cs)
        cr, cc = center
        h, w = r1 - r0 + 1, c1 - c0 + 1
        if h >= w:
            vertical = True
            side = 'U' if cr - r0 < r1 - cr else 'D'
        else:
            vertical = False
            side = 'L' if cc - c0 < c1 - cc else 'R'
        res.append(dict(color=col, center=center, bbox=(r0, r1, c0, c1),
                        vertical=vertical, side=side, bg=bg, frame=frame))
    return res


def border_cell(sh, side, n, m, inset=0, shift=0):
    r, c = sh['center']
    if side == 'U':
        return (0 + inset, c + shift)
    if side == 'D':
        return (n - 1 - inset, c + shift)
    if side == 'L':
        return (r + shift, 0 + inset)
    return (r + shift, m - 1 - inset)


OPP = {'U': 'D', 'D': 'U', 'L': 'R', 'R': 'L'}


def put(g, rc, v):
    r, c = rc
    if 0 <= r < len(g) and 0 <= c < len(g[0]):
        g[r][c] = v


def mark(inp, near_col=True, far_val=0, swap=False, only=None, inset=0, shift=0,
         perp=False, both_color=False, skip_far=False, skip_near=False):
    g = [row[:] for row in inp]
    n, m = len(g), len(g[0])
    sh_list = shapes(inp)
    if not sh_list:
        return None
    for sh in sh_list:
        if only is not None and not only(sh):
            continue
        side = sh['side']
        if perp:
            side = 'L' if sh['vertical'] else 'U'
        far = OPP[side]
        if swap:
            side, far = far, side
        col = sh['color']
        fv = col if both_color else (sh['bg'] if far_val == 'bg' else far_val)
        if not skip_near:
            put(g, border_cell(sh, side, n, m, inset, shift), col)
        if not skip_far:
            put(g, border_cell(sh, far, n, m, inset, shift), fv)
    return g


def reversed_direction(inp, out):
    return mark(inp, swap=True)


def both_colored(inp, out):
    return mark(inp, both_color=True)


def no_far_mark(inp, out):
    return mark(inp, skip_far=True)


def no_near_mark(inp, out):
    return mark(inp, skip_near=True)


def perpendicular_axis(inp, out):
    return mark(inp, perp=True)


def shifted_line(inp, out):
    return mark(inp, shift=1)


def inset_marks(inp, out):
    return mark(inp, inset=1)


def far_is_background(inp, out):
    return mark(inp, far_val='bg')


def only_vertical(inp, out):
    return mark(inp, only=lambda s: s['vertical'])


def only_horizontal(inp, out):
    return mark(inp, only=lambda s: not s['vertical'])


def fill_to_border(inp, out):
    g = mark(inp)
    if g is None:
        return None
    n, m = len(g), len(g[0])
    for sh in shapes(inp):
        r, c = sh['center']
        r0, r1, c0, c1 = sh['bbox']
        side = sh['side']
        if side == 'U':
            cells = [(i, c) for i in range(1, r0)]
        elif side == 'D':
            cells = [(i, c) for i in range(r1 + 1, n - 1)]
        elif side == 'L':
            cells = [(r, j) for j in range(1, c0)]
        else:
            cells = [(r, j) for j in range(c1 + 1, m - 1)]
        for rc in cells:
            if inp[rc[0]][rc[1]] == sh['bg']:
                put(g, rc, sh['color'])
    return g


def crop_interior(inp, out):
    return [row[1:-1] for row in out[1:-1]]


ALTERNATIVES = [
    ("color goes on the far side and 0 on the near side (direction reversed)", reversed_direction),
    ("both border ends of the line get the shape color, no 0", both_colored),
    ("only the near border cell is colored; the far end is left unchanged", no_far_mark),
    ("only the far border cell is set to 0; the near end is left unchanged", no_near_mark),
    ("marks go on the short-arm axis (perpendicular), color on left/top, 0 on right/bottom", perpendicular_axis),
    ("marks are placed one row/column off the cross center line", shifted_line),
    ("marks are placed one cell inside the border frame, on the interior edge", inset_marks),
    ("the far end gets the interior background color instead of 0", far_is_background),
    ("only vertical-pointing shapes are marked", only_vertical),
    ("only horizontal-pointing shapes are marked", only_horizontal),
    ("the whole line from the shape to the near border is filled with the color", fill_to_border),
    ("output is the interior with the frame cropped away", crop_interior),
]


def _valid(g, ref):
    if g is None or not isinstance(g, list) or not g:
        return False
    if not all(isinstance(r, list) and len(r) == len(g[0]) for r in g):
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != ref


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/689c358e.json').read_text())
    pairs = task['train']
    print(len(ALTERNATIVES), 'readings,', len(pairs), 'pairs')
    for desc, fn in ALTERNATIVES:
        counts = [int(_valid(fn(p['input'], p['output']), p['output'])) for p in pairs]
        print(sum(counts), counts, desc)
