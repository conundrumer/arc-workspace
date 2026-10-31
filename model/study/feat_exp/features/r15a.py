"""Round 15, explorer a: what X's content says about the train grids, judged against the tables visible at the point.

A feature reads the train inputs and outputs, the available tables (not the target ones), X and its types and frames.
"""
import collections as C
import math

from featlib import feature

MAX_ROWS = 20000


def _first(models):
    return models[0] if models else []


def _ctx_rows(table):
    """{(assignment, example): rows of the first model}, for a table (decoded rows)."""
    try:
        return {k: _first(v) for k, v in table.examples().items()}
    except Exception:
        return {}


def _pos_cols(table, frame=None):
    out = []
    for c in table.columns():
        if c.type == 'Position' and (frame is None or c.frame == frame):
            out.append(c)
    return out


def _visible(p):
    out = []
    try:
        for t in p.available():
            out.append(t)
    except Exception:
        pass
    return out


def _by_example(ctx):
    """{example: rows} taking the lowest assignment that holds the example."""
    out = {}
    for (a, e) in sorted(ctx, key=lambda k: (str(k[0]), str(k[1]))):
        out.setdefault(e, ctx[(a, e)])
    return out


def _partitions(table, frame):
    """Per visible table with a Position column of `frame`: for each other column, {example: {value: frozenset cells}}.
    Returns a list of (label, parts) with parts {example: [frozenset, ...]}."""
    pcols = _pos_cols(table, frame)
    if not pcols:
        return []
    cols = table.columns()
    pi = pcols[0].index if pcols[0].index is not None else cols.index(pcols[0])
    byex = _by_example(_ctx_rows(table))
    out = []
    for qi, c in enumerate(cols):
        if qi == pi or c.type in ('Example', 'Position', 'Box', 'Offset'):
            continue
        parts = {}
        for e, rows in byex.items():
            if len(rows) > MAX_ROWS:
                parts = None
                break
            d = C.defaultdict(set)
            for r in rows:
                cell = getattr(r[pi], 'cell', None)
                if cell is not None:
                    d[r[qi]].add(cell)
            parts[e] = [frozenset(s) for s in d.values()]
        if parts:
            out.append((table.name, c.name, parts))
    return out


def _box_parts(table, frame, sizes):
    """For each Box column of `frame` in a visible table: {example: [frozenset of the cells of each distinct box]}."""
    out = []
    cols = table.columns()
    byex = _by_example(_ctx_rows(table))
    for i, c in enumerate(cols):
        if c.type != 'Box' or c.frame != frame:
            continue
        parts = {}
        for e, rows in byex.items():
            hw = sizes.get(e)
            if hw is None or len(rows) > MAX_ROWS:
                continue
            h, w = hw
            seen = set()
            for r in rows:
                m = getattr(r[i], 'margins', None)
                if m:
                    seen.add(m)
            parts[e] = [frozenset((a, b) for a in range(t, h - bo) for b in range(l, w - ri))
                        for (t, bo, l, ri) in seen][:2000]
        if parts:
            out.append((table.name, c.name, parts))
    return out


@feature
def a1_union_of_classes(p):
    """A1 Whether X's cell set restates visible structure. X's first Position column in a grid frame gives the cell set
    S of each example. A visible table with a Position column of that frame and another column Q gives the classes (the
    cells that share a Q value); a visible table with a Box column of that frame gives the classes (the cells of each
    of its boxes). `exact` is the share of contexts where, for some partition of the first kind with at least two
    classes of mean size at least 2, the classes inside S cover S exactly and not every class lies inside S; `cover` is
    the largest share of S that such classes cover, over those partitions; `kfrac` the least share of classes needed
    among the exact partitions (1 where none); `box_exact` and `box_cover` are the same for the box classes.

    Needs: full X, available tables, train grids. Monotone: no.
    """
    try:
        x = p.x
        xcols = [c for c in x.columns() if c.type == 'Position' and c.frame in ('input', 'output')]
        if not xcols:
            return None
        xc = xcols[0]
        frame = xc.frame
        xi = xc.index if xc.index is not None else x.columns().index(xc)
        sizes = {e.index: (e.input if frame == 'input' else e.output).size for e in p.examples()}
        parts = []
        for t in _visible(p):
            if t.id == x.id:
                continue
            parts += [(0,) + q for q in _partitions(t, frame)]
            parts += [(1,) + q for q in _box_parts(t, frame, sizes)]
        if not parts:
            return None
        ctx = _by_example(_ctx_rows(x))
        n = 0
        ex = [0, 0]
        cov = [[], []]
        kfr = []
        for e, rows in ctx.items():
            S = {getattr(r[xi], 'cell', None) for r in rows}
            S.discard(None)
            if len(S) < 2:
                continue
            n += 1
            best_cov, best_k, hit = [0.0, 0.0], 1.0, [False, False]
            for tag, _, _, pe in parts:
                cl = pe.get(e)
                if not cl or len(cl) < 2:
                    continue
                if sum(len(c) for c in cl) / len(cl) < 2:
                    continue
                inside = [c for c in cl if c <= S]
                if inside and len(inside) < len(cl):
                    u = set().union(*inside)
                    best_cov[tag] = max(best_cov[tag], len(u) / len(S))
                    if u == S:
                        hit[tag] = True
                        if tag == 0:
                            best_k = min(best_k, len(inside) / len(cl))
            for t in (0, 1):
                ex[t] += hit[t]
                cov[t].append(best_cov[t])
            kfr.append(best_k)
        if not n:
            return None
        return {'exact': ex[0] / n, 'cover': sum(cov[0]) / n, 'kfrac': sum(kfr) / n,
                'box_exact': ex[1] / n, 'box_cover': sum(cov[1]) / n}
    except Exception:
        return None


ENUM = ('Dir', 'Dir8', 'DiagDir', 'D4', 'C4', 'Axis', 'Sense', 'Sym', 'DiagAxis')


def _colvals(table):
    """{column index: {example: frozenset of values}} for a table's non-Example, non-geometric columns."""
    cols = table.columns()
    byex = _by_example(_ctx_rows(table))
    out = {}
    for i, c in enumerate(cols):
        if c.type in ('Example', 'Position', 'Box', 'Offset', 'Ident'):
            continue
        out[i] = (c.type, {e: frozenset(r[i] for r in rows) for e, rows in byex.items()})
    return out


@feature
def a2_value_domain(p):
    """A2 How the values of X's enum, Color and Number columns relate to the values the visible tables hold in columns
    of that type. For each X column (not Example, geometric or Ident), V is its value set over all examples and W the
    union of the value sets of the visible columns of the same type. Per class (`enum` for the orientation types,
    `color`, `num`), the shares of that class's columns with: `none` (no visible column of the type), `outside` (V has a
    value not in W), `proper` (V is a proper subset of W), `same` (V equals W), and `copy` (V equals the value set of a
    single visible column in every example, over the examples). None where X has no column of the class.

    Needs: full X, available tables. Monotone: no.
    """
    try:
        x = p.x
        vis = {}
        for t in _visible(p):
            if t.id == x.id:
                continue
            for i, (ty, per) in _colvals(t).items():
                vis.setdefault(ty, []).append(per)
        xs = _colvals(x)
        acc = {}
        for i, (ty, per) in xs.items():
            cls = 'enum' if ty in ENUM else 'color' if ty == 'Color' else 'num' if ty == 'Number' else None
            if cls is None:
                continue
            a = acc.setdefault(cls, C.Counter())
            a['n'] += 1
            V = set().union(*per.values()) if per else set()
            cols = vis.get(ty, [])
            if not cols:
                a['none'] += 1
                continue
            W = set()
            for q in cols:
                for s in q.values():
                    W |= s
            if V - W:
                a['outside'] += 1
            elif V < W:
                a['proper'] += 1
            else:
                a['same'] += 1
            for q in cols:
                if per and all(q.get(e) == s for e, s in per.items()):
                    a['copy'] += 1
                    break
        out = {}
        for cls, a in acc.items():
            for k in ('none', 'outside', 'proper', 'same', 'copy'):
                out[f'{cls}_{k}'] = a[k] / a['n']
        return out or None
    except Exception:
        return None


def _hashable(v):
    return getattr(v, 'margins', None) and (v.margins, v.frame) or v


@feature
def a3_relation_fill(p):
    """A3 How much of a cross product X fills. Per context (assignment, example) with at least 6 distinct rows, over the
    columns that are not Example: `free_max` is the largest, over columns c with at least 3 values and at least 3
    distinct tuples of the other columns, of (distinct rows) / (values of c x tuples of the others) -- 1 where c
    is free, and near 1 where a few combinations are cut; `free_n` counts the columns whose share is at least 0.9;
    `pair_max` is the largest, over pairs of columns with at least 4 values each, of (distinct pairs) / (values x
    values); the mean over contexts. None where X has no such context.

    Needs: full X. Monotone: no.
    """
    try:
        x = p.x
        cols = x.columns()
        keep = [i for i, c in enumerate(cols) if c.type != 'Example']
        if len(keep) < 2:
            return None
        fm, fn, pm = [], [], []
        for (a, e), models in x.examples().items():
            rows = models[0] if models else []
            if not rows or len(rows) > MAX_ROWS:
                continue
            tup = {tuple(_hashable(r[i]) for i in keep) for r in rows}
            if len(tup) < 6:
                continue
            n = len(tup)
            vals = [{t[j] for t in tup} for j in range(len(keep))]
            fmax, fcount, pmax = 0.0, 0, 0.0
            for j in range(len(keep)):
                rest = {t[:j] + t[j + 1:] for t in tup}
                if len(vals[j]) >= 3 and len(rest) >= 3:
                    f = n / (len(vals[j]) * len(rest))
                    fmax = max(fmax, f)
                    fcount += f >= 0.9
            for j in range(len(keep)):
                if len(vals[j]) < 4:
                    continue
                for k in range(j + 1, len(keep)):
                    if len(vals[k]) < 4:
                        continue
                    pr = {(t[j], t[k]) for t in tup}
                    pmax = max(pmax, len(pr) / (len(vals[j]) * len(vals[k])))
            fm.append(fmax)
            fn.append(fcount)
            pm.append(pmax)
        if not fm:
            return None
        k = len(fm)
        return {'free_max': sum(fm) / k, 'free_n': sum(fn) / k, 'pair_max': sum(pm) / k}
    except Exception:
        return None


def _derived(p, x):
    """Visible tables that earlier clauses define (not the base grids `input`, `ex_input`, `ex_output`)."""
    base = set()
    for t in _visible(p):
        cols = [(c.type, c.frame) for c in t.columns() if c.type != 'Example']
        if cols in ([('Position', 'input'), ('Color', '')], [('Position', 'output'), ('Color', '')]):
            base.add(t.id)
    return [t for t in _visible(p) if t.id not in base and t.id != x.id]


def _geo_sets(table, types=('Position', 'Box')):
    """{column index: (type, frame, {example: frozenset of margin tuples})}."""
    byex = _by_example(_ctx_rows(table))
    out = {}
    for i, c in enumerate(table.columns()):
        if c.type in types:
            out[i] = (c.type, c.frame, {e: frozenset(getattr(r[i], 'margins', None) for r in rows) for e, rows in byex.items()})
    return out


@feature
def a4_derived_geometry(p):
    """A4 Whether X's Position and Box columns stay inside the geometry that a derived visible table holds. For each
    Position or Box column of X, per example, V is its set of values and W the union of the values of the columns of
    the same type and frame in the visible tables that earlier clauses define (not the grid tables). `inside` is the
    share of columns with V inside W in every example that has a value, `equal` the share with V equal to the
    value set of one such column in every example, `tight` the mean of |V| / |W| over the columns that are inside, `tight_min` the mean over the columns of the
    least |V| / |W_q| over the single derived columns q that hold V in every example (1 where none), `strict` the share of
    columns with such a q and a share below 1, and `derived` the number of derived tables that hold such a column. None where X has no such column or no derived table
    holds one of the same type and frame.

    Needs: full X, available tables. Monotone: no.
    """
    try:
        x = p.x
        der = _derived(p, x)
        W = {}
        for t in der:
            for i, (ty, fr, per) in _geo_sets(t).items():
                W.setdefault((ty, fr), []).append(per)
        xs = _geo_sets(x)
        n = ins = eq = strict = 0
        tight, tmin = [], []
        for i, (ty, fr, per) in xs.items():
            cols = W.get((ty, fr))
            if not cols or not per:
                continue
            n += 1
            union = {}
            for q in cols:
                for e, s in q.items():
                    union.setdefault(e, set()).update(s)
            ok = all(s <= union.get(e, set()) for e, s in per.items() if s)
            ins += ok
            if ok:
                r = [len(s) / len(union[e]) for e, s in per.items() if s and union.get(e)]
                if r:
                    tight.append(sum(r) / len(r))
            eq += any(all(q.get(e) == s for e, s in per.items()) for q in cols)
            best = None
            for q in cols:
                r = [len(s) / len(q[e]) for e, s in per.items() if s and e in q and q[e] and s <= q[e]]
                if r and len(r) == sum(1 for s in per.values() if s):
                    m = sum(r) / len(r)
                    best = m if best is None else min(best, m)
            if best is not None:
                tmin.append(best)
                strict += best < 1.0
        if not n:
            return None
        return {'inside': ins / n, 'equal': eq / n, 'tight': sum(tight) / len(tight) if tight else 1.0,
                'tight_min': sum(tmin) / len(tmin) if tmin else 1.0, 'strict': strict / n, 'derived': float(len(W))}
    except Exception:
        return None


@feature
def a5_spatial_coherence(p):
    """A5 Whether the cells of X's first Position column of a grid frame form clumps. Per example with a cell set S of
    m cells (3 <= m <= N - 3 for the frame's N cells), `adj` is the number of 4-adjacent pairs inside S over the
    number that a random set of m cells has on average; `line` is the share of cells of S that share their row or
    their column with at least two other cells of S; `pieces` is the number of 4-connected pieces of S over m;
    `boxfill` is m over the area of S's bounding box. The mean over examples. None where X has no such column.

    Needs: full X. Monotone: no.
    """
    try:
        x = p.x
        xcols = [c for c in x.columns() if c.type == 'Position' and c.frame in ('input', 'output')]
        if not xcols:
            return None
        xc = xcols[0]
        xi = xc.index if xc.index is not None else x.columns().index(xc)
        exs = {e.index: e for e in p.examples()}
        adjs, lines, fr, bf = [], [], [], []
        byex = _by_example(_ctx_rows(x))
        for e, rows in byex.items():
            ex = exs.get(e)
            if ex is None:
                continue
            h, w = (ex.input if xc.frame == 'input' else ex.output).size
            N = h * w
            S = {getattr(r[xi], 'cell', None) for r in rows}
            S = {c for c in S if c is not None and 0 <= c[0] < h and 0 <= c[1] < w}
            m = len(S)
            if m < 3 or m > N - 3:
                continue
            obs = sum(((r + 1, c) in S) + ((r, c + 1) in S) for r, c in S)
            tot = h * (w - 1) + w * (h - 1)
            exp = tot * m * (m - 1) / (N * (N - 1))
            if exp <= 0:
                continue
            adjs.append(obs / exp)
            seen, ncomp = set(), 0
            for cell in S:
                if cell in seen:
                    continue
                ncomp += 1
                stack = [cell]
                seen.add(cell)
                while stack:
                    a, b = stack.pop()
                    for nb in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                        if nb in S and nb not in seen:
                            seen.add(nb)
                            stack.append(nb)
            rr = [c[0] for c in S]
            cc2 = [c[1] for c in S]
            box = (max(rr) - min(rr) + 1) * (max(cc2) - min(cc2) + 1)
            fr.append(ncomp / m)
            bf.append(m / box)
            rc = C.Counter(r for r, _ in S)
            cc = C.Counter(c for _, c in S)
            lines.append(sum(1 for r, c in S if rc[r] >= 3 or cc[c] >= 3) / m)
        if not adjs:
            return None
        return {'adj': sum(adjs) / len(adjs), 'line': sum(lines) / len(lines), 'pieces': sum(fr) / len(fr),
                'boxfill': sum(bf) / len(bf)}
    except Exception:
        return None


@feature
def a6_assignment_dependence(p):
    """A6 Whether X changes with the assignment of the earlier clauses' parameters. The entries of X are grouped by
    assignment; an assignment's content is the sets of rows it holds in each example. With n assignments (n >= 2):
    `n` is that count, `distinct` the share of distinct contents among them, and `same` is 1 when all contents are
    equal. None where X has fewer than two assignments.

    Needs: full X. Monotone: no.
    """
    try:
        x = p.x
        per = {}
        for e in x.entries:
            key = (e['train'], e['model'])
            rows = frozenset(tuple(tuple(c['value']) for c in r) for r in e['rows'])
            per.setdefault(e['assignment'], {})[key] = rows
        if len(per) < 2:
            return None
        contents = [frozenset(d.items()) for d in per.values()]
        k = len(set(contents))
        return {'n': float(len(per)), 'distinct': k / len(per), 'same': float(k == 1)}
    except Exception:
        return None


def _mi(pairs):
    """Miller-Madow corrected mutual information of (a, q) pairs, over the entropy of q, in [0, 1]; 0 where q is constant."""
    n = len(pairs)
    if n < 8:
        return None
    ca, cq, cj = C.Counter(), C.Counter(), C.Counter()
    for a, q in pairs:
        ca[a] += 1
        cq[q] += 1
        cj[a, q] += 1
    if len(cq) < 2:
        return None
    hq = -sum(v / n * math.log2(v / n) for v in cq.values())
    mi = sum(v / n * math.log2(v * n / (ca[a] * cq[q])) for (a, q), v in cj.items())
    mi -= (len(ca) - 1) * (len(cq) - 1) / (2 * n * math.log(2))
    return max(0.0, mi) / hq


def _cell_attrs(grid):
    """{cell: dict of attributes} of an input grid."""
    h, w = grid.size
    cells = grid.cells
    bg = max(grid.colors().items(), key=lambda kv: kv[1])[0]
    seen, comp = {}, {}
    for r in range(h):
        for c in range(w):
            if (r, c) in seen:
                continue
            col, stack, mem = cells[r][c], [(r, c)], []
            seen[r, c] = 1
            while stack:
                a, b = stack.pop()
                mem.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    u, v = a + da, b + db
                    if 0 <= u < h and 0 <= v < w and (u, v) not in seen and cells[u][v] == col:
                        seen[u, v] = 1
                        stack.append((u, v))
            s = len(mem)
            b = 0 if s == 1 else 1 if s <= 3 else 2 if s <= 8 else 3
            for m in mem:
                comp[m] = b
    out = {}
    for r in range(h):
        for c in range(w):
            col = cells[r][c]
            same = sum(1 for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if 0 <= r + da < h and 0 <= c + db < w and cells[r + da][c + db] == col)
            out[r, c] = {'col': col, 'bg': col == bg, 'same': same, 'rowpar': r % 2, 'colpar': c % 2,
                         'border': min(r, c, h - 1 - r, w - 1 - c, 3), 'comp': comp[r, c]}
    return out


@feature
def a7_cell_dependence(p):
    """A7 Whether a non-geometric column of X varies with the grid cell its row is about. For each column Q of X that is
    not Example, Position, Box, Offset or Ident, in a table with a Position column of the input frame, the corrected
    mutual information between Q and an attribute of the input cell, over the rows of all examples, divided by Q's
    entropy. The attributes are the cell's color, background or not, the number of 4-neighbors of its color, the row
    and column parity, the distance to the border (at most 3) and the size class of its 4-connected piece of one color.
    `mi_max` is the mean over the columns Q of the largest value over the attributes; `mi_col` the same for the
    color attribute; `out` the same with the output color at the cell (examples with equal sizes) and whether the
    cell changes. None where X has no such column pair.

    Needs: full X, train grids. Monotone: no.
    """
    try:
        x = p.x
        cols = x.columns()
        pcol = next((c for c in cols if c.type == 'Position' and c.frame == 'input'), None)
        if pcol is None:
            return None
        pi = pcol.index if pcol.index is not None else cols.index(pcol)
        qs = [i for i, c in enumerate(cols) if c.type not in ('Example', 'Position', 'Box', 'Offset', 'Ident') and i != pi]
        if not qs:
            return None
        exs = {e.index: e for e in p.examples()}
        attrs = {}
        pooled = {i: [] for i in qs}
        pooled_out = {i: [] for i in qs}
        names = ('col', 'bg', 'same', 'rowpar', 'colpar', 'border', 'comp')
        data = {i: {n: [] for n in names} for i in qs}
        total = 0
        for e, rows in _by_example(_ctx_rows(x)).items():
            ex = exs.get(e)
            if ex is None:
                continue
            if e not in attrs:
                attrs[e] = _cell_attrs(ex.input)
            ch = ex.changed()
            for r in rows[:MAX_ROWS]:
                cell = getattr(r[pi], 'cell', None)
                at = attrs[e].get(cell)
                if at is None:
                    continue
                total += 1
                for i in qs:
                    q = r[i]
                    for n in names:
                        data[i][n].append((at[n], q))
                    if ch is not None:
                        pooled_out[i].append(((ex.output.cells[cell[0]][cell[1]], cell in ch), q))
        if not total:
            return None
        mx, mc, mo = [], [], []
        for i in qs:
            vals = {n: _mi(data[i][n]) for n in names}
            ok = [v for v in vals.values() if v is not None]
            if not ok:
                continue
            mx.append(max(ok))
            if vals['col'] is not None:
                mc.append(vals['col'])
            o = _mi(pooled_out[i]) if pooled_out[i] else None
            if o is not None:
                mo.append(o)
        if not mx:
            return None
        out = {'mi_max': sum(mx) / len(mx)}
        if mc:
            out['mi_col'] = sum(mc) / len(mc)
        if mo:
            out['out'] = sum(mo) / len(mo)
        return out
    except Exception:
        return None


def _pair_proj(table, cap=8):
    """{(type-frame key of the pair, order): {example: frozenset of value pairs}} for the column pairs of a table that are
    not Example or Ident columns; Position, Box and Offset values keyed by margins and frame."""
    cols = table.columns()
    use = [i for i, c in enumerate(cols) if c.type not in ('Example', 'Ident')][:cap]
    if len(use) < 2:
        return {}
    byex = _by_example(_ctx_rows(table))
    out = {}
    for a in range(len(use)):
        for b in range(len(use)):
            if a == b:
                continue
            i, j = use[a], use[b]
            ki, kj = (cols[i].type, cols[i].frame), (cols[j].type, cols[j].frame)
            if (ki, kj) > (kj, ki) and ki != kj:
                continue
            per = {}
            for e, rows in byex.items():
                if len(rows) > MAX_ROWS:
                    per = None
                    break
                per[e] = frozenset((_hashable(r[i]), _hashable(r[j])) for r in rows)
            if per:
                out.setdefault((ki, kj), []).append(per)
    return out


@feature
def a8_pair_restates(p):
    """A8 How many of X's column pairs repeat a pair of columns that a visible table holds. A pair of X's columns (not
    Example or Ident) with the types and frames (t1, t2) is compared with every pair of a visible table with the same
    types and frames, in both orders where they are equal; the projections are sets of value pairs per example.
    `equal` is the share of X's pairs equal to a visible pair in every example, `inside` the share that lie inside one
    in every example and are not equal, `outside` the rest that have a visible pair of the types, and `novel` the share
    with no visible pair of those types. `pairs` is the number of X's pairs. None where X has fewer than two such
    columns.

    Needs: full X, available tables. Monotone: no.
    """
    try:
        x = p.x
        vis = {}
        for t in _visible(p):
            if t.id == x.id:
                continue
            for k, lst in _pair_proj(t).items():
                vis.setdefault(k, []).extend(lst)
        xp = _pair_proj(x)
        if not xp:
            return None
        n = eq = ins = out = nov = 0
        for k, lst in xp.items():
            for per in lst:
                n += 1
                cands = vis.get(k, [])
                if not cands:
                    nov += 1
                    continue
                if any(per.keys() <= q.keys() and all(per[e] == q[e] for e in per) for q in cands):
                    eq += 1
                elif any(per.keys() <= q.keys() and all(per[e] <= q[e] for e in per) for q in cands):
                    ins += 1
                else:
                    out += 1
        return {'equal': eq / n, 'inside': ins / n, 'outside': out / n, 'novel': nov / n, 'pairs': float(n)}
    except Exception:
        return None
