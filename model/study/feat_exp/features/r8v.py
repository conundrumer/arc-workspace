"""Round 8, explorer V: features of a partial body and its table.

A body cut after any complete atom is a query with its own table. The export holds the tables of the relations
that are tables (the available tables and the input fact) but no table for a library relation or macro, so the
module evaluates the longest part of the body that it can: the top-level conjuncts that read a table or a fact,
negate such a read, or compare two labels that are already bound, in text order. A library atom or macro is
skipped (read as true, which can only add rows), so the evaluated table T is a superset of the true table of the
body cut at each point, projected on its columns. X is the table of the whole body, so X projected on T's
columns lies inside T. No function reads G, a target table or a clause at or after the point.

An atom's retention is the share of the distinct rows of the table before the atom, on that table's columns,
that survive the atom. Retention depends on the atoms before it only, so it keeps its value when atoms are
appended to the body; a count of atoms with retention 0 or 1 never falls when positive atoms, NOT atoms or
comparisons are appended. Atoms inside an OR, IF or ALL are not evaluated.

`featlib` gives no typed access to a joined table of a partial body; this module reads rows through
`Table.examples(decoded=False)` and the typed atoms, and joins them itself (helper `_prefix`).
"""
import collections as C
from featlib import feature

CAP = 400000
OPS = {'=': lambda a, b: a == b, '!=': lambda a, b: a != b, '<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
       '>': lambda a, b: a > b, '>=': lambda a, b: a >= b}


def _atom_rows(atom):
    """{(assignment, example): [{label: raw value}]} for a top-level read of a table or fact, else None.
    A literal 0 at a Number column is the value 0, and at a Box, Position or Offset column the zero margins."""
    if atom.kind not in ('table', 'fact') or atom.branch or atom.quantifier or atom.conditional:
        return None
    table = atom.table
    if table is None:
        return None
    cols = table.columns()
    names = [c.name for c in cols]
    bound, consts = [], []
    for g in atom.arguments:
        if g.name not in names:
            return None
        i = names.index(g.name)
        if g.is_zero:
            t = cols[i].type
            if t in ('Box', 'Position', 'Offset'):
                consts.append((i, (0, 0, 0, 0)))
            elif t == 'Number':
                consts.append((i, (0,)))
            else:
                return None
        elif g.label is None:
            return None
        else:
            bound.append((i, g.label))
    out = {}
    for key, models in table.examples(decoded=False).items():
        if len(models) != 1:
            return None
        rows = []
        for r in models[0]:
            if any(r[i] != c for i, c in consts):
                continue
            d, ok = {}, True
            for i, label in bound:
                if label in d and d[label] != r[i]:
                    ok = False
                    break
                d[label] = r[i]
            if ok:
                rows.append(d)
        out[key] = rows
    return out


def _compare(atom, cur):
    """The table after a comparison between two bound labels (or a label and 0), or None where it is not evaluable."""
    f, s = atom.first, atom.second
    if f is None or s is None or atom.operator not in OPS:
        return None
    op = OPS[atom.operator]
    new = {}
    for key, rows in cur.items():
        keep = []
        for d in rows:
            vals = []
            for g in (f, s):
                v = (0,) if g.is_zero else d.get(g.label)
                if v is None:
                    return None
                vals.append(v)
            a, b = vals
            if atom.operator not in ('=', '!=') and (len(a) != 1 or len(b) != 1):
                return None
            if op(a, b):
                keep.append(d)
        new[key] = keep
    return new


def _join(cur, ar, negated):
    new = {}
    for key, rows in cur.items():
        other = ar.get(key, [])
        keep = []
        if other and rows:
            shared = [l for l in other[0] if l in rows[0]]
            if negated:
                hit = {tuple(o[l] for l in shared) for o in other}
                keep = [d for d in rows if tuple(d[l] for l in shared) not in hit]
            else:
                idx = C.defaultdict(list)
                for o in other:
                    idx[tuple(o[l] for l in shared)].append(o)
                for d in rows:
                    for o in idx.get(tuple(d[l] for l in shared), ()):
                        nd = dict(d)
                        nd.update(o)
                        keep.append(nd)
                if sum(len(v) for v in new.values()) + len(keep) > CAP:
                    return None
        elif negated:
            keep = list(rows)
        new[key] = keep
    return new


def _prefix(p):
    """The evaluated prefix tables of the candidate's body: a list of (atom, kind, table) in text order, kind
    'pos', 'neg', 'cmp' or 'skip'; table is {(assignment, example): [rows]} after the atom (None before the first
    evaluated atom). Cached on the pair."""
    cached = getattr(p, '_v_prefix_cache', None)
    if cached is not None:
        return cached
    cur, hist = None, []
    for atom in p.clause.body.atoms:
        if atom.operator:
            new = _compare(atom, cur) if cur is not None and not (atom.branch or atom.quantifier or atom.conditional) else None
            kind = 'cmp'
        else:
            ar = _atom_rows(atom)
            if ar is None:
                new, kind = None, 'skip'
            elif atom.negated:
                new, kind = (_join(cur, ar, True) if cur is not None else None), 'neg'
            elif cur is None:
                new, kind = {k: list(v) for k, v in ar.items()}, 'pos'
            else:
                new, kind = _join(cur, ar, False), 'pos'
        if new is None:
            hist.append((atom, 'skip', cur))
        else:
            cur = new
            hist.append((atom, kind, cur))
    p._v_prefix_cache = hist
    return hist


def _distinct(table, cols):
    return sum(len({tuple(d[l] for l in cols) for d in rows}) for rows in table.values())


def _columns(table):
    for rows in table.values():
        if rows:
            return sorted(rows[0])
    return None


def retentions(p):
    """[(atom, kind, kept, before)] for each evaluated atom after the first, over distinct rows of the previous
    table on the previous table's columns."""
    out, prev = [], None
    for atom, kind, cur in _prefix(p):
        if kind == 'skip' or cur is None:
            continue
        if prev is not None:
            cols = _columns(prev)
            if cols is not None:
                out.append((atom, kind, _distinct(cur, cols), _distinct(prev, cols)))
        prev = cur
    return out


@feature
def v1_prefix_cuts(p):
    """V1: per evaluated atom of the table-only prefix, whether it empties the table (void), changes nothing
    (vacuous) or cuts rows, and the smallest and the product of the retentions."""
    r = retentions(p)
    if not r:
        return None
    void = sum(1 for _, _, k, b in r if b and k == 0)
    vac = sum(1 for _, _, k, b in r if b and k == b)
    cut = sum(1 for _, _, k, b in r if b and 0 < k < b)
    keeps = [k / b for _, _, k, b in r if b]
    prod = 1.0
    for x in keeps:
        prod *= x
    return {'void': void, 'vacuous': vac, 'cut': cut, 'min_keep': min(keeps) if keeps else 1.0, 'prod_keep': prod,
            'vacuous_neg': sum(1 for a, kd, k, b in r if kd == 'neg' and b and k == b)}


def _lib_skipped(p):
    return any(kind == 'skip' and not a.operator and a.kind in ('relation', 'macro') for a, kind, _ in _prefix(p))


def _plain(p, label):
    """True where the label is an X column whose values are comparable with the available tables' (not an Ident, whose
    values are local to a table)."""
    v = p.clause.body.variables.get(label)
    return v is not None and v.column is not None and v.column.type != 'Ident'


def _x_projection(p, labels):
    """{(assignment, example): set of X rows projected on labels}, from X's raw values; None if a label is no X column."""
    idx = []
    for l in labels:
        v = p.clause.body.variables.get(l)
        if v is None or v.column is None:
            return None
        idx.append(v.column.index)
    out = {}
    for key, models in p.x.examples(decoded=False).items():
        out[key] = {tuple(r[i] for i in idx) for r in models[0]} if models else set()
    return out


@feature
def v2_suffix_keep(p):
    """V2: the share of the table-only prefix's distinct rows (on its columns) that X keeps, with the number of
    examples where the prefix has rows and X has none; None where no library atom follows the prefix."""
    hist = _prefix(p)
    cur = None
    for _, kind, c in hist:
        if kind != 'skip' and c is not None:
            cur = c
    if cur is None or not _lib_skipped(p):
        return None
    cols = [l for l in (_columns(cur) or []) if _plain(p, l)]
    if not cols:
        return None
    xs = _x_projection(p, cols)
    if xs is None:
        return None
    nt = nx = void_ex = 0
    for key, rows in cur.items():
        t = {tuple(d[l] for l in cols) for d in rows}
        x = xs.get(key, set())
        nt += len(t)
        nx += len(x & t)
        void_ex += 1 if t and not (x & t) else 0
    if not nt:
        return None
    return {'keep': nx / nt, 'void_ex': void_ex}


@feature
def v3_prefix_changed_cover(p):
    """V3: the share of the changed cells (examples whose grids have one size) that the Position columns tagged
    `input` of the table-only prefix hold, and the share of those that X still holds."""
    cur = None
    for _, kind, c in _prefix(p):
        if kind != 'skip' and c is not None:
            cur = c
    if cur is None:
        return None
    pos = {}
    for atom, kind, _ in _prefix(p):
        if kind not in ('pos',) or atom.table is None:
            continue
        cols = {c.name: c for c in atom.table.columns()}
        for g in atom.arguments:
            c = cols.get(g.name)
            if g.label and c is not None and c.type == 'Position' and c.frame == 'input':
                pos[g.label] = True
    labels = [l for l in pos if cur and _columns(cur) and l in _columns(cur)]
    if not labels:
        return None
    xs = {}
    for l in labels:
        v = p.clause.body.variables.get(l)
        if v is None or v.column is None or v.column.type != 'Position' or v.column.frame != 'input':
            continue
        xs[l] = v.column.index
    exs = {e.index: e for e in p.examples()}
    total = in_t = in_x = 0
    xe = p.x.examples(decoded=False)
    for key, rows in cur.items():
        e = exs.get(key[1])
        ch = e.changed() if e is not None else None
        if not ch:
            continue
        t = {(d[l][0], d[l][2]) for d in rows for l in labels if len(d[l]) == 4}
        x = set()
        for m in xe.get(key, [])[:1]:
            for r in m:
                for i in xs.values():
                    if len(r[i]) == 4:
                        x.add((r[i][0], r[i][2]))
        total += len(ch)
        in_t += len(ch & t)
        in_x += len(ch & t & x)
    if not total:
        return None
    return {'prefix': in_t / total, 'lost': (in_t - in_x) / total}
