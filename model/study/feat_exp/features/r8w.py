"""Round 8, explorer W: what the search can see of a DET table whose later clauses must still fit the train outputs.

W1: the Number cells of X against the side lengths of the boxes that the body reads.
W2: the rows of an object table per example against the cells and colors of the train output.
W3: the colors of the objects that X's Ident column selects, against the train grids.
"""
import collections as C
import math

from featlib import feature

CELL_TYPES = ('Position', 'Box', 'Offset')


def _first(x):
    """{(assignment, example): distinct rows of the first model}; rows are decoded tuples."""
    return {k: list(dict.fromkeys(ms[0])) for k, ms in x.examples().items() if ms}


def _read_tables(p):
    """The available tables that a positive atom of the candidate's body reads."""
    body = p.clause.body
    out = {}
    for atom in body.atoms if body is not None else []:
        if atom.negated or atom.kind not in ('table', 'fact') or atom.interface is None:
            continue
        t = atom.table
        if t is None and atom.kind == 'fact':
            t = p.table(atom.relation)
        if t is not None and t is not p.x:
            out[t.id] = t
    return list(out.values())


def _extents(tables):
    """The side lengths (height and width) of the boxes with a resolved extent in the Box columns of the tables."""
    sides = set()
    seen = False
    for t in tables:
        cols = [c.index for c in t.columns() if c.type == 'Box']
        if not cols:
            continue
        for _, _, _, row in t.rows():
            for i in cols:
                b = row[i]
                if getattr(b, 'size', None) is None:
                    continue
                seen = True
                sides.add(b.size[0] - b.top - b.bottom)
                sides.add(b.size[1] - b.left - b.right)
    return sides if seen else None


@feature
def w1_number_extent(p):
    """W1: over the cells of X's Number columns (rows of the first model of each example, distinct): `ext` the share of cells whose value is the height or the width of a box with a resolved extent, in a Box column of a table that a positive atom of the body reads (None where those tables hold no such box); `neg` the share of negative cells; `ones` the share of cells equal to 1. None without a Number column."""
    x = p.x
    cols = [c.index for c in x.columns() if c.type == 'Number']
    if not cols:
        return None
    vals = [r[i] for rows in _first(x).values() for r in rows for i in cols if isinstance(r[i], int)]
    if not vals:
        return None
    n = len(vals)
    out = {'neg': sum(v < 0 for v in vals) / n, 'ones': sum(v == 1 for v in vals) / n}
    sides = _extents(_read_tables(p))
    if sides is not None:
        out['ext'] = sum(v in sides for v in vals) / n
    return out


def _object_colors(p):
    """[(X column index, [(X key indexes, {(assignment, example): {key tuple: set of colors}})])] for each Ident
    column of X that a positive top-level atom reading a table with one Color column binds from that table's Ident
    column. Ident values are local to their table and the export does not say which tables share them, so a row of
    X is matched to the table's rows by the other columns of that atom that X holds as well (the key; raw values).
    A source with no such column is left out."""
    body = p.clause.body
    out = []
    for atom in body.atoms if body is not None else []:
        if atom.negated or atom.branch or atom.quantifier or atom.conditional or atom.kind != 'table' or atom.interface is None:
            continue
        t = atom.table
        if t is None or t is p.x:
            continue
        tcols = t.columns()
        colors = [c.index for c in tcols if c.type == 'Color']
        if len(colors) != 1:
            continue
        pairs = []
        for a in atom.arguments:
            tc = atom.interface.column(a.name)
            xc = a.variable.column if a.variable is not None else None
            if tc is None or tc.index is None or xc is None or xc.index is None:
                continue
            pairs.append((a, tc, xc))
        for a, tc, xc in pairs:
            if not a.binds or xc.type != 'Ident' or tc.type != 'Ident':
                continue
            keys = sorted({(k.index, kx.index) for _, k, kx in pairs if k.type != 'Ident' and kx.type != 'Ident'})
            if not keys:
                continue
            per = {}
            for key, ms in t.examples(decoded=False).items():
                if ms and ms[0]:
                    d = per[key] = {}
                    for r in ms[0]:
                        d.setdefault(tuple(r[i] for i, _ in keys), set()).add(r[colors[0]])
            out.append((xc.index, keys, per))
    return out


@feature
def w3_object_colors(p):
    """W3: for each Ident column of X that a positive top-level atom binds from the Ident column of an available table with a Color column, the color of each object X holds (the table's Color cell in the row found by the other columns of that atom that X holds as well, in the same example; Ident values are not compared across tables, and an atom without such a column, a table without exactly one Color column, and an object whose columns match rows of two colors are left out): `out` the share of objects whose color occurs in that example's train output, `bg` the share whose color is the input's most common color, `miss` the share of objects with no row in the table. Pooled over examples and columns. None without such a column. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    sources = _object_colors(p)
    if not sources:
        return None
    grids = {e.index: e for e in p.examples()}
    rows_by = {k: list(dict.fromkeys(ms[0])) for k, ms in p.x.examples(decoded=False).items() if ms}
    n = out = bg = miss = 0
    for xi, keys, per in sources:
        for (a, ei), rows in rows_by.items():
            ex = grids.get(ei)
            m = per.get((a, ei))
            if ex is None or m is None:
                continue
            outc = set(ex.output.colors())
            back = min(ex.input.most_common())
            for r in rows:
                if not r[xi]:
                    continue
                got = m.get(tuple(r[i] for _, i in keys))
                if got is not None and len(got) > 1:
                    continue
                n += 1
                if got is None:
                    miss += 1
                    continue
                (c,) = got
                c = c[0] if len(c) == 1 else c
                out += c in outc
                bg += c == back
    if not n:
        return None
    return {'out': out / n, 'bg': bg / n, 'miss': miss / n}
