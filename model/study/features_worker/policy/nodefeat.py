"""Order-free features of a pool node: its rows against the task's train pairs. No gold, no age, no written order."""
import collections
import itertools
import json

TASKS = '/Users/davidlu/code/arc-workspace/data/tasks'
GRID = ('Position', 'Box', 'Offset')


def comps(cells):
    left = set(cells); out = []
    while left:
        s = [left.pop()]; c = {s[0]}
        while s:
            r, q = s.pop()
            for n in ((r + a, q + b) for a in (-1, 0, 1) for b in (-1, 0, 1)):
                if n in left:
                    left.discard(n); c.add(n); s.append(n)
        out.append(frozenset(c))
    return out


def norm(c):
    r0, q0 = min(x[0] for x in c), min(x[1] for x in c)
    return frozenset((a - r0, b - q0) for a, b in c)


class Pair:
    """One train pair's facts, computed once per task."""

    def __init__(self, a, b):
        self.a, self.b = a, b
        self.h, self.w = len(a), len(a[0])
        self.same = self.h == len(b) and self.w == len(b[0])
        self.area = self.h * self.w
        self.bg = collections.Counter(v for r in a for v in r).most_common(1)[0][0]
        self.obg = collections.Counter(v for r in b for v in r).most_common(1)[0][0]
        self.changed = {(i, j) for i in range(self.h) for j in range(self.w) if a[i][j] != b[i][j]} if self.same else set()
        self.fg = {(i, j) for i in range(self.h) for j in range(self.w) if a[i][j] != self.bg}
        self.ofg = {(i, j) for i in range(len(b)) for j in range(len(b[0])) if b[i][j] != self.obg}
        self.ocolors = {v for r in b for v in r}; self.colors = {v for r in a for v in r}
        self.newcolors = self.ocolors - self.colors
        self.byc = collections.defaultdict(set)
        for i in range(self.h):
            for j in range(self.w):
                self.byc[a[i][j]].add((i, j))
        self.incolor = {frozenset(s) for s in self.byc.values()}
        ob = collections.defaultdict(set)
        for i, j in self.ofg:
            ob[b[i][j]].add((i, j))
        self.oobj = {c for s in ob.values() for c in comps(s) if len(c) >= 3}
        ib = collections.defaultdict(set)
        for i, j in self.fg:
            ib[a[i][j]].add((i, j))
        self.iobj = {c for s in ib.values() for c in comps(s) if len(c) >= 3}
        self.nout = {norm(c) for c in self.oobj}; self.nin = {norm(c) for c in self.iobj}
        self.live = {norm(c) for c in self.oobj if not (self.same and c in self.iobj and all(a[i][j] == b[i][j] for i, j in c))}


def load_pairs(task):
    t = json.load(open(f'{TASKS}/{task}.json'))
    return [Pair(p['input'], p['output']) for p in t['train']]


def widths(types):
    return [4 if t in GRID else 1 for t in types]


def columns(rows, types):
    """Rows as tuples of cells, or None when the flat row doesn't fit the types."""
    w = widths(types); out = []
    for r in rows:
        if len(r) != sum(w):
            return None
        i = 0; c = []
        for n in w:
            c.append(tuple(r[i:i + n])); i += n
        out.append(tuple(c))
    return out


def features(node, pairs):
    types = node.get('table_types') or node['types']
    d = {'arity': node['arity'], 'depth': node['depth'], 'n_parents': len(node.get('parents') or []),
         'n_clauses': node.get('n_clauses') or 1, 'clause_len': (node.get('clause') or '').count('(:'),
         'clause_atoms': (node.get('clause') or '').count('(&') + (node.get('clause') or '').count('(input')}
    for t, n in collections.Counter(types).items():
        d['t_' + t] = n
    tr = {}; te = {}
    for ent in node.get('x_rows') or []:
        (a, e), rows = ent[0], ent[1]
        (tr if a == 1 else te).setdefault(e, []).extend(rows)  # one entry per DET assignment
    hashes = {}
    for a, e, n, h in node.get('examples') or []:
        hashes[(a, e)] = (n, h)
    nt = [v for k, v in hashes.items() if k[0] == 1]
    d['n_train'] = len(nt)
    if not nt:
        return d
    counts = [n for n, _ in nt]
    d['rows_mean'] = sum(counts) / len(counts); d['rows_min'] = min(counts); d['rows_max'] = max(counts)
    d['empty_any'] = float(min(counts) == 0)
    d['one_row'] = float(max(counts) == 1)
    d['same_hash'] = float(len({h for _, h in nt}) == 1)
    d['test_same'] = float(any(v[1] == nt[0][1] for k, v in hashes.items() if k[0] != 1))
    d['test_empty'] = float(any(v[0] == 0 for k, v in hashes.items() if k[0] != 1))
    capped = sum(len(v) for v in tr.values()) < sum(counts)
    d['capped'] = float(capped)
    allrows = [c for e in tr for c in (columns(tr[e], types) or [])]
    nc = len(types)
    if allrows and nc:
        cols = [[r[i] for r in allrows] for i in range(nc)]
        distinct = [len(set(c)) for c in cols]
        const = sum(n <= 1 for n in distinct)
        d['const_cols'] = const; d['live_cols'] = nc - const
        d['distinct_min'] = min(distinct); d['distinct_max'] = max(distinct)
        d['row_distinct'] = len(set(allrows)) / len(allrows)
    # Against the train pairs: the first Position column, and any Color column.
    pos = [i for i, t in enumerate(types) if t == 'Position']
    col = [i for i, t in enumerate(types) if t == 'Color']
    agg = collections.defaultdict(list)
    for e, rows in tr.items():
        if e >= len(pairs):
            continue
        p = pairs[e]; c = columns(rows, types)
        if not c:
            continue
        agg['rows_per_area'].append(len(rows) / p.area)
        agg['rows_eq_changed'].append(float(p.same and len(set(c)) == len(p.changed)))
        agg['rows_eq_ofg'].append(float(len(set(c)) == len(p.ofg)))
        for i in col:
            cs = {r[i][0] for r in c}
            agg['color_in_out'].append(len(cs & p.ocolors) / max(len(cs), 1))
            agg['color_new'].append(float(bool(cs & p.newcolors)))
            agg['color_one'].append(float(len(cs) == 1))
        for i in pos:
            S = {(r[i][0], r[i][2]) for r in c}
            if not S:
                continue
            agg['cover'].append(len(S) / p.area)
            agg['fg_share'].append(len(S & p.fg) / len(S))
            agg['ofg_share'].append(len(S & p.ofg) / len(S))
            if p.same:
                u = S | p.changed
                agg['iou_changed'].append(len(S & p.changed) / len(u) if u else 0.0)
                agg['prec_changed'].append(len(S & p.changed) / len(S))
                agg['rec_changed'].append(len(S & p.changed) / max(len(p.changed), 1))
                u = S | p.ofg
                agg['iou_ofg'].append(len(S & p.ofg) / len(u) if u else 0.0)
            agg['is_input_color'].append(float(frozenset(S) in p.incolor))
            ns = {norm(c2) for c2 in comps(S) if len(c2) >= 3 and len(c2) <= .6 * p.area}
            agg['shape_in'].append(float(bool(ns & p.nin)))
            agg['shape_out'].append(float(bool(ns & p.nout)))
            agg['shape_live'].append(float(bool(ns & p.live)))
            agg['shape_both_live'].append(float(bool(ns & p.live & p.nin)))
    for k, v in agg.items():
        d[k] = sum(v) / len(v)
    return d
