"""Content features of a relation pick: what an option's table holds, against the table of the clause so far, the tables of the derived relations in scope, and the train pairs.

A table here is an option's table with every column named, read at the clause's start, or the table of the clause's prefix. Nothing here reads gold, a test output, or a name.

  Table(parsed)                 the rows of S.full(tb) by train example and column
  table_row(t, grids)           features of the option alone
  scope_row(t, others)          features of the option against the derived tables in scope
  join_row(t, pre)              features of the option against the prefix table
  prefix_row(pre, grids)        features of the prefix alone, one set per pick
"""
import collections
import math

CAP = 600  # rows kept per example
RELATED = {'Position': 'Box', 'Offset': 'Box', 'Dir': 'Dir8', 'DiagDir': 'Dir8', 'Axis': 'Axis4', 'DiagAxis': 'Axis4', 'Nat': 'Number', 'Int': 'Number'}
OPTION = ('t_read', 't_empty', 't_rows_log', 't_rows_min_log', 't_rows_spread', 't_same_rows', 't_cols', 't_const', 't_distinct', 't_big',
          'y_prec', 'y_rec', 'y_fg_rec', 'y_color_new', 'y_color_out',
          's_dup', 's_cont', 's_jacc', 's_rows_ratio')
JOIN = ('j_read', 'j_pairs', 'j_cont_p', 'j_cont_o', 'j_zero', 'j_full', 'j_match', 'j_fan', 'j_new', 'j_rows_ratio')
PREFIX = ('p_read', 'p_rows_log', 'p_cols', 'p_empty', 'p_prec', 'p_rec')


def norm(t):
    return str(t).split('(')[0]


def top(t):
    while t in RELATED:
        t = RELATED[t]
    return t


def comparable(a, b):
    return a != 'Ident' and b != 'Ident' and top(a) == top(b)


class Table:
    def __init__(self, tb):
        self.types = [norm(t) for t in tb['types']]
        widths = tb['widths']
        got = {}
        for ex, _asg, rows, *_ in tb['entries']:
            if ex[0] != 1:
                continue
            s = got.setdefault(ex[1], set())
            for r in rows[:CAP]:
                i, row = 0, []
                for w in widths:
                    row.append(tuple(r[i:i + w]))
                    i += w
                s.add(tuple(row))
        self.rows = {e: sorted(v) for e, v in got.items()}
        self.vals = [{e: {r[c] for r in v} for e, v in self.rows.items()} for c in range(len(self.types))]
        self.key = frozenset((e, r) for e, v in self.rows.items() for r in v)


class Sized:
    """A table too large to read: its row counts alone."""

    def __init__(self, tb):
        self.counts = {}
        for ex, _asg, rows, *_ in tb['entries']:
            if ex[0] == 1:
                self.counts[ex[1]] = self.counts.get(ex[1], 0) + len(rows)
        self.types = [norm(t) for t in tb['types']]


def grids_of(task_json):
    """{example: (changed cells, output foreground cells, input colors, output colors)} for the train pairs."""
    out = {}
    for e, p in enumerate(task_json['train']):
        a, b = p['input'], p['output']
        ic = {x for r in a for x in r}
        oc = {x for r in b for x in r}
        same = len(a) == len(b) and len(a[0]) == len(b[0])
        ch = {(i, j) for i, r in enumerate(a) for j, x in enumerate(r) if same and x != b[i][j]}
        c = collections.Counter(x for r in b for x in r)
        bg = c.most_common(1)[0][0]
        fg = {(i, j) for i, r in enumerate(b) for j, x in enumerate(r) if x != bg}
        out[e] = (ch, fg, ic, oc)
    return out


def cells(v):
    return {(c[0], c[2]) for c in v if len(c) == 4}


def mean(v):
    return sum(v) / len(v) if v else 0.0


def table_row(t, grids):
    f = dict.fromkeys(OPTION, 0.0)
    if t is None:
        return f
    f['t_read'] = 1.0
    if isinstance(t, Sized):
        n = list(t.counts.values()) or [0]
        f.update(t_big=1.0, t_empty=float(max(n) == 0), t_rows_log=mean([math.log1p(x) for x in n]), t_rows_min_log=math.log1p(min(n)), t_cols=float(len(t.types)))
        return f
    n = [len(v) for v in t.rows.values()] or [0]
    f.update(t_empty=float(max(n) == 0), t_rows_log=mean([math.log1p(x) for x in n]), t_rows_min_log=math.log1p(min(n)), t_rows_spread=math.log1p(max(n)) - math.log1p(min(n)),
             t_same_rows=float(len(set(n)) == 1), t_cols=float(len(t.types)))
    if max(n) == 0:
        return f
    const = dist = 0.0
    for c in range(len(t.types)):
        s = [len(x) for e, x in t.vals[c].items() if t.rows[e]]
        const += all(x == 1 for x in s)
        dist = max(dist, mean([len(x) / len(t.rows[e]) for e, x in t.vals[c].items() if t.rows[e]]))
    f.update(t_const=const, t_distinct=dist)
    prec = rec = fg = 0.0
    for c, ty in enumerate(t.types):
        if ty == 'Position':
            pa, ra, fa = [], [], []
            for e, v in t.vals[c].items():
                g = grids.get(e)
                if g is None or not v:
                    continue
                a = cells(v)
                if g[0]:
                    pa.append(len(a & g[0]) / max(len(a), 1))
                    ra.append(len(a & g[0]) / len(g[0]))
                if g[1]:
                    fa.append(len(a & g[1]) / len(g[1]))
            prec, rec, fg = max(prec, mean(pa)), max(rec, mean(ra)), max(fg, mean(fa))
        elif ty == 'Color':
            new, out = [], []
            for e, v in t.vals[c].items():
                g = grids.get(e)
                if g is None or not v:
                    continue
                vs = {x[0] for x in v}
                fresh = g[3] - g[2]
                if fresh:
                    new.append(len(vs & fresh) / len(fresh))
                out.append(len(vs & g[3]) / len(vs))
            f['y_color_new'], f['y_color_out'] = max(f['y_color_new'], mean(new)), max(f['y_color_out'], mean(out))
    f.update(y_prec=prec, y_rec=rec, y_fg_rec=fg)
    return f


def scope_row(t, others, me=None):
    """others: {name: the Table of each derived relation in scope}; me: the option's own name there."""
    f = dict(s_dup=0.0, s_cont=0.0, s_jacc=0.0, s_rows_ratio=0.0)
    if not isinstance(t, Table) or not t.key:
        return f
    rat = []
    for name, s in others.items():
        if name == me or not isinstance(s, Table) or not s.key:
            continue
        if s.key == t.key:
            f['s_dup'] = 1.0
        rat.append(math.log1p(len(t.key)) - math.log1p(len(s.key)))
        for a, ta in enumerate(t.types):
            for b, tb in enumerate(s.types):
                if comparable(ta, tb):
                    c, j = [], []
                    for e, v in t.vals[a].items():
                        w = s.vals[b].get(e)
                        if w and v:
                            i = len(v & w)
                            c.append(i / len(v))
                            j.append(i / len(v | w))
                    f['s_cont'] = max(f['s_cont'], mean(c))
                    f['s_jacc'] = max(f['s_jacc'], mean(j))
    if rat:
        f['s_rows_ratio'] = mean(rat)
    return f


def join_row(t, pre):
    f = dict.fromkeys(JOIN, 0.0)
    if not isinstance(t, Table) or not isinstance(pre, Table) or not pre.key:
        return f
    f['j_read'] = 1.0
    f['j_rows_ratio'] = math.log1p(len(t.key)) - math.log1p(len(pre.key))
    best = None
    for a, ta in enumerate(t.types):
        for b, tb in enumerate(pre.types):
            if comparable(ta, tb):
                f['j_pairs'] += 1
                cp, co = [], []
                for e, w in pre.vals[b].items():
                    v = t.vals[a].get(e) or set()
                    if w:
                        i = len(v & w)
                        cp.append(i / len(w))
                        co.append(i / len(v) if v else 0.0)
                p, o = mean(cp), mean(co)
                if best is None or p > best[0]:
                    best = p, o, a, b
    if best is None:
        return f
    p, o, a, b = best
    f.update(j_cont_p=p, j_cont_o=o, j_zero=float(p == 0), j_full=float(p == 1))
    match, fan = [], []
    for e, rows in pre.rows.items():
        c = collections.Counter(r[a] for r in t.rows.get(e, ()))
        if rows:
            hit = [c[r[b]] for r in rows if r[b] in c]
            match.append(len(hit) / len(rows))
            fan.append(mean(hit))
    f['j_match'], f['j_fan'] = mean(match), math.log1p(mean(fan))
    new, seen = [], {}
    for b2, tb in enumerate(pre.types):
        for e, w in pre.vals[b2].items():
            seen.setdefault((top(tb), e), set()).update(w)
    for a2, ta in enumerate(t.types):
        for e, v in t.vals[a2].items():
            if a2 != a and v:
                new.append(len(v - seen.get((top(ta), e), set())) / len(v))
    f['j_new'] = mean(new)
    return f


def prefix_row(pre, grids):
    f = dict.fromkeys(PREFIX, 0.0)
    if not isinstance(pre, Table):
        return f
    n = [len(v) for v in pre.rows.values()] or [0]
    f.update(p_read=1.0, p_rows_log=mean([math.log1p(x) for x in n]), p_cols=float(len(pre.types)), p_empty=float(max(n) == 0))
    for c, ty in enumerate(pre.types):
        if ty == 'Position':
            pa, ra = [], []
            for e, v in pre.vals[c].items():
                g = grids.get(e)
                if g is not None and g[0] and v:
                    a = cells(v)
                    pa.append(len(a & g[0]) / max(len(a), 1))
                    ra.append(len(a & g[0]) / len(g[0]))
            f['p_prec'], f['p_rec'] = max(f['p_prec'], mean(pa)), max(f['p_rec'], mean(ra))
    return f
