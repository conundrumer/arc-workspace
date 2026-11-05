import json
from collections import Counter
from pathlib import Path


def info(g):
    h, w = len(g), len(g[0])
    bg = Counter(v for r in g for v in r).most_common(1)[0][0]
    rows = [r for r in range(h) if len(set(g[r])) == 1 and g[r][0] != bg]
    cols = [c for c in range(w) if len({g[r][c] for r in range(h)}) == 1 and g[0][c] != bg]
    cr, cc = rows[0], cols[0]
    line = g[cr][0]
    return h, w, bg, cr, cc, line


def objs(g):
    h, w, bg, cr, cc, line = info(g)
    return [(r, c, g[r][c]) for r in range(h) for c in range(w)
            if g[r][c] not in (bg, line)]


def mirror(inp, hor=True, ver=True, diag=True, dr=0, dc=0, axr=None, axc=None):
    """Copy objects over the cross axes onto background cells."""
    h, w, bg, cr, cc, line = info(inp)
    if axr is not None:
        cr = axr
    if axc is not None:
        cc = axc
    o = [row[:] for row in inp]
    for r, c, v in objs(inp):
        targets = []
        if hor:
            targets.append((r, 2 * cc - c + dc))
        if ver:
            targets.append((2 * cr - r + dr, c))
        if diag:
            targets.append((2 * cr - r + dr, 2 * cc - c + dc))
        for rr, c2 in targets:
            if 0 <= rr < h and 0 <= c2 < w and o[rr][c2] == bg:
                o[rr][c2] = v
    return o


def only_lr(inp, out):
    return mirror(inp, True, False, False)


def only_ud(inp, out):
    return mirror(inp, False, True, False)


def only_diag(inp, out):
    return mirror(inp, False, False, True)


def off_by_one_col(inp, out):
    return mirror(inp, dc=1)


def off_by_one_row(inp, out):
    return mirror(inp, dr=-1)


def grid_center(inp, out):
    h, w, bg, cr, cc, line = info(inp)
    o = [row[:] for row in inp]
    for r, c, v in objs(inp):
        for rr, c2 in ((r, w - 1 - c), (h - 1 - r, c), (h - 1 - r, w - 1 - c)):
            if o[rr][c2] == bg:
                o[rr][c2] = v
    return o


def translate_copies(inp, out):
    h, w, bg, cr, cc, line = info(inp)
    o = [row[:] for row in inp]
    for r, c, v in objs(inp):
        for rr, c2 in ((r, (c + cc + 1) % w), ((r + cr + 1) % h, c), ((r + cr + 1) % h, (c + cc + 1) % w)):
            if o[rr][c2] == bg:
                o[rr][c2] = v
    return o


def erase_source(inp, out):
    o = [row[:] for row in out]
    h, w, bg, cr, cc, line = info(inp)
    for r, c, v in objs(inp):
        o[r][c] = bg
    return o


def skip_diag_quadrant(inp, out):
    h, w, bg, cr, cc, line = info(inp)
    o = [row[:] for row in out]
    qs = {((r < cr), (c < cc)) for r, c, v in objs(inp)}
    if len(qs) != 1:
        return None
    sr, sc = next(iter(qs))
    for r in range(h):
        for c in range(w):
            if r != cr and c != cc and (r < cr) != sr and (c < cc) != sc:
                o[r][c] = bg
    return o


def crop_source_quadrant(inp, out):
    h, w, bg, cr, cc, line = info(inp)
    qs = {((r < cr), (c < cc)) for r, c, v in objs(inp)}
    if len(qs) != 1:
        return None
    sr, sc = next(iter(qs))
    rs = range(0, cr) if sr else range(cr + 1, h)
    cs = range(0, cc) if sc else range(cc + 1, w)
    return [[out[r][c] for c in cs] for r in rs]


def copies_in_line_color(inp, out):
    h, w, bg, cr, cc, line = info(inp)
    return [[line if inp[r][c] != out[r][c] else out[r][c] for c in range(w)] for r in range(h)]


def erase_cross(inp, out):
    h, w, bg, cr, cc, line = info(inp)
    o = [row[:] for row in out]
    for r in range(h):
        o[r][cc] = bg
    for c in range(w):
        o[cr][c] = bg
    return o


ALTERNATIVES = [
    ("mirror across the vertical line only (left-right), no vertical or diagonal copies", only_lr),
    ("mirror across the horizontal line only (up-down), no left-right or diagonal copies", only_ud),
    ("only the diagonal (point-reflected) copy, the two axis mirrors are missing", only_diag),
    ("reflection axis off by one column (mirror about the cell next to the vertical line)", off_by_one_col),
    ("reflection axis off by one row (mirror about the cell above the horizontal line)", off_by_one_row),
    ("mirror about the grid center instead of the cross", grid_center),
    ("copies are translated into the other quadrants (wrapped shift) instead of reflected", translate_copies),
    ("original objects erased, only the mirrored copies remain", erase_source),
    ("copies in the two adjacent quadrants only, the diagonal quadrant left empty", skip_diag_quadrant),
    ("output is only the object quadrant of the true output (crop)", crop_source_quadrant),
    ("mirrored copies painted in the line color", copies_in_line_color),
    ("cross lines erased to background", erase_cross),
]


def valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or len(g[0]) == 0:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/60d73be6.json'))
    train = task["train"]
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            try:
                g = fn(p["input"], p["output"])
            except Exception as e:
                print("  error:", repr(e))
                g = None
            if g is not None and valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
