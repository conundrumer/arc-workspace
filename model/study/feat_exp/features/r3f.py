"""Round 3, explorer F: what a lossy table loses and the traces of that loss in the train grids and the available tables.

F1, F1b: paint of X against the train output, counted on the cells the task changes.
F2: how many of the rows of an available table that the form reads survive in X.
"""
import collections as C

from featlib import feature, ident_group


def _resolved(cell):
    return cell.get('extent_status') == 'resolved' and cell.get('extent')


def _paint(p, x, pi, ci, mode):
    """Counts for one (Position column, Color column) pair of X, summed over X's contexts (each example on its own train grids).

    mode 'input': the Position column has frame input; only examples whose input and output grids have the same size count.
    mode 'output': frame output; the cells to produce are the changed cells if the grids have the same size, else all output cells.
    mode 'sized': any other frame (none, or a relation site) whose cells all have a resolved extent equal to the output size;
    the cells to produce are the changed cells if the grids have the same size, else all output cells.
    The rows of an example are those of `Table.examples()`: a table with an Example column holds the rows of every
    example in each entry, and a row belongs to the example its Example cells name. Every model of a context counts.
    Returns None when the column does not qualify, else a dict of counts.
    """
    need = hit_n = cells_n = rows = wrong = ch_rows = ch_right = covered = conflict = 0
    seen = False
    train = p.examples()
    for (_, k), models in x.examples().items():
        if k >= len(train):
            continue
        gin, gout = train[k].input, train[k].output
        h, w = gout.size
        if mode == 'input' and not train[k].same_size:
            continue
        if mode == 'sized' and any(getattr(r[pi], 'size', None) != (h, w) for entry_rows in models for r in entry_rows):
            return None
        todo = train[k].changed() if train[k].same_size else {(r, c) for r in range(h) for c in range(w)}
        if not todo:
            continue
        seen = True
        for entry_rows in models:
            hit = set()
            seen_cells = set()
            colors = {}
            for row in entry_rows:
                pos, color = row[pi], row[ci]
                if not hasattr(pos, 'margins'):
                    continue
                t, b, l, r = pos.margins
                rows += 1
                if min(t, b, l, r) < 0 or t + b != h - 1 or l + r != w - 1:
                    wrong += 1
                    continue
                ok = gout[t, l] == color
                seen_cells.add((t, l))
                colors.setdefault((t, l), set()).add(color)
                if not ok:
                    wrong += 1
                if (t, l) in todo:
                    ch_rows += 1
                    ch_right += ok
                    if ok:
                        hit.add((t, l))
            need += len(todo)
            hit_n += len(hit)
            cells_n += h * w
            covered += len(seen_cells)
            conflict += sum(len(v) > 1 for v in colors.values())
    if not seen:
        return None
    return dict(need=need, hit=hit_n, rows=rows, wrong=wrong, ch_rows=ch_rows, ch_right=ch_right,
                cells=cells_n, covered=covered, conflict=conflict)


def _key_bound(p, color):
    """Whether the label of a Color column is made at a site of a `key` column (an object's key color)."""
    v = p.clause.x_columns.get(color.name)
    return v is not None and any(a.binds and a.column == 'key' for a in v.binders)


def _best(p, modes_for_column, skip_keys=False):
    """The counts of the best (Position column, Color column) pair of X: the highest recall, then the lowest share of
    wrong rows, then the largest counts. The choice depends on the counts alone, so on no column order.
    None where X has two or more Color columns: that table compares colors, and paints none. With `skip_keys`, a Color
    column that holds an object's key color is left out where X also has an Ident column (the color of an object
    that a Position of another atom is joined to by a comparison only is not painted at that Position)."""
    x = p.x
    cols = x.columns()
    colors = [c for c in cols if c.type == 'Color']
    if len(colors) > 1:
        return None
    if skip_keys and any(c.type == 'Ident' for c in cols):
        colors = [c for c in colors if not _key_bound(p, c)]
    best = None
    for pos in cols:
        if pos.type != 'Position':
            continue
        mode = modes_for_column(pos)
        if not mode:
            continue
        for color in colors:
            c = _paint(p, x, pos.index, color.index, mode)
            if c is None:
                continue
            recall = c['hit'] / c['need']
            wrong = c['wrong'] / c['rows'] if c['rows'] else 1.0
            cand = (recall, -wrong, tuple(c[k] for k in sorted(c)), c)
            if best is None or cand[:3] > best[:3]:
                best = cand
    return best


@feature
def f1_changed_cell_paint(p):
    """F1: X's Position (frame input or output) and Color paint against the train output, counted on the cells that differ between train input and output (all output cells if the sizes differ).

    recall: share of those cells that some X row paints with the output color.
    prec_changed: share of X rows on those cells that have the output color (0 if none).
    wrong: share of X rows whose cell is off the grid or whose color is not the output color there.
    cover: share of grid cells that have at least one X row.
    conflict: share of the covered cells that X paints with two or more colors. None without such a Position and Color column.
    The best pair of columns has the highest recall, then the lowest `wrong`, then the largest counts.
    Input-frame positions are read in the output grid, which assumes the two grids share coordinates;
    only examples whose input and output grids have the same size count for them.
    In a table with an Example column, each train example is read from the rows of that example.
    None where X has two or more Color columns (a table that compares colors).
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    best = _best(p, lambda c: c.frame_kind if c.frame_kind in ('input', 'output') else None)
    if best is None:
        return None
    c = best[3]
    return {'recall': c['hit'] / c['need'],
            'prec_changed': c['ch_right'] / c['ch_rows'] if c['ch_rows'] else 0.0,
            'wrong': c['wrong'] / c['rows'] if c['rows'] else 1.0,
            'cover': c['covered'] / c['cells'],
            'conflict': c['conflict'] / c['covered'] if c['covered'] else 0.0}


@feature
def f1b_sized_frame_paint(p):
    """F1b: as F1, for a Position column whose frame is empty or a relation site and whose cells all have a resolved extent equal to the train output size.

    recall: share of the cells to produce (changed cells if input and output sizes are equal, else all output cells) that some X row paints with the output color.
    wrong: share of X rows whose color is not the output color at their cell.
    cover: share of output cells that have at least one X row.
    conflict: share of the covered cells that X paints with two or more colors.
    Equal sizes do not establish that the frame is the input or output grid; the feature reads X as a painting on that evidence.
    In a table with an Example column, each train example is read from the rows of that example, against that example's output.
    None where X has two or more Color columns (a table that compares colors), and where its only Color column holds an
    object's key color (bound from a `key` column) and X has an Ident column.
    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids.
    """
    if p.kind == 'Det':
        return None
    best = _best(p, lambda c: 'sized' if c.frame_kind in ('', 'site') else None, skip_keys=True)
    if best is None:
        return None
    c = best[3]
    return {'recall': c['hit'] / c['need'],
            'wrong': c['wrong'] / c['rows'] if c['rows'] else 1.0,
            'cover': c['covered'] / c['cells'],
            'conflict': c['conflict'] / c['covered'] if c['covered'] else 0.0}


# ---------------------------------------------------------------- F2

def _tracked(p):
    """(table, [(table column index, X column index)]) for each atom outside OR, NOT, IF and ALL that reads an available
    table and stars some labels that are columns of X."""
    body = p.clause.body
    out = []
    for atom in body.atoms if body is not None else []:
        if atom.negated or atom.branch or atom.quantifier or atom.conditional or atom.operator:
            continue
        t = atom.table
        if t is None or atom.interface.kind not in ('table', 'fact'):
            continue
        pairs = []
        for a in atom.arguments:
            tcol = atom.interface.column(a.name)
            if a.binds and a.variable is not None and a.variable.column is not None and tcol is not None:
                pairs.append((tcol, a.variable.column))
        if pairs:
            out.append((t, pairs))
    return out


@feature
def f2_source_survival(p):
    """F2: for the atoms of the form (outside OR and NOT) that read an available table and star some of its columns, the share of that table's distinct rows, projected on the starred columns, that appear in X's projection, per context and summed over contexts.

    largest: that share for the atom whose table has the most distinct projected rows, then the most starred columns, then the lowest share.
    min: the smallest share over such atoms.
    The starred columns that hold an Ident are left out unless the table and X share Ident values (an Ident is local
    to its table). Tables with an Example column and contexts the table lacks are skipped. None if no atom qualifies.

    None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so its rows would be compared with one example's rows of an earlier table.
    """
    if p.kind == 'Det':
        return None
    xrows = p.x.examples(decoded=False)
    shares = []
    for t, pairs in _tracked(p):
        if any(c.type == 'Example' for c in t.columns()):
            continue
        pairs = [(tc, xc) for tc, xc in pairs
                 if 'Ident' not in (tc.type, xc.type) or ident_group(t) == ident_group(p.x)]
        if not pairs:
            continue
        ti, xi = [tc.index for tc, _ in pairs], [xc.index for _, xc in pairs]
        inter = total = 0
        for key, models in t.examples(decoded=False).items():
            tp = {tuple(r[i] for i in ti) for r in models[0]}
            if not tp:
                continue
            xp = {tuple(r[i] for i in xi) for r in xrows.get(key, [[]])[0]}
            inter += len(tp & xp)
            total += len(tp)
        if total:
            shares.append((total, len(pairs), -inter / total))
    if not shares:
        return None
    total, n, neg = max(shares)
    return {'largest': -neg, 'min': min(-s[2] for s in shares)}


# ---------------------------------------------------------------- F3

@feature
def f3_site_extent_agreement(p):
    """F3: over X's Position and Box fields whose frame tag names a relation site (not empty, input or output), the share of rows in which every such cell with a resolved extent has the same extent, up to swapping height and width.

    Cells derived from one object by relative or apply atoms share an extent; a field computed from a whole input grid does not.
    None with fewer than two such fields or no row with two resolved cells.
    """
    x = p.x
    idx = [c.index for c in x.columns() if c.type in ('Position', 'Box') and c.frame_kind == 'site']
    if len(idx) < 2:
        return None
    rows = same = 0
    for e in x.entries:
        for r in e['rows']:
            ext = {tuple(sorted(r[i]['extent'])) for i in idx if _resolved(r[i])}
            n = sum(1 for i in idx if _resolved(r[i]))
            if n < 2:
                continue
            rows += 1
            same += len(ext) == 1
    return same / rows if rows else None


# ---------------------------------------------------------------- F5

@feature
def f5_border_boxes(p):
    """F5: over X's Box cells with a resolved extent, the share that touch exactly three sides of their frame (a line on the border) and the share that touch all four (the whole frame).

    A margin of 0 on a side means the box touches that side. None without a Box field or a resolved Box cell.
    """
    x = p.x
    idx = [c.index for c in x.columns() if c.type == 'Box']
    if not idx:
        return None
    n = three = four = 0
    for e in x.entries:
        for r in e['rows']:
            for i in idx:
                c = r[i]
                if not _resolved(c) or len(c['value']) != 4:
                    continue
                n += 1
                z = sum(v == 0 for v in c['value'])
                three += z == 3
                four += z == 4
    if not n:
        return None
    return {'edge3': three / n, 'full': four / n}
