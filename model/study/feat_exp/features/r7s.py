"""Round 7, explorer S: where X's directions point, and the frames X's cells live in.

S1: what lies beyond a Box or Position of the input or output frame on the side that a Dir column of the same row names.
S2: whether the frames of X's cells without an input or output tag have the size of the train output or of the input.
S3: whether a group of X's input cells, under one value of another column, has the bounding box of the train output.

A Dir value d (0 to 3) is read as the margin index of [top, bottom, left, right], as `margin` reads it. Types and frames
come from the table fields (featlib's Column). Every model of a context is read on its own; values are deduplicated
within a model.
"""
from featlib import feature

DIRS = ('Dir', 'Dir8')


def _prefix(cells, h, w):
    """2-D prefix sums of a set of (row, col) cells on an h by w grid: s[i][j] counts the cells in rows < i, cols < j."""
    s = [[0] * (w + 1) for _ in range(h + 1)]
    for i in range(h):
        acc = 0
        row, above = s[i + 1], s[i]
        for j in range(w):
            acc += (i, j) in cells
            row[j + 1] = above[j + 1] + acc
    return s


def _count(s, r0, r1, c0, c1):
    if r0 >= r1 or c0 >= c1:
        return 0
    return s[r1][c1] - s[r0][c1] - s[r1][c0] + s[r0][c0]


def _beam(m, d, h, w):
    """(r0, r1, c0, c1): the cells of the frame beyond the value's side d, within its span on the other axis."""
    t, b, l, r = m.margins
    if d == 0:
        return 0, t, l, w - r
    if d == 1:
        return h - b, h, l, w - r
    if d == 2:
        return t, h - b, 0, l
    return t, h - b, w - r, w


def _foreground(grid):
    bg = min(grid.most_common())
    return {(i, j) for i in range(grid.height) for j in range(grid.width) if grid.cells[i][j] != bg}


@feature
def s1_dir_beam(p):
    """S1: over pairs of a Position or Box column of frame input or output and a Dir column of X, for each distinct (value, direction d) of a model: whether the value touches its frame on side d (blocked), whether the cells beyond side d within its span hold a cell the output changes (chg, on one-size examples) or a cell off the grid's most common color (fg); shares per column pair, then the largest and smallest over pairs; blocked_all counts the pairs blocked in every value, chg_none the pairs whose beams hold no changed cell. None without such a pair or a value in a frame of the grid's size. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    cols = x.columns()
    grid = [c for c in cols if c.type in ('Position', 'Box') and c.frame_kind in ('input', 'output')]
    dirs = [c for c in cols if c.type in DIRS]
    if not grid or not dirs:
        return None
    exs = p.examples()
    sums = {}

    def prefix(ei, kind, what):
        key = (ei, kind, what)
        if key not in sums:
            e = exs[ei]
            g = e.input if kind == 'input' else e.output
            if what == 'chg':
                cells = e.changed()
                sums[key] = None if cells is None else _prefix(cells, g.height, g.width)
            else:
                sums[key] = _prefix(_foreground(g), g.height, g.width)
        return sums[key]

    stats = {}
    for (a, ei), models in x.examples().items():
        if not 0 <= ei < len(exs):
            continue
        e = exs[ei]
        for mi, rows in enumerate(models):
            for c in grid:
                g = e.input if c.frame_kind == 'input' else e.output
                for dc in dirs:
                    seen = set()
                    for r in rows:
                        m, d = r[c.index], r[dc.index]
                        if not isinstance(d, int) or not 0 <= d <= 3 or not hasattr(m, 'margins'):
                            continue
                        if m.size != g.size or not m.in_frame():
                            continue
                        key = (m.margins, d)
                        if key in seen:
                            continue
                        seen.add(key)
                        st = stats.setdefault((c.index, dc.index), [0, 0, 0, 0, 0])
                        st[0] += 1
                        st[1] += m.margins[d] == 0
                        box = _beam(m, d, g.height, g.width)
                        fg = prefix(ei, c.frame_kind, 'fg')
                        st[2] += _count(fg, *box) > 0
                        chg = prefix(ei, c.frame_kind, 'chg')
                        if chg is not None:
                            st[3] += 1
                            st[4] += _count(chg, *box) > 0
    if not stats:
        return None
    blocked = [s[1] / s[0] for s in stats.values()]
    fg = [s[2] / s[0] for s in stats.values()]
    out = {'pairs': len(stats), 'blocked_max': max(blocked), 'blocked_min': min(blocked),
           'blocked_all': sum(b == 1.0 for b in blocked), 'fg_max': max(fg), 'fg_min': min(fg)}
    chg = [s[4] / s[3] for s in stats.values() if s[3]]
    if chg:
        out['chg_max'] = max(chg)
        out['chg_min'] = min(chg)
        out['chg_none'] = sum(c == 0.0 for c in chg)
    return out


@feature
def s2_frame_size(p):
    """S2: over the Position and Box columns of X with an empty or relation-site frame tag, on examples whose input and output differ in size, the share of distinct cells (per model) whose resolved extent is the output's size (out), the input's size (inn), or neither (other); unresolved cells are left out. None without such a cell. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    cols = [c for c in x.columns() if c.type in ('Position', 'Box') and c.frame_kind in ('', 'site')]
    if not cols:
        return None
    exs = p.examples()
    if all(e.same_size for e in exs):
        return None
    n = out = inn = 0
    for (a, ei), models in x.examples().items():
        if not 0 <= ei < len(exs):
            continue
        e = exs[ei]
        if e.same_size:
            continue
        for rows in models:
            for c in cols:
                vals = {(m.margins, m.size) for m in (r[c.index] for r in rows) if getattr(m, 'size', None)}
                for _, size in vals:
                    n += 1
                    out += size == e.output.size
                    inn += size == e.input.size
    if not n:
        return None
    return {'out': out / n, 'inn': inn / n, 'other': (n - out - inn) / n}


def _box_size(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return (max(rs) - min(rs) + 1, max(cs) - min(cs) + 1)


@feature
def s3_crop_group(p):
    """S3: on examples whose output and input differ in size, for each Position column of X with frame tag input and the input's extent, and each other column k (not Example), the distinct cells of a model grouped by k's value: whether some group's bounding box has the output's size. Shares of (example, model) units per (column, k) pair; fit_lib is the largest over k bound by a library atom, fit_any over every k, lib_pairs counts the pairs with such a k; whole: the share of units where the bounding box of all of the column's cells has the output's size. None without such a column on such an example. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    cols = x.columns()
    pos = [c for c in cols if c.type == 'Position' and c.frame_kind == 'input']
    if not pos:
        return None
    exs = p.examples()
    if all(e.same_size for e in exs):
        return None
    lib = set()
    for name, var in p.clause.x_columns.items():
        if any(b.atom.kind in ('relation', 'macro') for b in var.binders):
            lib.add(name)
    keys = [k for k in cols if k.type != 'Example']
    units = whole = 0
    hits = {}
    for (a, ei), models in x.examples().items():
        if not 0 <= ei < len(exs) or exs[ei].same_size:
            continue
        e = exs[ei]
        target = e.output.size
        for rows in models:
            for c in pos:
                cells = {r[c.index].cell for r in rows if getattr(r[c.index], 'size', None) == e.input.size}
                if not cells:
                    continue
                units += 1
                whole += _box_size(cells) == target
                for k in keys:
                    if k.index == c.index:
                        continue
                    groups = {}
                    for r in rows:
                        m = r[c.index]
                        if getattr(m, 'size', None) == e.input.size:
                            groups.setdefault(r[k.index], set()).add(m.cell)
                    h = hits.setdefault((c.index, k.index), [0, 0])
                    h[0] += 1
                    h[1] += any(_box_size(g) == target for g in groups.values())
    if not units:
        return None
    out = {'whole': whole / units}
    shares = {key: h[1] / h[0] for key, h in hits.items() if h[0]}
    if shares:
        out['fit_any'] = max(shares.values())
        libs = [v for (ci, ki), v in shares.items() if cols[ki].name in lib]
        out['lib_pairs'] = len(libs)
        if libs:
            out['fit_lib'] = max(libs)
    return out
