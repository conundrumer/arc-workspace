import json
from pathlib import Path

DIRS4 = [(0, 1), (0, -1), (1, 0), (-1, 0)]


def _copy(g):
    return [list(r) for r in g]


def _centers(inp):
    h, w = len(inp), len(inp[0])
    res = []
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0:
                continue
            ok = True
            for dr, dc in DIRS4:
                rr, cc = r + dr, c + dc
                if not (0 <= rr < h and 0 <= cc < w and inp[rr][cc] == 2):
                    ok = False
            if ok:
                res.append((r, c))
    return res


def _link_cells(inp, out):
    """Cells of the true output that are link cells (1 in out, 0 in inp)."""
    return [(r, c) for r in range(len(out)) for c in range(len(out[0]))
            if out[r][c] == 1 and inp[r][c] == 0]


def wrong_link_color(inp, out):
    g = _copy(out)
    for r, c in _link_cells(inp, out):
        g[r][c] = 8
    return g


def _split_links(inp, out):
    """Classify each link cell by walking its run along rows and columns."""
    h, w = len(out), len(out[0])
    horiz, vert = set(), set()
    cs = _centers(inp)
    # link runs are between two centers in the same row or column
    for i, (r1, c1) in enumerate(cs):
        for (r2, c2) in cs[i + 1:]:
            if r1 == r2:
                lo, hi = sorted((c1, c2))
                cells = [(r1, c) for c in range(lo + 1, hi) if inp[r1][c] == 0]
                if cells and all(out[r][c] == 1 for r, c in cells):
                    horiz.update(cells)
            if c1 == c2:
                lo, hi = sorted((r1, r2))
                cells = [(r, c1) for r in range(lo + 1, hi) if inp[r][c1] == 0]
                if cells and all(out[r][c] == 1 for r, c in cells):
                    vert.update(cells)
    return horiz, vert


def vertical_missing(inp, out):
    horiz, vert = _split_links(inp, out)
    if not vert:
        return None
    g = _copy(out)
    for r, c in vert - horiz:
        g[r][c] = 0
    return g


def horizontal_missing(inp, out):
    horiz, vert = _split_links(inp, out)
    if not horiz:
        return None
    g = _copy(out)
    for r, c in horiz - vert:
        g[r][c] = 0
    return g


def span_overwrites_ring(inp, out):
    """Link drawn through the ring cells between centers too."""
    horiz, vert = _split_links(inp, out)
    g = _copy(out)
    cs = _centers(inp)
    for i, (r1, c1) in enumerate(cs):
        for (r2, c2) in cs[i + 1:]:
            if r1 == r2:
                lo, hi = sorted((c1, c2))
                if all((r1, c) in horiz or inp[r1][c] == 2 for c in range(lo + 1, hi)):
                    for c in range(lo + 1, hi):
                        g[r1][c] = 1
            if c1 == c2:
                lo, hi = sorted((r1, r2))
                if all((r, c1) in vert or inp[r][c1] == 2 for r in range(lo + 1, hi)):
                    for r in range(lo + 1, hi):
                        g[r][c1] = 1
    return g


def center_filled(inp, out):
    g = _copy(out)
    for r, c in _centers(inp):
        g[r][c] = 1
    return g


def rays_to_border(inp, out):
    """Each center shoots a line to the grid edge, with no partner needed."""
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r, c in _centers(inp):
        for dr, dc in DIRS4:
            rr, cc = r + dr, c + dc
            while 0 <= rr < h and 0 <= cc < w:
                if inp[rr][cc] == 0:
                    g[rr][cc] = 1
                rr += dr
                cc += dc
    return g


def ring_to_ring_fill(inp, out):
    """Any bg cell with a 2 on both sides (any distance) in a row or column gets 1."""
    h, w = len(inp), len(inp[0])
    g = _copy(inp)
    for r in range(h):
        for c in range(w):
            if inp[r][c] != 0:
                continue
            row = any(inp[r][x] == 2 for x in range(c)) and any(inp[r][x] == 2 for x in range(c + 1, w))
            col = any(inp[x][c] == 2 for x in range(r)) and any(inp[x][c] == 2 for x in range(r + 1, h))
            if row or col:
                g[r][c] = 1
    return g


def link_shortened(inp, out):
    """Each link stops one cell short of the ring on both ends."""
    horiz, vert = _split_links(inp, out)
    g = _copy(out)
    for r, c in horiz:
        if (r, c - 1) not in horiz or (r, c + 1) not in horiz:
            g[r][c] = 0
    for r, c in vert:
        if (r - 1, c) not in vert or (r + 1, c) not in vert:
            g[r][c] = 0
    return g


def only_first_link_per_line(inp, out):
    """Only the first pair of centers on each row or column is linked."""
    cs = _centers(inp)
    g = _copy(inp)
    rows, cols = {}, {}
    for r, c in cs:
        rows.setdefault(r, []).append(c)
        cols.setdefault(c, []).append(r)
    horiz, vert = _split_links(inp, out)
    for r, v in rows.items():
        v = sorted(v)
        if len(v) >= 2:
            for c in range(v[0] + 1, v[1]):
                if (r, c) in horiz:
                    g[r][c] = 1
    for c, v in cols.items():
        v = sorted(v)
        if len(v) >= 2:
            for r in range(v[0] + 1, v[1]):
                if (r, c) in vert:
                    g[r][c] = 1
    return g


def ring_recolored(inp, out):
    """Links are right, and the ring cells are recolored to the link color."""
    g = _copy(out)
    for r in range(len(g)):
        for c in range(len(g[0])):
            if inp[r][c] == 2:
                g[r][c] = 1
    return g


def unchanged_input(inp, out):
    return _copy(inp)


ALTERNATIVES = [
    ("link cells drawn in color 8 instead of 1", wrong_link_color),
    ("only horizontal links drawn; vertical links dropped", vertical_missing),
    ("only vertical links drawn; horizontal links dropped", horizontal_missing),
    ("link also overwrites the ring cells between centers", span_overwrites_ring),
    ("center cells filled with 1 as well", center_filled),
    ("each center shoots lines to the grid border without needing a partner", rays_to_border),
    ("any 0 cell with a 2 on both sides in its row or column gets 1", ring_to_ring_fill),
    ("links stop one cell short at each end", link_shortened),
    ("only the first pair of centers on each line is linked", only_first_link_per_line),
    ("links correct but ring cells recolored to 1", ring_recolored),
    ("input returned unchanged", unchanged_input),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == '__main__':
    task = json.loads((Path(__file__).resolve().parents[3] / 'data/tasks/60a26a3e.json').read_text())
    train = task['train']
    print('pairs', len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g) and g != p['output']:
                n += 1
        print(n, desc)
