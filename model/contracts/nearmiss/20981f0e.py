import json
from pathlib import Path

DOT = 2
BG = 0


def _dividers(g):
    rows = sorted({r for r, row in enumerate(g) for v in row if v == DOT})
    cols = sorted({c for row in g for c, v in enumerate(row) if v == DOT})
    return rows, cols


def _tiles(g, half_open=False):
    rows, cols = _dividers(g)
    tiles = []
    for i in range(len(rows) - 1):
        for j in range(len(cols) - 1):
            r0, r1 = rows[i] + 1, rows[i + 1] - 1
            c0, c1 = cols[j] + 1, cols[j + 1] - 1
            tiles.append((r0, r1, c0, c1))
    return tiles


def _pieces(g, tiles):
    res = []
    for (r0, r1, c0, c1) in tiles:
        cells = [(r, c, g[r][c]) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
                 if g[r][c] not in (BG, DOT)]
        res.append(cells)
    return res


def _rebuild(inp, tiles, pieces, place, cell_map=None, erase=True):
    g = [row[:] for row in inp]
    h, w = len(g), len(g[0])
    for t, cells in zip(tiles, pieces):
        if not cells and True:
            continue
        for r, c, v in cells:
            if erase:
                g[r][c] = BG
    for t, cells in zip(tiles, pieces):
        if not cells:
            continue
        rs = [r for r, _, _ in cells]
        cs = [c for _, c, _ in cells]
        bb = (min(rs), max(rs), min(cs), max(cs))
        dr, dc = place(t, bb)
        for r, c, v in cells:
            nr, nc = r + dr, c + dc
            if cell_map:
                nr, nc, v = cell_map(t, bb, r, c, v, nr, nc, dr, dc)
            if 0 <= nr < h and 0 <= nc < w:
                g[nr][nc] = v
    return g


def _center(t, bb, floor=True, do_r=True, do_c=True, tile_adj=(0, 0, 0, 0)):
    r0, r1, c0, c1 = (t[0] + tile_adj[0], t[1] + tile_adj[1], t[2] + tile_adj[2], t[3] + tile_adj[3])
    dr = dc = 0
    if do_r:
        sp = (r1 - r0 + 1) - (bb[1] - bb[0] + 1)
        dr = r0 + (sp // 2 if floor else (sp + 1) // 2) - bb[0]
    if do_c:
        sp = (c1 - c0 + 1) - (bb[3] - bb[2] + 1)
        dc = c0 + (sp // 2 if floor else (sp + 1) // 2) - bb[2]
    return dr, dc


def _run(inp, place, cell_map=None, erase=True):
    tiles = _tiles(inp)
    return _rebuild(inp, tiles, _pieces(inp, tiles), place, cell_map, erase)


def clear_only(inp, out):
    return _run(inp, lambda t, bb: (0, 0), cell_map=lambda t, bb, r, c, v, nr, nc, dr, dc: (-1, -1, v))


def center_round_up(inp, out):
    return _run(inp, lambda t, bb: _center(t, bb, floor=False))


def top_left(inp, out):
    return _run(inp, lambda t, bb: (t[0] - bb[0], t[2] - bb[2]))


def bottom_right(inp, out):
    return _run(inp, lambda t, bb: (t[1] - bb[1], t[3] - bb[3]))


def center_cols_only(inp, out):
    return _run(inp, lambda t, bb: _center(t, bb, do_r=False))


def center_rows_only(inp, out):
    return _run(inp, lambda t, bb: _center(t, bb, do_c=False))


def mirrored_horizontally(inp, out):
    def cm(t, bb, r, c, v, nr, nc, dr, dc):
        # mirror within the piece box, then centre
        return nr, (bb[2] + bb[3] - c) + dc, v
    return _run(inp, lambda t, bb: _center(t, bb), cell_map=cm)


def flipped_vertically(inp, out):
    def cm(t, bb, r, c, v, nr, nc, dr, dc):
        return (bb[0] + bb[1] - r) + dr, nc, v
    return _run(inp, lambda t, bb: _center(t, bb), cell_map=cm)


def tile_half_open(inp, out):
    # tile taken as running from one divider up to but excluding the next
    return _run(inp, lambda t, bb: _center(t, bb, tile_adj=(-1, 0, -1, 0)))


def tile_shrunk(inp, out):
    # one extra margin cell on the far sides excluded from the tile
    return _run(inp, lambda t, bb: _center(t, bb, tile_adj=(0, -1, 0, -1)))


def dividers_removed(inp, out):
    return [[BG if v == DOT else v for v in row] for row in out]


def moved_piece_recolored(inp, out):
    return [[DOT if (v not in (BG, DOT) and inp[r][c] != v) else v for c, v in enumerate(row)]
            for r, row in enumerate(out)]


def only_first_tile_row_moved(inp, out):
    rows, _ = _dividers(inp)
    limit = rows[1] if len(rows) > 1 else 0
    g = [row[:] for row in out]
    for r in range(limit + 1, len(g)):
        g[r] = inp[r][:]
    return g


ALTERNATIVES = [
    ("pieces are erased from every tile instead of being moved", clear_only),
    ("piece is centred in its tile with the odd cell rounded the other way", center_round_up),
    ("piece slides to the top-left corner of its tile", top_left),
    ("piece slides to the bottom-right corner of its tile", bottom_right),
    ("piece is centred horizontally only, rows unchanged", center_cols_only),
    ("piece is centred vertically only, columns unchanged", center_rows_only),
    ("piece is mirrored left-right while being centred", mirrored_horizontally),
    ("piece is flipped top-bottom while being centred", flipped_vertically),
    ("tile taken as divider-inclusive on the near side, so the centre is off by one", tile_half_open),
    ("divider dots are erased along with the move", dividers_removed),
    ("moved piece cells are recoloured to the divider colour", moved_piece_recolored),
    ("only the first row of tiles is recentred; later tile rows stay as in the input", only_first_tile_row_moved),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == '__main__':
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/20981f0e.json'))
    train = task['train']
    print('pairs', len(train))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p['input'], p['output'])
            if g is not None and _valid(g, p['output']):
                n += 1
        print(n, '-', desc)
