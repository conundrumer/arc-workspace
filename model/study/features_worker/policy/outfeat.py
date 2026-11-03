"""Distance of a node to OUT, and A -> B link features. A node's table is painted on the train inputs and compared with the train outputs.

A table with a Position and a Color column paints each cell on a copy of the input; where input and output differ in size, it paints on a blank
grid of the output's size and background. A table with a Position column alone gives a set of cells that one color could fill. The base count
is the number of wrong cells before any paint. No gold, no age, no written order.
"""
import collections
import itertools
import math

from nodefeat import columns


def base_of(p, i, j):
    return p.a[i][j] if p.same else p.obg


def base_err(p):
    return len(p.changed) if p.same else len(p.ofg)


def paint_one(p, e, cells):
    """cells: {(i, j): set of colors}. Returns fixed cells, broken cells, cells still wrong, out-of-bounds count, conflicts."""
    fixed, broke, stale = set(), set(), set()
    oob = conflict = 0
    H, W = len(p.b), len(p.b[0])
    for (i, j), cs in cells.items():
        if not (0 <= i < H and 0 <= j < W):
            oob += 1
            continue
        conflict += len(cs) > 1
        v = next(iter(cs)) if len(cs) == 1 else None
        want = p.b[i][j]
        was = base_of(p, i, j) == want
        if v == want:
            if not was:
                fixed.add((e, i, j))
        elif was:
            broke.add((e, i, j))
        else:
            stale.add((e, i, j))
    return fixed, broke, stale, oob, conflict


def entropy(p):
    return 0.0 if p <= 0 or p >= 1 else -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def split_power(p, S):
    """The share of the entropy of "this cell changes" that membership in the cell set S removes. None where the sizes differ or nothing changes."""
    n, c = p.area, len(p.changed)
    if not p.same or not c or c == n:
        return None
    S = {x for x in S if 0 <= x[0] < p.h and 0 <= x[1] < p.w}
    m, a = len(S), len(S & p.changed)
    h = entropy(c / n)
    rest = (m / n) * (entropy(a / m) if m else 0.0) + ((n - m) / n) * (entropy((c - a) / (n - m)) if n > m else 0.0)
    return (h - rest) / h


def table(node, pairs):
    """Per train example, the rows as tuples of cells. Only examples with a pair."""
    types = node.get('table_types') or node['types']
    out = {}
    for ent in node.get('x_rows') or []:
        (a, e), rows = ent[0], ent[1]
        if a != 1 or e >= len(pairs):
            continue
        c = columns(rows, types)
        if c is not None:
            out[e] = c
    return types, out


def out_features(node, pairs):
    """The OUT distance features, and the node's fixed-cell set and cell set for the link pass."""
    types, tab = table(node, pairs)
    d = {}; state = dict(fixed=set(), cells=set(), gain=None, rows=sum(map(len, tab.values())))
    base = sum(base_err(p) for p in pairs) or 1
    pos = [i for i, t in enumerate(types) if t == 'Position']
    col = [i for i, t in enumerate(types) if t == 'Color']
    if not pos or not tab:
        return d, state
    best = None
    for pi, ci in itertools.product(pos, col):
        fixed, broke, stale = set(), set(), set(); oob = conflict = 0; per = []
        remap = {}; remap_ok = True
        for e, p in enumerate(pairs):
            cells = collections.defaultdict(set)
            for r in tab.get(e, ()):
                cells[(r[pi][0], r[pi][2])].add(r[ci][0])
            f, b, s, o, c = paint_one(p, e, cells)
            fixed |= f; broke |= b; stale |= s; oob += o; conflict += c
            be = base_err(p)
            per.append((be - len(f) + len(b)) / be if be else float(len(b) > 0))
            for (i, j), cs in cells.items():
                if len(cs) == 1 and 0 <= i < len(p.b) and 0 <= j < len(p.b[0]):
                    v = next(iter(cs))
                    if remap.setdefault(v, p.b[i][j]) != p.b[i][j]:
                        remap_ok = False
        err = base - len(fixed) + len(broke)
        if best is None or err < best[0]:
            best = err, fixed, broke, stale, oob, conflict, per, remap_ok, remap
    if best is not None:
        err, fixed, broke, stale, oob, conflict, per, remap_ok, remap = best
        n = len(fixed) + len(broke) + len(stale)
        d['out_err'] = err / base
        d['out_gain'] = 1 - err / base
        d['out_exact'] = float(err == 0 and oob == 0)
        d['out_rec'] = len(fixed) / base
        d['out_prec'] = len(fixed) / n if n else 0.0
        d['out_broke'] = len(broke) / base
        d['out_oob'] = float(oob > 0)
        d['out_conflict'] = float(conflict > 0)
        d['out_pair_best'] = 1 - min(per); d['out_pair_worst'] = 1 - max(per)
        d['out_pairs_exact'] = sum(x == 0 for x in per) / len(per)
        d['out_pairs_fixed'] = sum(x < 1 for x in per) / len(per)
        d['near_only_missing'] = float(err > 0 and not broke and not stale and fixed != set())
        d['near_only_extra'] = float(len(fixed) == base and err > 0)
        d['near_remap'] = float(remap_ok and any(k != v for k, v in remap.items()) and not fixed)
        state['fixed'] = fixed; state['gain'] = d['out_gain']
    power = [[x for e, p in enumerate(pairs) if (x := split_power(p, {(r[pi][0], r[pi][2]) for r in tab.get(e, ())})) is not None] for pi in pos]
    power = [x for x in power if x]
    if power:
        d['split_worst'] = max(min(x) for x in power); d['split_mean'] = max(sum(x) / len(x) for x in power)
    # A Position column with no paint color: how close one fill color comes.
    bestf = None
    for pi in pos:
        got = own = 0; cells = set(); inside = n = 0
        for e, p in enumerate(pairs):
            S = {(r[pi][0], r[pi][2]) for r in tab.get(e, ())}
            S = {(i, j) for i, j in S if 0 <= i < len(p.b) and 0 <= j < len(p.b[0])}
            cells |= {(e, i, j) for i, j in S}
            c = collections.Counter(p.b[i][j] for i, j in S)
            if c:
                v, m = c.most_common(1)[0]
                got += sum(1 for i, j in S if p.b[i][j] == v and base_of(p, i, j) != v)
                own += sum(1 for i, j in S if p.b[i][j] != v and base_of(p, i, j) == p.b[i][j])
                inside += m; n += len(S)
        g = (got - own) / base
        if bestf is None or g > bestf[0]:
            bestf = g, got / base, inside / n if n else 0.0, cells
    if bestf is not None:
        d['fill_gain'] = bestf[0]; d['fill_rec'] = bestf[1]; d['fill_one_color'] = bestf[2]
        d['near_fill'] = float(bestf[2] == 1.0 and bestf[1] > 0)
        state['cells'] = bestf[3]
        if state['gain'] is None:
            state['gain'] = bestf[0]
    return d, state


def link_one(ps, d, s, nodes):
    """Adds link_* to the features d of a node with state s. ps: its parents' tokens. nodes: {token: (parents, features, state)}, parents included."""
    base_cells = lambda x: x['fixed'] or x['cells']
    par = [nodes[p] for p in ps if p in nodes]
    d['link_np'] = len(par)
    scored = [x[2] for x in par if x[2]['gain'] is not None]
    fb = base_cells(s)
    if scored:
        top = max(x['gain'] for x in scored)
        d['link_parent_gain'] = top
        if s['gain'] is not None:
            d['link_adds'] = s['gain'] - top
            d['link_better'] = float(s['gain'] > top)
            u = set().union(*(base_cells(x) for x in scored))
            d['link_new_cells'] = len(fb - u) / max(len(fb), 1)
            d['link_new_count'] = len(fb - u)
            d['link_pair_union'] = max((len(fb | base_cells(x)) - max(len(fb), len(base_cells(x)))) / max(len(fb | base_cells(x)), 1) for x in scored)
            sub = [x for x in scored if s['cells'] and x['cells']]
            d['link_filter'] = float(any(s['cells'] < x['cells'] for x in sub))
            d['link_grow'] = float(any(s['cells'] > x['cells'] for x in sub))
            d['link_disjoint'] = float(bool(sub) and all(not s['cells'] & x['cells'] for x in sub))
    if par:
        d['link_row_ratio'] = (s['rows'] + 1) / (max(x[2]['rows'] for x in par) + 1)


def link_features(nodes):
    """nodes: {token: (parents, features, state)}. Adds link_* to each node's features, and kid_* from the nodes that read it."""
    kids = collections.defaultdict(list)
    for t, (ps, _, _) in nodes.items():
        for p in ps:
            kids[p].append(t)
    for t, (ps, d, s) in nodes.items():
        link_one(ps, d, s, nodes)
        rd = [nodes[k][2] for k in kids.get(t, ())]
        d['kid_n'] = len(rd)
        rd = [x for x in rd if x['gain'] is not None]
        if rd:
            d['kid_best'] = max(x['gain'] for x in rd)
            if s['gain'] is not None:
                d['kid_best_adds'] = d['kid_best'] - s['gain']
