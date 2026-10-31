"""Round 5, explorer N: what the search can see of a table with extra rows, in X against the earlier tables and the train grids.

N1: how each column of X relates, as a set of values per context, to the columns of the same type in the earlier tables
    (equal, inside, containing, disjoint, overlapping).
N2: how the values of a Color column of X relate to the colors of the train output.
N3: what the train output holds at the cells of an input-frame Position column.
N4: how many rows each key of an Ident-keyed X holds.
"""
import collections as C
import functools
import math

import featlib
from featlib import feature

MAX_TABLE_ROWS = 20000
# Number is left out: small integer sets lie inside each other by chance. Ident values are local to their table.
SKIP_TYPES = ('Ident', 'Example', 'Number')
BIG = 0.3  # an earlier column that makes up at least this share of the X column it lies in is not a chance subset


def _train_list(p):
    tr = p.train
    return tr['train'] if isinstance(tr, dict) and 'train' in tr else tr


def _index(p):
    """Table id -> its index entry (roles, row_count), from the pair file and the shared point file."""
    out = {}
    shared = featlib._point_cache.get(getattr(p, 'point_dir', None))
    if isinstance(shared, dict):
        for t in shared.get('tables', []):
            out[t['id']] = t
    for t in p._meta.get('tables', []):
        out[t['id']] = t
    return out


def _first(table):
    """(assignment, train) -> rows of the first model."""
    out = {}
    for e in table.entries:
        out.setdefault((e['assignment'], e['train']), e['rows'])
    return out


def _col_sets(table):
    """Column index -> {(assignment, train): frozenset of the column's values in the first model}."""
    first = _first(table)
    return {j: {k: frozenset(tuple(r[j]['value']) for r in rows) for k, rows in first.items()}
            for j in range(len(table.fields))}


@functools.lru_cache(maxsize=64)
def _loaded(path):
    t = featlib.Table(featlib.load(path))
    return t.name, t.types(), t.frames(), _col_sets(t)


def _before(p):
    """(name, types, frames, column sets) of each table built before the point, except the grid tables and tables of
    more than MAX_TABLE_ROWS rows."""
    index = _index(p)
    for tid, path in p._available.items():
        meta = index.get(tid, {})
        if 'target' in meta.get('roles', []) or (meta.get('row_count') or 0) > MAX_TABLE_ROWS:
            continue
        got = _loaded(str(path))
        if got[0] in ('ex_input', 'ex_output'):
            continue
        yield got


def _relation(v, w, keys):
    """How X's value sets v relate to the earlier column's sets w over the contexts where both are non-empty:
    (relation in every context: eq, sub, sup, disj or ovl; mean of |w| / |v|; the relation of each context)."""
    ks = [k for k in keys if v.get(k) and w.get(k)]
    if not ks:
        return None, 0.0, C.Counter()
    ratio = sum(len(w[k]) / len(v[k]) for k in ks) / len(ks)
    per = C.Counter('eq' if v[k] == w[k] else 'sub' if v[k] <= w[k] else 'sup' if v[k] >= w[k]
                    else 'disj' if not (v[k] & w[k]) else 'ovl' for k in ks)
    if per['eq'] == len(ks):
        return 'eq', ratio, per
    if per['eq'] + per['sub'] == len(ks):
        return 'sub', ratio, per
    if per['eq'] + per['sup'] == len(ks):
        return 'sup', ratio, per
    if per['disj'] == len(ks):
        return 'disj', ratio, per
    return 'ovl', ratio, per


# Not a feature: it reads private attributes; G13 (g_vs_earlier) replaces it.
def n1_col_relations(p):
    """N1: for each column of X (not Ident, Example or Number), against each distinct value-set column of the same type and a compatible frame in the earlier tables, over the contexts where both are non-empty: eq (equal in every context), sub (inside), sup (strictly containing it in every context), disj (disjoint), ovl (otherwise); sums over X's columns of the distinct earlier columns in each relation (a column with the same sets in several tables counts once); sup_cell and sup_label split sup by Position or Box columns against other types; sup_big counts the sup relations whose earlier column makes up at least 0.3 of X's column (mean over contexts of the ratio of their sizes); sup_cols (X columns that contain some earlier column), share (sup over all relations), absorb (the largest mean share of an X column that an earlier column it contains makes up), ctx_sup, ctx_ovl and ctx_disj (the share of the (X column, earlier column, context) triples in which X's column contains it, overlaps it without containing it, or is disjoint from it). None without a column or a related earlier column. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so its rows would be compared with one example's rows of an earlier table."""
    if p.kind == 'Det':
        return None
    x = p.x
    xsets = _col_sets(x)
    keys = [k for k in xsets[next(iter(xsets))]] if xsets else []
    if not keys:
        return None
    cols = [j for j, t in enumerate(x.types()) if t not in SKIP_TYPES]
    if not cols:
        return None
    tables = list(_before(p))
    acc = C.Counter()
    absorb = 0.0
    sup_cols = 0
    total = 0
    used_cols = 0
    ctxs = 0
    for j in cols:
        xt, xf = x.types()[j], x.frames()[j]
        v = xsets[j]
        seen = set()
        had_sup = False
        for _, types, frames, sets in tables:
            for tj, (tt, tf) in enumerate(zip(types, frames)):
                if tt != xt or not (xf == tf or not xf or not tf):
                    continue
                w = sets[tj]
                rel, ratio, per = _relation(v, w, keys)
                if rel is None:
                    continue
                sig = (rel, tuple(sorted((k, tuple(sorted(w[k]))) for k in keys if w.get(k) and v.get(k))))
                if sig in seen:
                    continue
                seen.add(sig)
                acc[rel] += 1
                total += 1
                for name, n in per.items():
                    acc['ctx_' + name] += n
                    ctxs += n
                if rel == 'sup':
                    had_sup = True
                    if ratio >= BIG:
                        acc['sup_big'] += 1
                    acc['sup_cell' if xt in ('Position', 'Box') else 'sup_label'] += 1
                    absorb = max(absorb, ratio)
        used_cols += bool(seen)
        sup_cols += had_sup
    if not total:
        return None
    return {'eq': acc['eq'], 'sub': acc['sub'], 'sup': acc['sup'], 'disj': acc['disj'], 'ovl': acc['ovl'],
            'sup_cell': acc['sup_cell'], 'sup_label': acc['sup_label'], 'sup_big': acc['sup_big'], 'sup_cols': sup_cols,
            'share': acc['sup'] / total, 'absorb': absorb, 'ctx_sup': acc['ctx_sup'] / ctxs,
            'ctx_ovl': acc['ctx_ovl'] / ctxs, 'ctx_disj': acc['ctx_disj'] / ctxs}


@feature
def n2_color_vs_output(p):
    """N2: for each Color column of X, per context, the colors X holds against the colors of that example's train output (O) and input (I): prec (the share of X's colors that occur in O, mean over contexts, the lowest over columns), cov (the share of O that X holds, the highest over columns), vanish (mean number of X colors absent from O), exact (columns whose colors equal O in every non-empty context) and same_input (columns whose colors equal I in every non-empty context), pure_same_input (the same, for an X with no Position or Box column). None without a Color column or a non-empty context. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    cols = [j for j, t in enumerate(x.types()) if t == 'Color']
    if not cols:
        return None
    train = _train_list(p)
    first = _first(x)
    precs, covs, vanish = [], [], []
    exact = same = 0
    for j in cols:
        pr, cv, va = [], [], []
        ex_all = si_all = True
        for (a, t), rows in first.items():
            if not rows or t >= len(train):
                continue
            v = {r[j]['value'][0] for r in rows if len(r[j]['value']) == 1}
            if not v:
                continue
            out = {c for row in train[t]['output'] for c in row}
            inp = {c for row in train[t]['input'] for c in row}
            pr.append(len(v & out) / len(v))
            cv.append(len(v & out) / len(out))
            va.append(len(v - out))
            ex_all &= v == out
            si_all &= v == inp
        if not pr:
            continue
        precs.append(sum(pr) / len(pr))
        covs.append(sum(cv) / len(cv))
        vanish.append(sum(va) / len(va))
        exact += ex_all
        same += si_all
    if not precs:
        return None
    pure = not any(t in ('Position', 'Box') for t in x.types())
    return {'prec': min(precs), 'cov': max(covs), 'vanish': sum(vanish) / len(vanish), 'exact': exact,
            'same_input': same, 'pure_same_input': same if pure else 0}


@feature
def n3_output_uniform(p):
    """N3: for each Position column with frame tag `input` whose extent equals the example's grid size, in examples whose input and output have one size, the output grid's colors at the column's distinct cells, pooled over examples: modal (the share of cells with the most common output color), novel (the share of cells whose output color does not occur in that example's input), ncolors (distinct output colors over the cells) and cells (the number of distinct cells); the best column by modal. None without such a column or a cell. None at a Det point: X there is the task-level body table without its Example column, and every train example's entry holds the rows of all examples, so a row would be compared with another example's grids."""
    if p.kind == 'Det':
        return None
    x = p.x
    cols = [j for j, f in enumerate(x.fields) if f['type'] == 'Position' and f.get('frame', '') == 'input']
    if not cols:
        return None
    train = _train_list(p)
    first = _first(x)
    best = None
    for j in cols:
        outs = C.Counter()
        novel = cells = 0
        for (a, t), rows in first.items():
            if t >= len(train):
                continue
            gi, go = train[t]['input'], train[t]['output']
            h, w = len(gi), len(gi[0])
            if (len(go), len(go[0])) != (h, w):
                continue
            inp = {c for row in gi for c in row}
            seen = set()
            for r in rows:
                cell = r[j]
                v = cell['value']
                if len(v) != 4 or cell.get('extent_status') != 'resolved' or list(cell.get('extent') or []) != [h, w]:
                    continue
                rc = (v[0], v[2])
                if rc in seen or not (0 <= rc[0] < h and 0 <= rc[1] < w):
                    continue
                seen.add(rc)
                o = go[rc[0]][rc[1]]
                outs[o] += 1
                novel += o not in inp
                cells += 1
        if not cells:
            continue
        got = {'modal': max(outs.values()) / cells, 'novel': novel / cells, 'ncolors': len(outs), 'cells': cells}
        if best is None or got['modal'] > best['modal']:
            best = got
    return best


@feature
def n4_key_counts(p):
    """N4: for an X whose first column is an Ident key, the rows per key in each context with at least 2 keys: uniform (the share of those contexts where every key holds the same number of rows), spread (mean of distinct counts over keys) and cv (mean coefficient of variation of the counts). None without an Ident first column or such a context."""
    x = p.x
    if not x.fields or x.fields[0]['type'] != 'Ident':
        return None
    uni, spr, cvs = [], [], []
    for (a, t), rows in _first(x).items():
        counts = C.Counter(tuple(r[0]['value']) for r in rows)
        if len(counts) < 2:
            continue
        vals = list(counts.values())
        mean = sum(vals) / len(vals)
        sd = math.sqrt(sum((c - mean) ** 2 for c in vals) / len(vals))
        uni.append(len(set(vals)) == 1)
        spr.append(len(set(vals)) / len(vals))
        cvs.append(sd / mean)
    if not uni:
        return None
    n = len(uni)
    return {'uniform': sum(uni) / n, 'spread': sum(spr) / n, 'cv': sum(cvs) / n}
