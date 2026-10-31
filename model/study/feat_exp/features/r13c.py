"""Round 13, explorer c: what X's rows share across the train examples, how its columns depend on each other, and which
kinds of column it holds.

A feature reads only the train inputs and outputs, X and its types and frames. The rows of a context are the rows of
the first model of one (assignment, example); a table without an Example column is read per train input, as
`Table.examples` gives it. Cells are compared by value, with a Position, Box or Offset keyed by its frame tag and
margins; an Ident column is local to its table, so the overlap functions leave it out. At a Det point the evaluation
keeps every non-Example column of X, so every example has the same rows there and C1 gives None.
"""
import collections as C
import math

from featlib import feature

DIR_TYPES = ('Dir', 'Dir8', 'DiagDir', 'D4', 'C4')
ENUM_TYPES = DIR_TYPES + ('Axis', 'Sense', 'Sym')
MAX_ROWS = 30000


def _key(v):
    """A hashable value of a decoded cell, equal across tables for equal cells."""
    m = getattr(v, 'margins', None)
    if m is not None:
        return tuple(m) + (getattr(v, 'frame', None),)
    return v


def _entropy(counter):
    n = sum(counter.values())
    return -sum(v / n * math.log2(v / n) for v in counter.values()) if n else 0.0


def _contexts(x):
    """{assignment: {example: rows of the first model}} for the contexts that have at least one row."""
    out = {}
    for (a, e), models in x.examples().items():
        if models and models[0]:
            out.setdefault(a, {})[e] = models[0]
    return out


@feature
def c1_example_overlap(p):
    """C1 What X's rows share across the train examples. Over the columns of X that are neither Example nor Ident, per
    assignment with at least two examples that hold a row: `shared` (distinct rows that every such example holds, over
    the distinct rows of their union), `unique` (distinct rows that exactly one example holds, over that union),
    `equal` (1 where every example holds the same rows), `jacc_mean`, `jacc_min`, `jacc_max` (over the columns, the
    share of a column's values, over the union, that every example holds); the mean over assignments. `cover` is the
    share of train examples that hold a row, the mean over assignments. None at a Det point, whose examples all hold
    the same rows, and where X has no such column or no row.

    Needs: full X. Monotone: no.
    """
    try:
        if getattr(p, 'kind', None) == 'Det':
            return None
        x = p.x
        cols = x.columns()
        real = [c.index for c in cols if c.type not in ('Example', 'Ident')]
        ctxs = _contexts(x)
        if not ctxs or not real:
            return None
        n_ex = len(p.examples())
        acc = C.defaultdict(list)
        for a, by_ex in ctxs.items():
            if n_ex:
                acc['cover'].append(min(1.0, len(by_ex) / n_ex))
            if len(by_ex) < 2:
                continue
            sets = [set(tuple(_key(r[i]) for i in real) for r in rows) for rows in by_ex.values()]
            union = set.union(*sets)
            inter = set.intersection(*sets)
            if not union:
                continue
            acc['shared'].append(len(inter) / len(union))
            counts = C.Counter(t for s in sets for t in s)
            acc['unique'].append(sum(1 for v in counts.values() if v == 1) / len(counts))
            acc['equal'].append(float(all(s == sets[0] for s in sets)))
            jac = []
            for i in real:
                vs = [set(_key(r[i]) for r in rows) for rows in by_ex.values()]
                u = set.union(*vs)
                jac.append(len(set.intersection(*vs)) / len(u) if u else 1.0)
            acc['jacc_mean'].append(sum(jac) / len(jac))
            acc['jacc_min'].append(min(jac))
            acc['jacc_max'].append(max(jac))
        out = {k: sum(v) / len(v) for k, v in acc.items() if v}
        return out or None
    except Exception:
        return None


@feature
def c2_dependence(p):
    """C2 How far X's rows are from a product of its columns. Per context (the first model of one assignment and
    example) with at least 4 distinct rows and at least 2 columns that are not Example, with n distinct rows and column
    entropies h_i (bits): tc = 1 - log2(n) / sum(h_i) (0 where every column is constant, or the rows are the full
    product of the columns with uniform counts; it grows with the dependence among the columns). `tc` is the mean over
    contexts weighted by rows, `tc_min` the smallest, `key` the share of contexts where some column alone takes a
    different value in every row. None without such a context.

    Needs: full X. Monotone: no.
    """
    try:
        x = p.x
        plain = [c.index for c in x.columns() if c.type != 'Example']
        if len(plain) < 2:
            return None
        tcs, ws, keys = [], [], []
        for a, by_ex in _contexts(x).items():
            for rows in by_ex.values():
                rs = list(set(tuple(_key(r[i]) for i in plain) for r in rows))
                n = len(rs)
                if n < 4 or n > MAX_ROWS:
                    continue
                hs = [_entropy(C.Counter(r[k] for r in rs)) for k in range(len(plain))]
                total = sum(hs)
                if total <= 1e-9:
                    continue
                tcs.append(max(0.0, 1.0 - math.log2(n) / total))
                ws.append(n)
                keys.append(float(any(len({r[k] for r in rs}) == n for k in range(len(plain)))))
        if not tcs:
            return None
        return {'tc': sum(t * w for t, w in zip(tcs, ws)) / sum(ws), 'tc_min': min(tcs), 'key': sum(keys) / len(keys)}
    except Exception:
        return None


@feature
def c3_column_kinds(p):
    """C3 The kinds of column that X holds, from the column types and frames of X's fields (Example columns are not
    counted): `cols`, `color`, `ident`, `offset`, `box`, `position`, `pos_in` (Position or Box with frame tag `input`),
    `dir` (Dir, Dir8, DiagDir, D4, C4), `axis`, `number`; `box_site`, `box_empty`, `pos_site`, `pos_empty` (Box and
    Position columns whose frame tag names a relation site, and with no frame tag); `grounded` (1 where X has a
    Position, Box or Color column); `univ_only` (1 where every column that is not Ident is of an enumerated type,
    such as Dir or Axis, or a Number: X then holds no cell, box, offset or color of the grids); `counter` (Number
    columns that, in some context, take every integer from 0 or 1 up to a maximum, at least 3 values).

    Needs: full X. Monotone: no.
    """
    try:
        x = p.x
        cols = [c for c in x.columns() if c.type != 'Example']
        if not cols:
            return None
        types = [c.type for c in cols]
        out = {'cols': len(cols)}
        for name, t in (('color', 'Color'), ('ident', 'Ident'), ('offset', 'Offset'), ('box', 'Box'),
                        ('position', 'Position'), ('axis', 'Axis'), ('number', 'Number')):
            out[name] = sum(1 for u in types if u == t)
        out['dir'] = sum(1 for u in types if u in DIR_TYPES)
        out['pos_in'] = sum(1 for c in cols if c.type in ('Position', 'Box') and c.frame_kind == 'input')
        out['box_site'] = sum(1 for c in cols if c.type == 'Box' and c.frame_kind == 'site')
        out['box_empty'] = sum(1 for c in cols if c.type == 'Box' and c.frame_kind == '')
        out['pos_site'] = sum(1 for c in cols if c.type == 'Position' and c.frame_kind == 'site')
        out['pos_empty'] = sum(1 for c in cols if c.type == 'Position' and c.frame_kind == '')
        out['grounded'] = float(any(u in ('Position', 'Box', 'Color') for u in types))
        real = [u for u in types if u != 'Ident']
        out['univ_only'] = float(bool(real) and all(u in ENUM_TYPES or u == 'Number' for u in real))
        ctxs = [rows for by_ex in _contexts(x).values() for rows in by_ex.values()]
        counters = 0
        for c in cols:
            if c.type != 'Number':
                continue
            for rows in ctxs:
                vs = sorted({r[c.index] for r in rows if isinstance(r[c.index], int)})
                if len(vs) >= 3 and vs[0] in (0, 1) and vs == list(range(vs[0], vs[0] + len(vs))):
                    counters += 1
                    break
        out['counter'] = counters
        return out
    except Exception:
        return None
