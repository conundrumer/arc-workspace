import json
from collections import Counter
from pathlib import Path


def _blocks(g):
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if g[r][c] == 0 or (r, c) in seen:
                continue
            st = [(r, c)]
            seen.add((r, c))
            cells = []
            while st:
                y, x = st.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != 0 and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        st.append((ny, nx))
            ys = [p[0] for p in cells]
            xs = [p[1] for p in cells]
            res.append((min(ys), min(xs), max(ys) + 1, max(xs) + 1, cells))
    return res


def _parse(inp):
    bl = _blocks(inp)
    canvas = None
    for b in bl:
        if len({inp[y][x] for y, x in b[4]}) == 1:
            canvas = b
    others = [b for b in bl if b is not canvas]
    fill = inp[canvas[0]][canvas[1]]
    cols = [{inp[y][x] for y, x in b[4]} for b in others]
    ink = (cols[0] & cols[1]) - {fill}
    ink = next(iter(ink)) if ink else None
    if ink is None:
        # shared color of the two small blocks
        ink = next(iter(cols[0] & cols[1]))
    stamp = plan = None
    for b, cs in zip(others, cols):
        if fill in cs:
            plan = b
        else:
            stamp = b
    sub = lambda b: [row[b[1]:b[3]] for row in inp[b[0]:b[2]]]
    blank = next(iter({inp[y][x] for y, x in stamp[4]} - {ink}))
    return dict(fill=fill, ink=ink, blank=blank, canvas=canvas, stamp=sub(stamp), plan=sub(plan))


def _pixels(P, shape=None):
    """Plan reduced to one cell per tile; True where the pixel is ink."""
    plan = P['plan']
    ph, pw = len(plan), len(plan[0])
    th = (P['canvas'][2] - P['canvas'][0]) // len(P['stamp'])
    tw = (P['canvas'][3] - P['canvas'][1]) // len(P['stamp'][0])
    sy, sx = ph // th, pw // tw
    return [[plan[a * sy][b * sx] == P['ink'] for b in range(tw)] for a in range(th)], th, tw


def _render(P, pix, foot=None, bg=None, inkc=None, invert=False):
    st = P['stamp']
    sh, sw = len(st), len(st[0])
    th, tw = len(pix), len(pix[0])
    bg = P['fill'] if bg is None else bg
    inkc = P['ink'] if inkc is None else inkc
    if foot is None:
        foot = [[v == P['ink'] for v in row] for row in st]
    out = [[bg] * (tw * sw) for _ in range(th * sh)]
    for a in range(th):
        for b in range(tw):
            if pix[a][b] != invert:
                for i in range(sh):
                    for j in range(sw):
                        if foot[i][j]:
                            out[a * sh + i][b * sw + j] = inkc
    return out


def _true(inp):
    P = _parse(inp)
    pix, _, _ = _pixels(P)
    return P, pix


def a_inverted_footprint(inp, out):
    P, pix = _true(inp)
    foot = [[v == P['blank'] for v in row] for row in P['stamp']]
    return _render(P, pix, foot=foot)


def a_inverted_marking(inp, out):
    P, pix = _true(inp)
    return _render(P, pix, invert=True)


def a_mirrored_plan(inp, out):
    P, pix = _true(inp)
    return _render(P, [r[::-1] for r in pix])


def a_flipped_plan_vertical(inp, out):
    P, pix = _true(inp)
    return _render(P, pix[::-1])


def a_mirrored_stamp(inp, out):
    P, pix = _true(inp)
    foot = [[v == P['ink'] for v in row[::-1]] for row in P['stamp']]
    return _render(P, pix, foot=foot)


def a_all_tiles_inked(inp, out):
    P, pix = _true(inp)
    return _render(P, [[True] * len(pix[0]) for _ in pix])


def a_single_tile(inp, out):
    P, pix = _true(inp)
    sh, sw = len(P['stamp']), len(P['stamp'][0])
    return [row[:sw] for row in out[:sh]]


def a_last_tile_column_dropped(inp, out):
    P, pix = _true(inp)
    sw = len(P['stamp'][0])
    return [row[:-sw] for row in out]


def a_ink_drawn_in_stamp_blank_color(inp, out):
    P, pix = _true(inp)
    return _render(P, pix, inkc=P['blank'])


def a_background_instead_of_fill(inp, out):
    P, pix = _true(inp)
    return _render(P, pix, bg=0)


def a_stamp_copied_verbatim(inp, out):
    P, pix = _true(inp)
    st = P['stamp']
    sh, sw = len(st), len(st[0])
    res = [[P['fill']] * (len(pix[0]) * sw) for _ in range(len(pix) * sh)]
    for a in range(len(pix)):
        for b in range(len(pix[0])):
            if pix[a][b]:
                for i in range(sh):
                    for j in range(sw):
                        res[a * sh + i][b * sw + j] = st[i][j]
    return res


def a_plan_unscaled_corner(inp, out):
    P, pix = _true(inp)
    plan = P['plan']
    th, tw = len(pix), len(pix[0])
    wrong = [[plan[a][b] == P['ink'] for b in range(tw)] for a in range(th)]
    return _render(P, wrong)


def a_plan_read_column_major(inp, out):
    P, pix = _true(inp)
    th, tw = len(pix), len(pix[0])
    flat = [pix[a][b] for a in range(th) for b in range(tw)]
    wrong = [[False] * tw for _ in range(th)]
    k = 0
    for b in range(tw):
        for a in range(th):
            wrong[a][b] = flat[k]
            k += 1
    return _render(P, wrong)


_RAW = [
    ("Footprint taken from the stamp's blank color instead of its ink color", a_inverted_footprint),
    ("Marked and unmarked plan pixels swapped: stamp drawn where the plan is fill", a_inverted_marking),
    ("Plan read mirrored left to right", a_mirrored_plan),
    ("Plan read flipped top to bottom", a_flipped_plan_vertical),
    ("Stamp footprint drawn mirrored left to right", a_mirrored_stamp),
    ("Plan ignored: every tile gets the footprint", a_all_tiles_inked),
    ("Output is a single stamp-sized tile", a_single_tile),
    ("Canvas tiled one tile column short", a_last_tile_column_dropped),
    ("Footprint drawn in the stamp's other color", a_ink_drawn_in_stamp_blank_color),
    ("Output background is 0 instead of the canvas color", a_background_instead_of_fill),
    ("Whole stamp, both colors, copied into marked tiles", a_stamp_copied_verbatim),
    ("Plan pixels read unscaled from its top-left corner", a_plan_unscaled_corner),
    ("Plan pixels placed onto the tiles in column-major order", a_plan_read_column_major),
]


def _guard(f):
    def g(inp, out):
        r = f(inp, out)
        if r is None or r == out:
            return None
        return r
    return g


ALTERNATIVES = [(d, _guard(f)) for d, f in _RAW[:12]]


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/5833af48.json'))
    train = task['train']
    print('pairs', len(train))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in train:
            r = f(p['input'], p['output'])
            if (r is not None and r != p['output'] and isinstance(r, list) and r
                    and all(isinstance(row, list) and len(row) == len(r[0]) for row in r)
                    and all(isinstance(v, int) and 0 <= v <= 9 for row in r for v in row)):
                n += 1
        print(n, desc)
    # sanity: the true rendering matches
    for p in train:
        P, pix = _true(p['input'])
        assert _render(P, pix) == p['output']
