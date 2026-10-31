"""G8 keeps_source: X keeps the values of the tables its form reads.

For each X column that a top-level atom of the form binds from a column of an available table, the share of that
source column's values (per context) that X's column holds. A second set of keys restricts the source values to the
ones that matter in the train grids. All shares only fall as atoms are added to a body that makes no new column.

Everything is read through the typed access: the atoms, the variables and their X columns, the tables the atoms read,
the INIT's earlier ports (`p.clause.before`) and the library's component. No form text and no name is read.
"""
import collections as C

import numpy as np

from featlib import feature, ident_group


def _top(atom):
    return atom is not None and not (atom.negated or atom.branch or atom.quantifier or atom.conditional
                                     or atom.operator)


def _source(p, atom):
    """The Table an atom reads (an available table or a fact's table), or None."""
    if atom is None or atom.interface is None:
        return None
    t = atom.table
    if t is None and atom.kind == 'fact':
        t = p.table(atom.relation)
    return t


def _bound(p):
    """[(atom, source table, [(source Column, X Column)])] for each top-level atom that reads a table without an
    Example column and stars labels that are columns of X."""
    body = p.clause.body
    out = []
    for atom in body.atoms if body is not None else []:
        if not _top(atom) or atom.kind not in ('table', 'fact'):
            continue
        t = _source(p, atom)
        if t is None or any(c.type == 'Example' for c in t.columns()):
            continue
        pairs = []
        for a in atom.arguments:
            tc = atom.interface.column(a.name)
            xc = a.variable.column if a.binds and a.variable is not None else None
            if tc is not None and tc.index is not None and xc is not None and xc.index is not None:
                pairs.append((tc, xc))
        if pairs:
            out.append((atom, t, pairs))
    return out


def _background(grid):
    """The smallest of the colors with the most cells."""
    return min(grid.most_common())


def _cells(rows, ci, size):
    """The cells (top, left) of a Position column that lie on a grid of that size."""
    h, w = size
    out = set()
    for r in rows:
        m = r[ci]
        if not hasattr(m, 'margins'):
            continue
        t, b, l, rt = m.margins
        if min(m.margins) >= 0 and t + b == h - 1 and l + rt == w - 1:
            out.add((t, l))
    return out


def _mask(rows, ci, size):
    """The cells of the grid that some box of a Box column covers (a box outside the grid is left out)."""
    h, w = size
    out = np.zeros((h, w), dtype=bool)
    for r in rows:
        m = r[ci]
        if not hasattr(m, 'margins'):
            continue
        t, b, l, rt = m.margins
        if min(m.margins) >= 0 and t + b <= h - 1 and l + rt <= w - 1:
            out[t:h - b, l:w - rt] = True
    return out


def _matter(p, t, tc, xc, tdec, xdec, xkeys):
    """Kept and needed counts of one (source column, X column) pair over the source values that matter in the train
    grids: {kind: [kept, need]} with kinds `chg` (cells the output changes) and `fg` (cells off the input's most
    common color) for a Position column, `box` (changed cells under a source box) for a Box column, `color` (output
    colors other than the input's most common color) for a Color column. A Position or Box column counts where its
    frame tag is `input` or `output` (`fg`: `input`), and `chg` and `box` on examples whose grids have one size."""
    kind = xc.type
    tag = xc.frame_kind
    if kind in ('Position', 'Box') and tag not in ('input', 'output'):
        return {}
    acc = C.defaultdict(lambda: [0, 0])
    examples = p.examples()
    for key, tmodels in tdec.items():
        if key not in xkeys or key[1] >= len(examples) or not tmodels:
            continue
        ex = examples[key[1]]
        xmodels = xdec.get(key)
        xrows = xmodels[0] if xmodels else []
        trows = tmodels[0]
        grid = ex.input if tag == 'input' else ex.output
        if kind == 'Color':
            wanted = set(ex.output.colors()) - {_background(ex.input)}
            src = {r[tc.index] for r in trows} & wanted
            held = {r[xc.index] for r in xrows}
            acc['color'][0] += len(src & held)
            acc['color'][1] += len(src)
            continue
        size = grid.size
        changed = ex.changed()
        if kind == 'Position':
            src = _cells(trows, tc.index, size)
            held = _cells(xrows, xc.index, size)
            if changed is not None:
                acc['chg'][0] += len(src & held & changed)
                acc['chg'][1] += len(src & changed)
            if tag == 'input':
                fg = {(r, q) for r in range(size[0]) for q in range(size[1]) if ex.input[r, q] != _background(ex.input)}
                acc['fg'][0] += len(src & held & fg)
                acc['fg'][1] += len(src & fg)
        elif kind == 'Box' and changed is not None:
            ch = np.zeros(size, dtype=bool)
            for r, q in changed:
                ch[r, q] = True
            src = _mask(trows, tc.index, size) & ch
            held = _mask(xrows, xc.index, size) & src
            acc['box'][0] += int(held.sum())
            acc['box'][1] += int(src.sum())
    return {k: v for k, v in acc.items() if v[1]}


@feature
def g8_keeps_source(p):
    """G8 keeps_source: the share of a source table's values that X's columns keep, per X column that a top-level atom of the form binds from a column of the same type of an available table (outside OR, NOT, IF, ALL; tables with an Example column are left out).

    min, mean: the smallest and mean share over such columns, of the source column's distinct values (per context, summed over contexts) that X's column holds; lost: the number of columns below 1.
    ident_min: the smallest share over Ident columns, by count (min of 1 and the ratio of distinct counts) where X and the source do not share Ident values, else by value.
    rows_min: the smallest, over atoms that star two or more columns, of the share of the source's distinct rows projected on the starred columns that X's projection holds (Ident columns only where X and the source share Ident values).
    chg_min, fg_min, box_min, color_min: the smallest share over columns of the source values that matter in the train grids that X keeps: the changed cells of a Position column with frame tag input or output, the input's foreground cells of a Position column with tag input, the changed cells under a source box of a Box column with tag input or output (examples with one grid size), and the output's colors other than the input's most common color for a Color column. matter_min is the smallest of the four.
    A context that X lacks is skipped. None if no column qualifies. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so its rows would be compared with one example's rows of an earlier table.
    Needs: partial. Monotone: yes (a share only falls under positive atoms, NOT, comparisons and a complete OR; a new table read adds a term that can only lower the minima).
    """
    if p.kind == 'Det':
        return None
    x = p.x
    xkeys = {(e['assignment'], e['train']) for e in x.entries}
    xraw, xdec = x.examples(decoded=False), None
    shares, idents, rows_shares = {}, [], []
    matter = C.defaultdict(list)
    for atom, t, pairs in _bound(p):
        traw = t.examples(decoded=False)
        tdec = None
        keep = []
        for tc, xc in pairs:
            if tc.type != xc.type or tc.type in ('Example', 'Axis'):
                continue
            same_ident = ident_group(t) == ident_group(x)
            ident = tc.type == 'Ident'
            inter = total = 0
            for key, tmodels in traw.items():
                if key not in xkeys or not tmodels:
                    continue
                sv = {r[tc.index] for r in tmodels[0]}
                if not sv:
                    continue
                xm = xraw.get(key)
                xv = {r[xc.index] for r in (xm[0] if xm else [])}
                inter += min(len(sv), len(xv)) if ident and not same_ident else len(sv & xv)
                total += len(sv)
            if total and xc.index not in shares:
                shares[xc.index] = inter / total
                if ident:
                    idents.append(inter / total)
            if not ident or same_ident:
                keep.append((tc, xc))
            if xc.type in ('Position', 'Box', 'Color'):
                if tdec is None:
                    tdec = t.examples()
                    xdec = xdec if xdec is not None else x.examples()
                for kind, (kept, need) in _matter(p, t, tc, xc, tdec, xdec, xkeys).items():
                    matter[kind].append(kept / need)
        if len(keep) >= 2:
            ti, xi = [tc.index for tc, _ in keep], [xc.index for _, xc in keep]
            inter = total = 0
            for key, tmodels in traw.items():
                if key not in xkeys or not tmodels:
                    continue
                tp = {tuple(r[i] for i in ti) for r in tmodels[0]}
                if not tp:
                    continue
                xm = xraw.get(key)
                xp = {tuple(r[i] for i in xi) for r in (xm[0] if xm else [])}
                inter += len(tp & xp)
                total += len(tp)
            if total:
                rows_shares.append(inter / total)
    if not shares:
        return None
    vals = list(shares.values())
    out = {'min': min(vals), 'mean': sum(vals) / len(vals), 'lost': sum(v < 1.0 for v in vals)}
    if idents:
        out['ident_min'] = min(idents)
    if rows_shares:
        out['rows_min'] = min(rows_shares)
    for kind in ('chg', 'fg', 'box', 'color'):
        if matter[kind]:
            out[kind + '_min'] = min(matter[kind])
    allm = [v for vs in matter.values() for v in vs]
    if allm:
        out['matter_min'] = min(allm)
    return out


@feature
def g8_earlier_ports(p):
    """G8 keeps_source: at an INIT point, the share of the values that an earlier port of the same INIT takes from a table, which X holds.

    port_min, port_mean: over the head columns of the earlier ports whose label an atom of that port (outside OR, NOT, IF and ALL) binds from a Position or Box column of a table, the smallest and the mean of the best share, over X's Position and Box columns, of that table column's distinct values (per context, summed) that the X column holds; n: the number of such head columns.
    None without such a column or an X cell column.
    Needs: partial. Monotone: yes (the share only falls; `port_min` is the minimum of shares).
    """
    clause = p.clause
    if clause is None or not clause.before:
        return None
    x = p.x
    xcols = [c for c in x.columns() if c.type in ('Position', 'Box')]
    if not xcols:
        return None
    xkeys = {(e['assignment'], e['train']) for e in x.entries}
    xraw = x.examples(decoded=False)
    shares = []
    for scope in clause.before:
        for head in scope.head:
            var = head.variable
            if var is None:
                continue
            for site in var.binders:
                atom = site.atom
                if not _top(atom) or atom.scope is not scope or atom.kind not in ('table', 'fact'):
                    continue
                t = _source(p, atom)
                col = t.column(site.name) if t is not None else None
                if col is None or col.type not in ('Position', 'Box'):
                    continue
                traw = t.examples(decoded=False)
                best = 0.0
                for c in xcols:
                    inter = total = 0
                    for key, tmodels in traw.items():
                        if key not in xkeys or not tmodels:
                            continue
                        sv = {r[col.index] for r in tmodels[0]}
                        if not sv:
                            continue
                        xm = xraw.get(key)
                        xv = {r[c.index] for r in (xm[0] if xm else [])}
                        inter += len(sv & xv)
                        total += len(sv)
                    if total:
                        best = max(best, inter / total)
                shares.append(best)
    if not shares:
        return None
    return {'port_min': min(shares), 'port_mean': sum(shares) / len(shares), 'n': len(shares)}
