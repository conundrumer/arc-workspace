"""Round 6, explorer P: what the lost rows of a lossy X leave behind, whatever its size.

P1: whether a Number column of X holds the sizes of the train grids.
P2: the shape of the cell set of a Position column: holes and notches.
P3: whether X holds the values that an earlier port of the same INIT supplies.
P4: Number columns that keep one value in every example.
P5: the share of the matter cells (changed, foreground) that a source table holds and X dropped.
P6: the share of the changed regions and of the input's objects that X touches.
P7: how much of a column of X one value holds.
P8: P5 for Box columns.
P9: the output's colors that a source table holds in a column and X's column dropped.

Types, frames, the correspondence of X's columns to the form's variables and the tables a variable is read from come
from featlib's typed access. All the features read the first model of each context.
"""
import collections as C

from featlib import feature

NOMINAL = ('Number', 'Color', 'Dir', 'Dir8', 'DiagDir', 'Axis', 'C4', 'D4', 'Sense', 'Sym')


def _contexts(table):
    """{(assignment, example): rows of the first model}; a row is a tuple of decoded cells."""
    return {key: models[0] for key, models in table.examples().items() if models}


def _example(p, index):
    exs = p.examples()
    return exs[index] if 0 <= index < len(exs) else None


def _components(cells):
    """8-connected components of a set of (row, column) cells."""
    cells = set(cells)
    seen = set()
    out = []
    for s in sorted(cells):
        if s in seen:
            continue
        seen.add(s)
        stack, comp = [s], []
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    n = (r + dr, c + dc)
                    if n in cells and n not in seen:
                        seen.add(n)
                        stack.append(n)
        out.append(comp)
    return out


def _background(grid):
    """The smallest of the colors with the most cells."""
    return min(grid.most_common())


# ---------------------------------------------------------------- P1

@feature
def p1_number_ground(p):
    """P1: over the Number columns of X, per context: whether their values together hold both sides of the train output (out), both sides of the train input (inn), the output sides without the input sides on examples where the two differ (out_only), and a count of at least 3 that the grids show (cnt: the cells of one color of the input or output, or the cells off the most common color). Shares over contexts; None without a Number column. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    cols = [c.index for c in x.columns() if c.type == 'Number']
    if not cols:
        return None
    n = out = inn = only = differ = cnt = 0
    for (_, ei), rows in _contexts(x).items():
        ex = _example(p, ei)
        if ex is None or not rows:
            continue
        (hi, wi), (ho, wo) = ex.input.size, ex.output.size
        vals = {r[i] for r in rows for i in cols if isinstance(r[i], int)}
        counts = set()
        for grid in (ex.input, ex.output):
            count = grid.colors()
            counts |= set(count.values())
            counts.add(sum(count.values()) - max(count.values()))
        counts = {c for c in counts if c >= 3} - {hi, wi, ho, wo}
        n += 1
        has_out = ho in vals and wo in vals
        has_in = hi in vals and wi in vals
        out += has_out
        inn += has_in
        if (hi, wi) != (ho, wo):
            differ += 1
            only += has_out and not has_in
        cnt += bool(vals & counts)
    if not n:
        return None
    res = {'out': out / n, 'inn': inn / n, 'cnt': cnt / n}
    if differ:
        res['out_only'] = only / differ
    return res


# ---------------------------------------------------------------- P2

def _gaps(cells):
    """Cells outside the set that have a cell of the set on both sides in a row or in a column."""
    gaps = set()
    for r, c in cells:
        for dr, dc in ((0, 2), (2, 0)):
            if (r + dr, c + dc) in cells:
                mid = (r + dr // 2, c + dc // 2)
                if mid not in cells:
                    gaps.add(mid)
    return len(gaps)


def _fill(cells):
    """Cells of the set over the cells in the bounding boxes of its 8-connected components."""
    area = 0
    for comp in _components(cells):
        rs = [r for r, _ in comp]
        cs = [c for _, c in comp]
        area += (max(rs) - min(rs) + 1) * (max(cs) - min(cs) + 1)
    return len(cells) / area if area else 1.0


@feature
def p2_cell_shape(p):
    """P2: for each Position column of X, per context, the distinct cells (top, left): fill (cells over the cells in the bounding boxes of the 8-connected components) and gap (cells outside the set with the set on both sides in a row or a column, over the cells). Contexts weigh by their cells. fill is the smallest and gap the largest over columns. None without a Position column of 3 cells."""
    x = p.x
    fills, gaps = [], []
    contexts = _contexts(x)
    for col in x.columns():
        if col.type != 'Position':
            continue
        tot = fsum = gsum = 0.0
        for rows in contexts.values():
            cells = {r[col.index].cell for r in rows}
            if len(cells) < 3:
                continue
            tot += len(cells)
            fsum += len(cells) * _fill(cells)
            gsum += _gaps(cells)
        if tot >= 3:
            fills.append(fsum / tot)
            gaps.append(gsum / tot)
    if not fills:
        return None
    return {'fill': min(fills), 'gap': max(gaps)}


# ---------------------------------------------------------------- P3

def _top_level(atom):
    return atom is not None and not (atom.negated or atom.branch or atom.quantifier or atom.conditional)


def _source(p, atom):
    """The Table an atom reads (an available table or a fact's table), or None."""
    if atom is None or atom.interface is None:
        return None
    t = atom.table
    if t is None and atom.kind == 'fact':
        t = p.table(atom.relation)
    return t


@feature
def p3_port_cover(p):
    """P3: at an INIT point, for each head column of an earlier port of the same INIT whose label an atom of that port (outside OR, NOT, IF and ALL) binds from a Position or Box column of an available table: the share of that table column's distinct values, per context, that a Position or Box column of X holds (the best X column; the values compare as four margins). held_min and held_mean over the earlier columns, n their number. None without such a column."""
    clause = p.clause
    if clause is None or not clause.before:
        return None
    x = p.x
    xcols = [c.index for c in x.columns() if c.type in ('Position', 'Box')]
    if not xcols:
        return None
    xctx = _contexts(x)
    shares = []
    for scope in clause.before:
        for head in scope.head:
            var = head.variable
            if var is None:
                continue
            for site in var.binders:
                atom = site.atom
                if not _top_level(atom) or atom.scope is not scope:
                    continue
                t = _source(p, atom)
                col = t.column(site.name) if t is not None else None
                if col is None or col.type not in ('Position', 'Box'):
                    continue
                best = 0.0
                tctx = _contexts(t)
                for c in xcols:
                    inter = total = 0
                    for key, trows in tctx.items():
                        if key not in xctx:
                            continue
                        sv = {r[col.index].margins for r in trows}
                        if not sv:
                            continue
                        xv = {r[c].margins for r in xctx[key]}
                        inter += len(sv & xv)
                        total += len(sv)
                    if total:
                        best = max(best, inter / total)
                shares.append(best)
    if not shares:
        return None
    return {'held_min': min(shares), 'held_mean': sum(shares) / len(shares), 'n': len(shares)}


# ---------------------------------------------------------------- P4

@feature
def p4_dead_number(p):
    """P4: over the Number columns of X, those with one value in every context that has 2 or more rows (dead, when at least 2 such contexts), their share of the Number columns, and the share of the (column, context) pairs with one value (flat). None without a Number column or without a context of 2 rows."""
    x = p.x
    cols = [c.index for c in x.columns() if c.type == 'Number']
    if not cols:
        return None
    ctxs = [rows for rows in _contexts(x).values() if len(rows) >= 2]
    if not ctxs:
        return None
    dead = flat = 0
    for c in cols:
        one = [len({r[c] for r in rows}) == 1 for rows in ctxs]
        flat += sum(one)
        dead += len(ctxs) >= 2 and all(one)
    return {'dead': dead, 'share': dead / len(cols), 'flat': flat / (len(cols) * len(ctxs))}


# ---------------------------------------------------------------- P5, P8 and P9

def _bound_pairs(p, kinds):
    """(source table, source column index, X column index, X column) for each X column of a type in kinds whose
    variable an atom outside OR, NOT, IF and ALL binds from a column of that type of an available table."""
    clause = p.clause
    if clause is None or clause.body is None:
        return []
    x = p.x
    out = []
    for xc in x.columns():
        var = clause.x_columns.get(xc.name)
        if var is None or xc.type not in kinds:
            continue
        for site in var.binders:
            atom = site.atom
            if not _top_level(atom) or atom.kind not in ('table', 'fact'):
                continue
            t = _source(p, atom)
            if t is None or any(c.type == 'Example' for c in t.columns()):
                continue
            col = t.column(site.name)
            if col is not None and col.type == xc.type:
                out.append((t, col.index, xc.index))
    return out


def _cell_set(rows, ci, size):
    """The distinct cells (top, left) of a Position column, or None if a cell has another frame size than the grid."""
    out = set()
    for r in rows:
        m = r[ci]
        if m.size is not None and m.size != size:
            return None
        out.add(m.cell)
    return out


@feature
def p5_source_loss(p):
    """P5: for each Position column of X whose variable an atom outside OR, NOT, IF and ALL binds from a Position column of an available table, per context whose cells carry the grid's frame size: the share of the matter cells that the source column holds and X's column does not, over the matter cells that the source holds. The matter cells are the cells where the train output differs from the input (lost; contexts where the two grids have one size) and the input cells off its most common color (fg). Sums over contexts. lost_max and lost_min over the pairs, n their number; fg_max, fg_min and fg_n the same for the foreground. None without such a pair or without a matter cell in a source. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    xctx = _contexts(p.x)
    losses, fgs = [], []
    for t, ti, c in _bound_pairs(p, ('Position',)):
        tctx = _contexts(t)
        lost = need = fg_lost = fg_need = 0
        ok = True
        for key, trows in tctx.items():
            ex = _example(p, key[1])
            if key not in xctx or ex is None:
                continue
            size = ex.input.size
            src = _cell_set(trows, ti, size)
            held = _cell_set(xctx[key], c, size)
            if src is None or held is None:
                ok = False
                break
            bg = _background(ex.input)
            fg = {(r, q) for r in range(size[0]) for q in range(size[1]) if ex.input[r, q] != bg}
            fg_need += len(src & fg)
            fg_lost += len((src - held) & fg)
            changed = ex.changed()
            if changed is not None:
                need += len(src & changed)
                lost += len((src - held) & changed)
        if ok and need:
            losses.append(lost / need)
        if ok and fg_need:
            fgs.append(fg_lost / fg_need)
    res = {}
    if losses:
        res.update({'lost_max': max(losses), 'lost_min': min(losses), 'n': len(losses)})
    if fgs:
        res.update({'fg_max': max(fgs), 'fg_min': min(fgs), 'fg_n': len(fgs)})
    return res or None


def _boxes(rows, ci, size):
    """The distinct boxes (top, bottom, left, right) of a Box column that lie inside the grid, or None if a box has
    another frame size than the grid."""
    out = set()
    h, w = size
    for r in rows:
        m = r[ci]
        if m.size is not None and m.size != size:
            return None
        t, b, l, rt = m.margins
        if min(m.margins) >= 0 and t + b <= h - 1 and l + rt <= w - 1:
            out.add(m.margins)
    return out


def _in_boxes(cell, boxes, size):
    r, c = cell
    h, w = size
    return any(t <= r <= h - 1 - b and l <= c <= w - 1 - rt for t, b, l, rt in boxes)


@feature
def p8_box_source_loss(p):
    """P8: for each Box column of X whose variable an atom outside OR, NOT, IF and ALL binds from a Box column of an available table, per context where the train input and output have one size and the boxes carry the grid's frame size: the share of the changed cells that lie in a box of the source column and in no box of X's column, over the changed cells that lie in a box of the source column; summed over contexts. lost_max and lost_min over the pairs. None without such a pair or without a changed cell in a source box. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    xctx = _contexts(p.x)
    losses = []
    for t, ti, c in _bound_pairs(p, ('Box',)):
        lost = need = 0
        ok = True
        for key, trows in _contexts(t).items():
            ex = _example(p, key[1])
            if key not in xctx or ex is None or ex.changed() is None:
                continue
            size = ex.input.size
            src = _boxes(trows, ti, size)
            held = _boxes(xctx[key], c, size)
            if src is None or held is None:
                ok = False
                break
            inside = [cell for cell in sorted(ex.changed()) if _in_boxes(cell, src, size)]
            need += len(inside)
            lost += sum(not _in_boxes(cell, held, size) for cell in inside)
        if ok and need:
            losses.append(lost / need)
    if not losses:
        return None
    return {'lost_max': max(losses), 'lost_min': min(losses), 'n': len(losses)}


@feature
def p9_color_source_loss(p):
    """P9: for each Color column of X whose variable an atom outside OR, NOT, IF and ALL binds from a Color column of an available table: per context, the colors of the train output other than the input's most common color that the source column holds and X's column does not, over those that the source column holds; summed over contexts. lost_max and lost_min over the pairs, n their number. None without such a pair or without such a color in a source. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    xctx = _contexts(p.x)
    losses = []
    for t, ti, c in _bound_pairs(p, ('Color',)):
        lost = need = 0
        for key, trows in _contexts(t).items():
            ex = _example(p, key[1])
            if key not in xctx or ex is None:
                continue
            wanted = set(ex.output.colors()) - {_background(ex.input)}
            src = {r[ti] for r in trows} & wanted
            held = {r[c] for r in xctx[key]}
            need += len(src)
            lost += len(src - held)
        if need:
            losses.append(lost / need)
    if not losses:
        return None
    return {'lost_max': max(losses), 'lost_min': min(losses), 'n': len(losses)}


# ---------------------------------------------------------------- P6

@feature
def p6_region_touch(p):
    """P6: for each Position column of X whose frame is the input (or whose cells all carry the frame size of the grid), on contexts where the train input and output have one size: the share of the 8-connected regions of changed cells that the column holds a cell of (chg), and the share of the 8-connected regions of input cells off the most common color that it holds a cell of (fg); the column with the largest chg, then the largest fg. None without such a column or without a changed cell. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    contexts = _contexts(x)
    best = None
    for col in x.columns():
        if col.type != 'Position' or col.frame_kind == 'output':
            continue
        tot_c = hit_c = tot_f = hit_f = 0
        ok = True
        for (_, ei), rows in contexts.items():
            ex = _example(p, ei)
            if ex is None or ex.changed() is None:
                continue
            size = ex.input.size
            cells = _cell_set(rows, col.index, size)
            if cells is None or (col.frame_kind != 'input' and any(r[col.index].size is None for r in rows)):
                ok = False
                break
            bg = _background(ex.input)
            fg = {(r, q) for r in range(size[0]) for q in range(size[1]) if ex.input[r, q] != bg}
            for comp in _components(ex.changed()):
                tot_c += 1
                hit_c += any(c in cells for c in comp)
            for comp in _components(fg):
                tot_f += 1
                hit_f += any(c in cells for c in comp)
        if not ok or not tot_c:
            continue
        cand = {'chg': hit_c / tot_c, 'fg': hit_f / tot_f if tot_f else 1.0}
        if best is None or (cand['chg'], cand['fg']) > (best['chg'], best['fg']):
            best = cand
    return best


# ---------------------------------------------------------------- P7

@feature
def p7_mode_share(p):
    """P7: over the Number, Color, Dir, Dir8, DiagDir and Axis columns of X, per context of 2 or more rows: the share of rows that hold the column's most common value. mode_max is the largest and mode_mean the mean, over columns, of that share averaged over contexts; flat_other the number of non-Number columns with one value in every context of 2 or more rows (when there are 2 such contexts). None without such a column or context."""
    x = p.x
    cols = [c for c in x.columns() if c.type in NOMINAL]
    ctxs = [rows for rows in _contexts(x).values() if len(rows) >= 2]
    if not cols or not ctxs:
        return None
    shares, flat_other = [], 0
    for col in cols:
        per = [max(C.Counter(r[col.index] for r in rows).values()) / len(rows) for rows in ctxs]
        shares.append(sum(per) / len(per))
        if col.type != 'Number' and len(ctxs) >= 2 and all(s == 1.0 for s in per):
            flat_other += 1
    return {'mode_max': max(shares), 'mode_mean': sum(shares) / len(shares), 'flat_other': flat_other}
