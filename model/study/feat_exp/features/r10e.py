"""Round 10, explorer e: sampler draws that give a real view of the grids but lie off the path.

Three families, each read from the train grids, the tables built before the point and X only:
- e1: X is a copy of a table built before the point, and how large that table is among them.
- e2: X's input-frame cells are objects that the task leaves unchanged.
- e3: X's input-frame cells are made of whole color classes of the input.
A Position column is read against the train grids only where its frame tag is `input` (as G11 does); a context that X has
with no row is skipped. Tables 'ex_input' and 'ex_output' (every example's grid, task level) are not counted as tables
that X could copy.
"""
import itertools

from featlib import ORIENTATION_TYPES, feature

MAX_TABLE_ROWS = 20000
MAX_MAPPINGS = 24
CELL_TYPES = ('Position', 'Box')


def _contexts(table, keep=None):
    """(assignment, train) -> set of rows (tuples of cell values) over the context's models, restricted to keep."""
    out = {}
    for e in table.entries:
        rows = out.setdefault((e['assignment'], e['train']), set())
        for r in e['rows']:
            rows.add(tuple(tuple(r[i]['value']) for i in keep) if keep is not None else tuple(tuple(c['value']) for c in r))
    return out


def _mappings(xcols, table):
    """Every injective map from X's kept columns onto columns of the table with equal type and compatible frame tag
    (equal, or one of them empty); none when there are more than MAX_MAPPINGS."""
    tcols = table.columns()
    cands = [[t.index for t in tcols if t.type == c.type and (t.frame == c.frame or not t.frame or not c.frame)]
             for c in xcols]
    out = []
    for combo in itertools.product(*cands):
        if len(set(combo)) == len(combo):
            out.append(combo)
            if len(out) > MAX_MAPPINGS:
                return []
    return out


def _mean_rows(table):
    ctx = _contexts(table)
    return sum(len(v) for v in ctx.values()) / len(ctx) if ctx else 0.0


@feature
def e1_copy_rank(p):
    """E1: whether X equals a table built before the point, and how large that table is among the tables with cells.

    copy: 1 when some table's projection on columns of X's types equals X (without Ident and Example) in every shared
    context, 0 otherwise. rank: for the largest matching table, the share of the tables with a Position or Box column
    that have fewer rows per context; top: 1 when no such table has more.
    None when X has no column other than Ident and Example, or every column is
    of an orientation type.
    """
    x = p.x
    xcols = [c for c in x.columns() if c.type not in ('Ident', 'Example')]
    if not xcols or not x.entries or all(c.type in ORIENTATION_TYPES for c in xcols):
        return None
    xs = _contexts(x, [c.index for c in xcols])
    universe = []
    matched = []
    for t in p.available():
        if t.name in ('ex_input', 'ex_output') or sum(len(e['rows']) for e in t.entries) > MAX_TABLE_ROWS:
            continue
        size = _mean_rows(t)
        if any(c.type in CELL_TYPES for c in t.columns()):
            universe.append(size)
        for mp in _mappings(xcols, t):
            ts = _contexts(t, list(mp))
            shared = [k for k in xs if k in ts]
            if shared and all(xs[k] == ts[k] for k in shared):
                matched.append((size, t))
                break
    if not matched:
        return {'copy': 0}
    size, t = max(matched, key=lambda m: m[0])
    below = sum(1 for s in universe if s < size)
    return {'copy': 1, 'rank': below / len(universe) if universe else 0.0,
            'top': int(not any(s > size for s in universe))}


def _input_cells(p):
    """[(grid, example, held cells)] for each input-frame Position column of X and context, as lists per column:
    {column index: [(example, held set)]}. A cell counts when it lies on the input grid."""
    x = p.x
    cols = [c for c in x.columns() if c.type == 'Position' and c.frame_kind == 'input']
    if not cols or p.kind == 'Det':
        return None
    exs = p.examples()
    ex = x.examples()
    has_ex = any(c.type == 'Example' for c in x.columns())
    keys = {(e['assignment'], e['train']) for e in x.entries}
    out = {}
    for col in cols:
        per = []
        for (a, k) in keys:
            if k >= len(exs):
                continue
            rows = ex.get((a, k))
            rows = rows[0] if rows else []
            h, w = exs[k].input.size
            held = set()
            for r in rows:
                m = r[col.index]
                if hasattr(m, 'margins') and min(m.margins) >= 0 and m.top + m.bottom == h - 1 \
                        and m.left + m.right == w - 1:
                    held.add((m.top, m.left))
            per.append((exs[k], held))
        out[col.index] = per
    return out


@feature
def e2_unchanged_object(p):
    """E2: how much of X's input-frame cells is foreground that the task leaves unchanged.

    The foreground of a train input is its cells off its most common color (the smallest color on a tie); changed cells
    are the cells where the output differs from the input, in the examples whose two grids have one size. For the
    input-frame Position column with the largest `obj`: obj, the mean share of its distinct cells that are foreground
    and unchanged; chg_zero, 1 when no cell of the column is changed in any such example and the column holds a cell
    there. None without an input-frame Position column, or without an example of one size that the column holds a cell in.
    """
    cols = _input_cells(p)
    if not cols:
        return None
    best = None
    for per in cols.values():
        obj = []
        nchg = 0
        for e, held in per:
            if not held:
                continue
            ch = e.changed()
            if ch is None:
                continue
            g = e.input
            back = min(g.most_common())
            fgset = {(r, c) for r in range(g.height) for c in range(g.width) if g[r, c] != back}
            obj.append(len(held & fgset - ch) / len(held))
            nchg += len(held & ch)
        if obj:
            res = {'obj': sum(obj) / len(obj), 'chg_zero': int(nchg == 0)}
            if best is None or res['obj'] > best['obj']:
                best = res
    return best


@feature
def e3_color_class(p):
    """E3: whether X's input-frame cells are made of whole color classes of the input.

    A color class is the set of the input's cells of one color. For the input-frame Position column that holds the most
    cells: union, 1 when in every example each class is held entirely or not at all; classes, the mean number of
    classes the column touches; partial, the mean share of the touched classes that it holds in part only. None without
    an input-frame Position column that holds a cell.
    """
    cols = _input_cells(p)
    if not cols:
        return None
    col = max(cols.values(), key=lambda per: sum(len(h) for _, h in per))
    union, ncls, part, n = 1, 0.0, 0.0, 0
    for e, held in col:
        if not held:
            continue
        g = e.input
        by = {}
        for r in range(g.height):
            for c in range(g.width):
                by.setdefault(g[r, c], set()).add((r, c))
        touched = [(cl, cells) for cl, cells in by.items() if cells & held]
        partial = [1 for cl, cells in touched if not cells <= held]
        union &= not partial
        ncls += len(touched)
        part += len(partial) / len(touched) if touched else 0.0
        n += 1
    if not n:
        return None
    return {'union': int(union), 'classes': ncls / n, 'partial': part / n}
