"""Order-free features of a pool node: its rows against the task's train pairs. No gold, no age, no written order."""
import collections
import itertools
import json

TASKS = '/Users/davidlu/code/arc-workspace/data/tasks'
GRID = ('Position', 'Box')


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


def names():
    """{TableVector name: its place in the vector}."""
    if not NAMES:
        import arclog
        NAMES.update((n, i) for i, n in enumerate(arclog.table_feature_names()))
    return NAMES


NAMES = {}
# The TableVector entries that the model reads, by what a table needs for the entry to exist: the engine gives 0 for an entry that the table cannot give, and the model reads it as missing.
ROW_ENTRIES = ('const_cols', 'live_cols', 'distinct_min', 'distinct_max', 'row_distinct', 'rows_per_area', 'rows_eq_changed', 'rows_eq_ofg')
COLOR_ENTRIES = ('color_in_out', 'color_new', 'color_one')
POSITION_ENTRIES = ('cover', 'fg_share', 'ofg_share', 'is_input_color', 'shape_in', 'shape_out', 'shape_live', 'shape_both_live')
SAME_ENTRIES = ('iou_changed', 'prec_changed', 'rec_changed', 'iou_ofg')
OUT_ENTRIES = ('out_err', 'out_gain', 'out_exact', 'out_rec', 'out_prec', 'out_broke', 'out_oob', 'out_conflict', 'out_pair_best', 'out_pair_worst', 'out_pairs_exact',
               'out_pairs_fixed', 'near_only_missing', 'near_only_extra', 'near_remap')
FILL_ENTRIES = ('fill_gain', 'fill_rec', 'fill_one_color', 'near_fill')
DIRECT = ('rows_mean', 'rows_min', 'rows_max', 'empty_any', 'one_row', 'same_hash', 'test_same', 'test_empty')


def table_values(vector, types, pairs):
    """{name: value} of the TableVector entries that the model reads, from the vector of a table (an array in table_feature_names() order) and its column types. An entry that
    the table has no data for is left out, as the model reads a missing entry: the row-derived entries of a table with no train rows, the Color entries of a table with no Color
    column, the Position entries of a table with no Position column, and the changed-cell entries when no train pair keeps its size."""
    ix = names()
    v = lambda k: float(vector[ix[k]])  # noqa: E731
    d = {'n_train': v('n_train')}
    for t in set(types):
        if 't_' + t in ix and v('t_' + t) > 0:
            d['t_' + t] = v('t_' + t)
    if not d['n_train']:
        return d
    d.update((k, v(k)) for k in DIRECT)
    pos, col = 'Position' in types, 'Color' in types
    d.update((k, v(k)) for k in [*OUT_ENTRIES * (pos and col), *FILL_ENTRIES * pos])  # these have a value for a table with no rows too
    if not v('rows_max'):  # no train entry has a row
        return d
    keep = [*ROW_ENTRIES, *COLOR_ENTRIES * col, *POSITION_ENTRIES * pos, *SAME_ENTRIES * (pos and any(p.same for p in pairs))]
    d.update((k, v(k)) for k in keep)
    return d


def gain_of(d):
    """The node's gain for the link features: out_gain where it has the OUT entries, else fill_gain, else None."""
    return d['out_gain'] if 'out_gain' in d else d.get('fill_gain')


def features(node, pairs):
    """The node's order-free features. node: types, table_types, arity, depth, parents, clause, n_clauses, features (the TableVector) and, where rows are exported, x_rows.
    Every entry of the TableVector comes from it by name; `capped` reads x_rows, which no entry gives."""
    types = node.get('table_types') or node['types']
    d = {'arity': node['arity'], 'depth': node['depth'], 'n_parents': len(node.get('parents') or []),
         'n_clauses': node.get('n_clauses') or 1, 'clause_len': (node.get('clause') or '').count('(:'),
         'clause_atoms': (node.get('clause') or '').count('(&') + (node.get('clause') or '').count('(input')}
    d.update(table_values(node['features'], types, pairs))
    if node.get('x_rows') is not None and d.get('n_train'):
        d['capped'] = float(any(len(ent[1]) < ent[2] for ent in node['x_rows'] if ent[0][0] == 1))
    return d
