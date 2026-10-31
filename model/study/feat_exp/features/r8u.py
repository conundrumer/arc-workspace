"""Round 8, explorer u: frames read from frame tags, never from a size.

U1, U2 replace `r3f.f1b_sized_frame_paint` and `r4l.l5_sized_cells`: a Position column is a grid's cell set when its
frame tag says so, or when its tag is empty and the frames of its variable, taken from the available tables that
the form reads, are that one grid. U3 to U5 read frames that differ between a variable's sites and between X and its form.
"""
import collections as C

from featlib import feature, load as featlib_load

GRIDS = ('input', 'output')
BOX_TYPES = ('Position', 'Box')


def _kind(tag):
    if tag is None:
        return None
    return tag if tag in ('', 'input', 'output') else 'site'


_grid_id_cache = {}


def _grid_ids(p):
    """{frame id: grid kind} for the frame ids of `types_frames_v1` that the native grid analysis establishes as one grid
    (input or output) at a label or site of a clause before the point. Read from the point's `point.json`, because featlib
    does not hand this map out; {} where the point has no complete key."""
    pd = getattr(p, 'point_dir', None)
    if pd is None:
        return {}
    if pd not in _grid_id_cache:
        ids = {}
        try:
            top = featlib_load(pd / 'point.json').get('types_frames_v1') or {}
        except Exception:
            top = {}
        for cl in top.get('prefix') or []:
            for it in (cl.get('labels') or []) + (cl.get('sites') or []):
                fr = it.get('frame') or {}
                kinds = {g.get('kind') for g in fr.get('grids') or []}
                if it.get('frame_id') and fr.get('status') == 'established' and len(kinds) == 1:
                    ids[it['frame_id']] = next(iter(kinds))
        if len(_grid_id_cache) > 4:
            _grid_id_cache.clear()
        _grid_id_cache[pd] = ids
    return _grid_id_cache[pd]


def _var_frames(p, col):
    """The non-empty frames of the variable that X's column `col` holds, from the available tables the form reads (and
    from `types_frames_v1` where featlib has it): the tag 'input' or 'output', a native frame id that establishes
    one grid read as that grid, any other tag or id as itself."""
    v = p.clause.x_columns.get(col.name)
    if v is None:
        return frozenset()
    ids = _grid_ids(p)
    return frozenset(ids.get(f, f) for f in v.frames if f)


def _inferred_grid(p, col):
    """'input' or 'output' for a column whose own tag is empty and whose variable is read, at every site that has a
    frame, from that one grid; else None."""
    if col.frame_kind != '':
        return None
    fr = _var_frames(p, col)
    if len(fr) == 1:
        (f,) = fr
        if f in GRIDS:
            return f
    return None


def _cells(p, col, grid_of_ex):
    """{example: [set of (row, col) per model]} of a Position column read as cells of the grid `grid_of_ex(example)`,
    or None when some cell is off that grid."""
    out = {}
    train = p.examples()
    for (_, k), models in p.x.examples().items():
        if k >= len(train):
            continue
        h, w = grid_of_ex(train[k]).size
        per = []
        for rows in models:
            s = set()
            for r in rows:
                m = r[col.index]
                if not hasattr(m, 'margins'):
                    continue
                t, b, l, rt = m.margins
                if min(t, b, l, rt) < 0 or t + b != h - 1 or l + rt != w - 1:
                    return None
                s.add((t, l))
            per.append(s)
        out.setdefault(k, []).extend(per)
    return out


@feature
def u1_grid_paint(p):
    """U1 Paint of X against the train output, over Position columns whose tag is empty and whose variable is read from one grid.

    For the (Position, Color) pair with the best recall (then the lowest `wrong`): `recall`, the share of the cells to
    produce (the changed cells if the example's grids have one size, else all output cells) that some row paints with the
    output color; `wrong`, the share of rows whose cell is off the grid or whose color is not the output's; `cover`, the share
    of output cells with a row; `conflict`, the share of covered cells with two colors. A column read from the input counts
    only on examples whose grids have one size. None without such a column.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.

    Needs: partial. Monotone: no for `recall`; `wrong` holds under adding positive atoms.
    """
    if p.kind == 'Det':
        return None
    cols = p.x.columns()
    colors = [c for c in cols if c.type == 'Color']
    train = p.examples()
    best = None
    for pos in cols:
        if pos.type != 'Position':
            continue
        grid = _inferred_grid(p, pos)
        if grid is None:
            continue
        for color in colors:
            need = hit = rows_n = wrong = cells = covered = conflict = 0
            seen = False
            for (_, k), models in p.x.examples().items():
                if k >= len(train):
                    continue
                ex = train[k]
                if grid == 'input' and not ex.same_size:
                    continue
                gout = ex.output
                h, w = gout.size
                todo = ex.changed() if ex.same_size else {(r, c) for r in range(h) for c in range(w)}
                if not todo:
                    continue
                seen = True
                for rows in models:
                    got, colmap = set(), {}
                    for r in rows:
                        m = r[pos.index]
                        if not hasattr(m, 'margins'):
                            continue
                        t, b, l, rt = m.margins
                        rows_n += 1
                        if min(t, b, l, rt) < 0 or t + b != h - 1 or l + rt != w - 1:
                            wrong += 1
                            continue
                        if gout[t, l] != r[color.index]:
                            wrong += 1
                        colmap.setdefault((t, l), set()).add(r[color.index])
                        if gout[t, l] == r[color.index] and (t, l) in todo:
                            got.add((t, l))
                    need += len(todo)
                    hit += len(got)
                    cells += h * w
                    covered += len(colmap)
                    conflict += sum(len(v) > 1 for v in colmap.values())
            if not seen or not need:
                continue
            cand = (hit / need, -(wrong / rows_n if rows_n else 1.0), covered, conflict, cells)
            if best is None or cand[:2] > best[:2]:
                best = cand
    if best is None:
        return None
    cells = best[4]
    return {'recall': best[0], 'wrong': -best[1], 'cover': best[2] / cells if cells else 0.0,
            'conflict': best[3] / best[2] if best[2] else 0.0}


@feature
def u2_grid_cells(p):
    """U2 The cells of a Position column with an empty tag, read from one grid, against the cells the task changes.

    Over the columns whose variable is read from the input (or from the output) and the examples whose input and output
    have one size: `chg_cov`, the share of changed cells that the column holds; `chg_prec`, the share of its distinct
    cells that are changed cells; `bg`, the share of its distinct cells on the input's most common color. The column with
    the largest `chg_cov` (then `chg_prec`) is reported. None without such a column.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.

    Needs: partial. Monotone: no (`chg_cov` can only fall under adding positive atoms; `chg_prec` can rise).
    """
    if p.kind == 'Det':
        return None
    train = p.examples()
    best = None
    for pos in p.x.columns():
        if pos.type != 'Position':
            continue
        grid = _inferred_grid(p, pos)
        if grid is None:
            continue
        cells = _cells(p, pos, lambda e: e.output if grid == 'output' else e.input)
        if not cells:
            continue
        n = bg = chg = need = 0
        for k, per in cells.items():
            ex = train[k]
            if not ex.same_size:
                continue
            todo = ex.changed()
            ground = ex.input.most_common()
            for s in per:
                n += len(s)
                bg += sum(ex.input[r, c] in ground for r, c in s)
                chg += len(s & todo)
                need += len(todo)
        if not n or not need:
            continue
        cand = (chg / need, chg / n, bg / n)
        if best is None or cand[:2] > best[:2]:
            best = cand
    if best is None:
        return None
    return {'chg_cov': best[0], 'chg_prec': best[1], 'bg': best[2]}


def _tag_extents(p):
    """{frame tag: {example: set of extents}} over the Position and Box cells of the available tables whose extent is
    resolved, with the tags 'input' and 'output' read as the train grids' sizes. The first 300 rows of each entry count."""
    out = {}
    for t in p.available():
        cols = [c for c in t.columns() if c.type in BOX_TYPES and c.frame]
        if not cols:
            continue
        for e in t.entries:
            for row in e['rows'][:300]:
                for c in cols:
                    cell = row[c.index]
                    if cell.get('extent_status') == 'resolved' and cell.get('extent'):
                        out.setdefault(c.frame, {}).setdefault(e['train'], set()).add(tuple(cell['extent']))
    for ex in p.examples():
        out.setdefault('input', {})[ex.index] = {ex.input.size}
        out.setdefault('output', {})[ex.index] = {ex.output.size}
    return out


@feature
def u3_frame_clash(p):
    """U3 Variables that sit at sites of different frames, and whether those frames have one extent.

    `vars`: the number of variables of the candidate's body with two or more distinct non-empty frames among the tables
    they are read from. `same_extent`: those whose frames have, on every example where all of them have a resolved extent,
    the same set of extents; `diff_extent`: the others. `grid_site`: those with one grid tag and one relation-site tag.
    `cmp_cross`: the comparison atoms whose two variables each have a frame and share none. None without a body.

    Needs: partial. Monotone: `vars` rises under adding positive atoms that join a variable to a new frame.
    """
    body = p.clause.body
    if body is None:
        return None
    ids = _grid_ids(p)
    n = gs = same = diff = cross = 0
    for cmp in body.comparisons:
        x, y = cmp.first, cmp.second
        if x is None or y is None or x.variable is None or y.variable is None:
            continue
        fx = {ids.get(f, f) for f in x.variable.frames if f}
        fy = {ids.get(f, f) for f in y.variable.frames if f}
        if fx and fy and fx.isdisjoint(fy):
            cross += 1
    ext = None
    for v in body.variables.values():
        fr = {ids.get(f, f) for f in v.frames if f}
        if len(fr) < 2:
            continue
        n += 1
        if any(f in GRIDS for f in fr) and any(f not in GRIDS for f in fr):
            gs += 1
        if ext is None:
            ext = _tag_extents(p)
        exs = None
        for f in fr:
            keys = set(ext.get(f, {}))
            exs = keys if exs is None else exs & keys
        agree = bool(exs) and all(len({frozenset(ext[f][k]) for f in fr}) == 1 for k in exs)
        same += agree
        diff += not agree
    return {'vars': n, 'same_extent': same, 'diff_extent': diff, 'grid_site': gs, 'cmp_cross': cross}


@feature
def u4_made_cover(p):
    """U4 How fully X's cells fill the frame that their own tag names, for a relation-site frame.

    Over the Position columns whose tag names a relation site and whose cells have a resolved extent (h, w): per example and
    model and extent, the distinct cells of the column with that extent divided by h * w. `cover`: the largest such mean over the columns; `full`: the
    share of those (example, model, extent) groups of that column with every cell; `dup`: the mean rows per distinct cell of that column.
    None without such a column.

    Needs: partial. Monotone: no (cover falls under adding positive atoms, but a join can raise `dup`).
    """
    cols = [c for c in p.x.columns() if c.type == 'Position' and c.frame_kind == 'site']
    best = None
    for pos in cols:
        shares, full, rows_n, cell_n = [], 0, 0, 0
        for (_, k), models in p.x.examples().items():
            for rows in models:
                cells = {}
                for r in rows:
                    m = r[pos.index]
                    if not hasattr(m, 'margins') or m.size is None:
                        continue
                    cells.setdefault(m.size, set()).add(m.margins[::2])
                    rows_n += 1
                for size, group in cells.items():
                    total = size[0] * size[1]
                    shares.append(len(group) / total if total else 0.0)
                    full += len(group) == total
                    cell_n += len(group)
        if not shares:
            continue
        cand = (sum(shares) / len(shares), full / len(shares), rows_n / cell_n if cell_n else 1.0)
        if best is None or cand > best:
            best = cand
    if best is None:
        return None
    return {'cover': best[0], 'full': best[1], 'dup': best[2]}


@feature
def u5_frame_lost(p):
    """U5 X columns whose tag is empty although their variable is read from a frame.

    Over the Position and Box columns of X with an empty tag whose variable has a non-empty frame tag at the tables the
    form reads: `clash`, the number of those whose variable has two or more distinct frame tags (the tag is empty because
    the sites disagree); `single`, the number whose variable has one frame tag. `clash_share`: `clash` over the Position
    and Box columns of X. None without a Position or Box column.

    Needs: partial. Monotone: no.
    """
    cols = [c for c in p.x.columns() if c.type in BOX_TYPES and c.frame_kind is not None]
    if not cols:
        return None
    clash = single = 0
    for c in cols:
        if c.frame_kind != '':
            continue
        n = len(_var_frames(p, c))
        clash += n >= 2
        single += n == 1
    return {'clash': clash, 'single': single, 'clash_share': clash / len(cols)}
