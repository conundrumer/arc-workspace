"""Round 9, explorer z: tiling, scale, crop and panel layouts.

The layout of each train example comes from its grids alone (`_layout`): the output is a multiple of the input in both
sides (mode `up`: the tile is the input, the grid is the multiple), or the input splits into equal panels, with or
without divider lines, that the output's size matches or a divider line separates (mode `down`/`panel`: the tile is a
panel, the grid is the panel count), or the output is a subgrid of the input (mode `crop`: the offset). The features
compare X's Position and Box cells (their resolved extents and their margins) with that layout. No frame is read from a
size: a cell's extent is compared with the layout's sizes, and a pair of columns is compared by the relation the
layout names. All features read the first model of each context.
"""
import collections as C

from featlib import feature

CELL_TYPES = ('Position', 'Box')


# ---------------------------------------------------------------- layout of the train grids

def _background(cells):
    count = C.Counter(v for row in cells for v in row)
    top = max(count.values())
    return min(v for v, k in count.items() if k == top)


def _runs(flags):
    """[(start, end)] of the maximal runs of False in a list of flags (True marks a divider line)."""
    out, start = [], None
    for i, f in enumerate(flags):
        if not f and start is None:
            start = i
        if f and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(flags) - 1))
    return out


def _divided(cells):
    """The panels of a grid cut by full lines of one color other than its most common color: (rects, lines) where a rect
    is (top, bottom, left, right) in rows and columns (inclusive) and lines is the set of divider cells; None if the grid
    has no such line or fewer than two panels."""
    h, w = len(cells), len(cells[0])
    bg = _background(cells)
    best = None
    for c in {v for row in cells for v in row} - {bg}:
        rows = [all(v == c for v in cells[r]) for r in range(h)]
        cols = [all(cells[r][k] == c for r in range(h)) for k in range(w)]
        if not any(rows) and not any(cols):
            continue
        rr, cc = _runs(rows), _runs(cols)
        if len(rr) * len(cc) < 2 or all(rows) or all(cols):
            continue
        n = sum(rows) + sum(cols)
        if best is None or n > best[0]:
            best = (n, rr, cc, rows, cols)
    if best is None:
        return None
    _, rr, cc, rows, cols = best
    rects = [(a, b, l, r) for (a, b) in rr for (l, r) in cc]
    lines = {(r, k) for r in range(h) for k in range(w) if rows[r] or cols[k]}
    return rects, lines


def _equal(rects):
    sizes = {(b - a + 1, r - l + 1) for a, b, l, r in rects}
    return next(iter(sizes)) if len(sizes) == 1 else None


def _layout(ex):
    """{'mode', 'tile', 'grid', 'rects', 'lines', 'step', 'offset'} of one example, or None where the grids show none.
    `step` is the distance between tile origins (the tile size, plus 1 where a divider line separates tiles)."""
    gi, go = ex.input, ex.output
    (h, w), (oh, ow) = gi.size, go.size
    if (oh, ow) != (h, w) and oh % h == 0 and ow % w == 0:
        return {'mode': 'up', 'tile': (h, w), 'grid': (oh // h, ow // w), 'rects': None, 'lines': None,
                'step': (h, w), 'offset': None}
    cut = _divided(gi.cells)
    if cut is not None:
        rects, lines = cut
        tile = _equal(rects)
        if tile is not None or (oh, ow) == (h, w):
            grid = None
            step = None
            if tile is not None:
                grid = (len({(a, b) for a, b, _, _ in rects}), len({(l, r) for _, _, l, r in rects}))
                tops = sorted({a for a, _, _, _ in rects})
                lefts = sorted({l for _, _, l, _ in rects})
                dh = tops[1] - tops[0] if len(tops) > 1 else tile[0] + 1
                dw = lefts[1] - lefts[0] if len(lefts) > 1 else tile[1] + 1
                step = (dh, dw)
            return {'mode': 'panel', 'tile': tile, 'grid': grid, 'rects': rects, 'lines': lines,
                    'step': step, 'offset': None}
    if (oh, ow) != (h, w) and oh <= h and ow <= w and oh * ow >= 4:
        for dv in (0, 1):
            if (h + dv) % (oh + dv) == 0 and (w + dv) % (ow + dv) == 0:
                m, n = (h + dv) // (oh + dv), (w + dv) // (ow + dv)
                if m * n < 2 or m * n > 16:
                    continue
                if dv and not (all(len(set(gi.cells[r])) == 1 for r in range(h) if r % (oh + 1) == oh)
                               and all(len({gi.cells[r][c] for r in range(h)}) == 1
                                       for c in range(w) if c % (ow + 1) == ow)):
                    continue
                rects = [(i * (oh + dv), i * (oh + dv) + oh - 1, j * (ow + dv), j * (ow + dv) + ow - 1)
                         for i in range(m) for j in range(n)]
                lines = {(r, c) for r in range(h) for c in range(w)
                         if r % (oh + dv) == oh or c % (ow + dv) == ow} if dv else set()
                return {'mode': 'down', 'tile': (oh, ow), 'grid': (m, n), 'rects': rects, 'lines': lines,
                        'step': (oh + dv, ow + dv), 'offset': None}
    if (oh, ow) != (h, w) and oh <= h and ow <= w and oh * ow >= 4:
        for r0 in range(h - oh + 1):
            for c0 in range(w - ow + 1):
                if all(gi.cells[r0 + a][c0:c0 + ow] == go.cells[a] for a in range(oh)):
                    return {'mode': 'crop', 'tile': None, 'grid': None, 'rects': None, 'lines': None,
                            'step': None, 'offset': (r0, c0)}
    return None


def _layouts(p):
    return {e.index: (e, _layout(e)) for e in p.examples()}


def _first_models(x):
    """{example: rows of the first model of its first assignment}, rows being tuples of decoded values."""
    out = {}
    for (assignment, ex), models in x.examples().items():
        if models and (ex not in out):
            out[ex] = models[0]
    return out


def _cell_cols(x):
    return [c for c in x.columns() if c.type in CELL_TYPES]


# ---------------------------------------------------------------- Z1

@feature
def z1_extent_layout(p):
    """Z1: over the Position and Box cells of X with a resolved extent, on examples whose grids show a tiling, scale or
    panel layout (the output is a multiple of the input, or the input splits into panels), the share whose extent is
    the tile's size (`tile`), the tile grid's dimensions (`grid`), the input's size (`inp`), the output's size (`out`),
    a whole number of tiles in both sides (`multiple`), or none of these (`alien`); `tile_cols`, `grid_cols`, `alien_cols`: the columns whose resolved cells match that
    size in every example. None without such an example or cell.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = _cell_cols(x)
    if not cols:
        return None
    lay = _layouts(p)
    rows_of = _first_models(x)
    counts = C.Counter()
    total = 0
    per_col = {c.index: C.Counter() for c in cols}
    for ex, rows in rows_of.items():
        if ex not in lay or lay[ex][1] is None or lay[ex][1]['mode'] == 'crop':
            continue
        e, lo = lay[ex]
        sizes = {'tile': lo['tile'], 'grid': lo['grid'], 'inp': e.input.size, 'out': e.output.size}
        for r in rows:
            for c in cols:
                m = r[c.index]
                if m.size is None:
                    continue
                total += 1
                per_col[c.index]['n'] += 1
                hit = False
                for k, v in sizes.items():
                    if v is not None and m.size == v:
                        counts[k] += 1
                        per_col[c.index][k] += 1
                        hit = True
                th, tw = lo['tile'] if lo['tile'] else (0, 0)
                if th and tw and m.size != (th, tw) and m.size[0] % th == 0 and m.size[1] % tw == 0:
                    counts['multiple'] += 1
                    per_col[c.index]['multiple'] += 1
                    hit = True
                if not hit:
                    counts['alien'] += 1
                    per_col[c.index]['alien'] += 1
    if not total:
        return None
    out = {k: counts[k] / total for k in ('tile', 'grid', 'inp', 'out', 'multiple', 'alien')}
    for k in ('tile', 'grid', 'alien'):
        out[k + '_cols'] = sum(1 for c in per_col.values() if c['n'] and c[k] == c['n'])
    return out


# ---------------------------------------------------------------- Z2

@feature
def z2_panel_cover(p):
    """Z2: on examples whose input splits into panels (equal blocks, or blocks between divider lines), over the columns
    of X with a resolved extent equal to the input's size. For a Box column: `box_exact` (the share of panels that equal
    a Box value of the column) and `box_pure` (the share of its distinct Box values that are panels). For a Position
    column: `touch` (the share of panels that hold one of its cells), `full` (the share of panels whose every cell it
    holds), `even` (the fewest cells in a panel over the most, 0 when a panel is empty) and `line` (the share of its
    cells on divider lines; None without divider lines). Each key is the best over the columns (`line` the least).
    None without such an example or column.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = _cell_cols(x)
    if not cols:
        return None
    lay = _layouts(p)
    rows_of = _first_models(x)
    acc = {c.index: C.defaultdict(list) for c in cols}
    for ex, rows in rows_of.items():
        if ex not in lay or lay[ex][1] is None or not lay[ex][1]['rects']:
            continue
        e, lo = lay[ex]
        if lo['mode'] == 'up':
            continue
        rects = lo['rects']
        h, w = e.input.size
        rset = {(a, h - 1 - b, l, w - 1 - r) for a, b, l, r in rects}
        for c in cols:
            vals = {r[c.index] for r in rows if r[c.index].size == (h, w)}
            if not vals:
                continue
            a = acc[c.index]
            if c.type == 'Box':
                boxes = {v.margins for v in vals}
                a['box_exact'].append(len(rset & boxes) / len(rset))
                a['box_pure'].append(len(rset & boxes) / len(boxes))
            else:
                cells = {v.cell for v in vals}
                per = [sum(1 for (cr, cc) in cells if rt[0] <= cr <= rt[1] and rt[2] <= cc <= rt[3]) for rt in rects]
                areas = [(rt[1] - rt[0] + 1) * (rt[3] - rt[2] + 1) for rt in rects]
                a['touch'].append(sum(1 for n in per if n) / len(rects))
                a['full'].append(sum(1 for n, ar in zip(per, areas) if n == ar) / len(rects))
                a['even'].append(min(per) / max(per) if max(per) else 0.0)
                if lo['lines']:
                    a['line'].append(sum(1 for cl in cells if cl in lo['lines']) / len(cells))
    out = {}
    for k in ('box_exact', 'box_pure', 'touch', 'full', 'even'):
        v = [sum(a[k]) / len(a[k]) for a in acc.values() if a[k]]
        if v:
            out[k] = max(v)
    v = [sum(a['line']) / len(a['line']) for a in acc.values() if a['line']]
    if v:
        out['line'] = min(v)
    return out or None


# ---------------------------------------------------------------- Z3

def _rel_share(pairs, f):
    return sum(1 for a, b in pairs if f(a, b)) / len(pairs)


@feature
def z3_correspondence(p):
    """Z3: for pairs of Position columns of X, the share of distinct (cell, cell) rows of an example that the layout's
    law relates, by the best direction and column pair, averaged over examples where the law applies. `scale` (an output
    cell and the input cell it scales from: cell // grid = cell, examples with the output a multiple of the input),
    `period` (the output cell modulo the tile = the input cell, same examples), `inner` (a cell modulo the panel step =
    the other cell, examples cut into panels), `outer` (a cell // panel step = the other cell, same examples), `shift`
    (the cells differ by the crop's offset, examples whose output is a subgrid). Each key is None without an example
    where it applies, and the feature is None without two Position columns.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = [c for c in x.columns() if c.type == 'Position'][:8]
    if len(cols) < 2:
        return None
    lay = _layouts(p)
    rows_of = _first_models(x)
    acc = C.defaultdict(list)
    for ex, rows in rows_of.items():
        if ex not in lay or lay[ex][1] is None:
            continue
        lo = lay[ex][1]
        laws = {}
        if lo['mode'] == 'up':
            gm, gn = lo['grid']
            th, tw = lo['tile']
            laws['scale'] = lambda big, small: (big[0] // gm, big[1] // gn) == small
            laws['period'] = lambda big, small: (big[0] % th, big[1] % tw) == small
        elif lo['step'] is not None or lo['rects']:
            if lo['step'] is not None:
                sh, sw = lo['step']
            else:
                t = lo['tile']
                if t is None:
                    continue
                sh, sw = t
            laws['inner'] = lambda big, small: (big[0] % sh, big[1] % sw) == small
            laws['outer'] = lambda big, small: (big[0] // sh, big[1] // sw) == small
        elif lo['mode'] == 'crop' and lo['offset'] != (0, 0):
            r0, c0 = lo['offset']
            laws['shift'] = lambda big, small: (small[0] + r0, small[1] + c0) == big
        for name, law in laws.items():
            best = None
            for i in range(len(cols)):
                for j in range(len(cols)):
                    if i == j:
                        continue
                    pairs = {(r[cols[i].index].cell, r[cols[j].index].cell) for r in rows}
                    if pairs:
                        s = _rel_share(pairs, law)
                        best = s if best is None else max(best, s)
            if best is not None:
                acc[name].append(best)
    if not acc:
        return None
    out = {k: sum(v) / len(v) for k, v in acc.items()}
    out['any'] = max(out.values())
    return out


# ---------------------------------------------------------------- Z4

@feature
def z4_block_spread(p):
    """Z4: on examples with a tile (a tiling, a scale or equal panels), over the Position columns of X with a resolved
    extent. `tile_cover`: for a column whose extent is the tile's size, the distinct cells over the tile's cells.
    `grid_cover`: the same for a column whose extent is the tile grid's dimensions. `block_touch` and `block_even`: for a
    column whose extent is a multiple of the tile (2 or more tiles), the share of tile-sized blocks that hold a cell
    and the fewest cells in a block over the most. Each key is the largest over the columns of its mean over examples;
    None without a matching column.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = [c for c in x.columns() if c.type == 'Position']
    if not cols:
        return None
    lay = _layouts(p)
    rows_of = _first_models(x)
    acc = {c.index: C.defaultdict(list) for c in cols}
    for ex, rows in rows_of.items():
        if ex not in lay or lay[ex][1] is None or lay[ex][1]['tile'] is None:
            continue
        lo = lay[ex][1]
        th, tw = lo['tile']
        for c in cols:
            by_size = C.defaultdict(set)
            for r in rows:
                m = r[c.index]
                if m.size is not None:
                    by_size[m.size].add(m.cell)
            for size, cells in by_size.items():
                a = acc[c.index]
                if size == (th, tw):
                    a['tile_cover'].append(len(cells) / (th * tw))
                if lo['grid'] is not None and size == lo['grid']:
                    a['grid_cover'].append(len(cells) / (size[0] * size[1]))
                if size[0] % th == 0 and size[1] % tw == 0 and size != (th, tw):
                    per = C.Counter((r // th, k // tw) for r, k in cells)
                    nb = (size[0] // th) * (size[1] // tw)
                    a['block_touch'].append(len(per) / nb)
                    a['block_even'].append(min(per.get((i, j), 0) for i in range(size[0] // th)
                                               for j in range(size[1] // tw)) / max(per.values()))
    out = {}
    for k in ('tile_cover', 'grid_cover', 'block_touch', 'block_even'):
        v = [sum(a[k]) / len(a[k]) for a in acc.values() if a[k]]
        if v:
            out[k] = max(v)
    return out or None


# ---------------------------------------------------------------- Z5

def _crop_sites(ex):
    """The boxes (top, bottom, left, right margins in the input) whose subgrid of the input equals the output, for an
    example whose output is smaller than its input; empty when none."""
    gi, go = ex.input, ex.output
    (h, w), (oh, ow) = gi.size, go.size
    if oh > h or ow > w or (oh, ow) == (h, w):
        return set()
    return {(r0, h - r0 - oh, c0, w - c0 - ow)
            for r0 in range(h - oh + 1) for c0 in range(w - ow + 1)
            if all(gi.cells[r0 + a][c0:c0 + ow] == go.cells[a] for a in range(oh))}


@feature
def z5_crop_box(p):
    """Z5: on examples whose output is a subgrid of the input, over the Box columns of X whose resolved extent is the
    input's size: `exact` (the share of examples where the column holds a box whose subgrid of the input is the output),
    `size` (the share of the column's distinct boxes with the output's height and width) and `pure` (the share of its
    distinct boxes that are such a subgrid). Each key is the best over the columns. None without such an example or column.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = [c for c in x.columns() if c.type == 'Box']
    if not cols:
        return None
    exs = {e.index: e for e in p.examples()}
    rows_of = _first_models(x)
    acc = {c.index: C.defaultdict(list) for c in cols}
    for ex, rows in rows_of.items():
        e = exs.get(ex)
        if e is None:
            continue
        sites = _crop_sites(e)
        if not sites:
            continue
        h, w = e.input.size
        oh, ow = e.output.size
        for c in cols:
            boxes = {r[c.index].margins for r in rows if r[c.index].size == (h, w)}
            if not boxes:
                continue
            a = acc[c.index]
            a['exact'].append(float(bool(boxes & sites)))
            a['size'].append(sum(1 for t, b, l, r in boxes if h - t - b == oh and w - l - r == ow) / len(boxes))
            a['pure'].append(len(boxes & sites) / len(boxes))
    out = {}
    for k in ('exact', 'size', 'pure'):
        v = [sum(a[k]) / len(a[k]) for a in acc.values() if a[k]]
        if v:
            out[k] = max(v)
    return out or None


# ---------------------------------------------------------------- Z6

def _orbit(cell, h, w):
    """The images of a cell of an h by w tile under the flips, and under the transpose where the tile is square."""
    r, c = cell[0] % h, cell[1] % w
    out = {(r, c), (h - 1 - r, c), (r, w - 1 - c), (h - 1 - r, w - 1 - c)}
    if h == w:
        out |= {(c, r), (h - 1 - c, r), (c, h - 1 - r), (h - 1 - c, h - 1 - r)}
    return out


@feature
def z6_tile_compose(p):
    """Z6: on examples with a tile step (a tiling or equal panels), over the Position columns of X. `compose`: the share of
    distinct rows of the best ordered column triple (outer, inner, whole) where whole = outer * step + inner in both
    coordinates. `orbit`: the share of distinct (a, b) rows of the best column pair, whose cells differ in some row, where
    b is a flip or transpose of a within a tile (cell modulo the tile). Averaged over examples; None without a tile step
    or without three (compose) or two (orbit) Position columns, each key on its own.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    x = p.x
    cols = [c for c in x.columns() if c.type == 'Position'][:8]
    if len(cols) < 2:
        return None
    lay = _layouts(p)
    rows_of = _first_models(x)
    comp, orb = [], []
    for ex, rows in rows_of.items():
        if ex not in lay or lay[ex][1] is None or lay[ex][1]['step'] is None or not rows:
            continue
        lo = lay[ex][1]
        sh, sw = lo['step']
        th, tw = lo['tile']
        if len(cols) >= 3:
            best = None
            idx = [c.index for c in cols]
            for o in idx:
                for i in idx:
                    for t in idx:
                        if len({o, i, t}) < 3:
                            continue
                        trip = {(r[o].cell, r[i].cell, r[t].cell) for r in rows}
                        s = sum(1 for a, b, c in trip if c == (a[0] * sh + b[0], a[1] * sw + b[1])) / len(trip)
                        best = s if best is None else max(best, s)
            if best is not None:
                comp.append(best)
        best = None
        for a in cols:
            for b in cols:
                if a.index == b.index:
                    continue
                pairs = {(r[a.index].cell, r[b.index].cell) for r in rows}
                if all(u == v for u, v in pairs):
                    continue
                s = sum(1 for u, v in pairs if v in _orbit(u, th, tw)) / len(pairs)
                best = s if best is None else max(best, s)
        if best is not None:
            orb.append(best)
    out = {}
    if comp:
        out['compose'] = sum(comp) / len(comp)
    if orb:
        out['orbit'] = sum(orb) / len(orb)
    return out or None
