"""Round 14, explorer c: orientation values and the relations over them (orientation.dl).

The library tables of the orientation relations are rebuilt here from `programs/lib/orientation.dl`, in the encoding of
the exported cells: Dir T B L R = 0 1 2 3, DiagDir TL TR BL BR = 256 257 258 259, Axis V H = 512 513, DiagAxis DG AD =
768 769, D4 ID CW HT CC LR TB DG AD = 1024..1031, Sym = 1280..1289, Sense CW CC = 1536 1537.
"""
import collections as C
import functools
import itertools

from featlib import feature

MAX_ROWS = 150000


def _safe(fn):
    """A feature function that returns None where it would raise or where X is too large."""
    @functools.wraps(fn)
    def run(p):
        try:
            if sum(len(e['rows']) for e in p.x.entries) > MAX_ROWS:
                return None
            return fn(p)
        except Exception:
            return None
    return run

T, B, L, R = 0, 1, 2, 3
TL, TR, BL, BR = 256, 257, 258, 259
V, H = 512, 513
DG, AD = 768, 769
D4N = ['ID', 'CW', 'HT', 'CC', 'LR', 'TB', 'DG', 'AD']
D4V = {n: 1024 + i for i, n in enumerate(D4N)}
SYMN = ['1', 'LR', 'TB', 'HT', 'DG', 'AD', 'BOX', 'X', 'C4', 'D4']
SYMV = {n: 1280 + i for i, n in enumerate(SYMN)}
SCW, SCC = 1536, 1537


def _tables():
    t = {}
    dirs, diags, axes, daxes = [T, B, L, R], [TL, TR, BL, BR], [V, H], [DG, AD]
    t['dir_elem'] = (('d',), [(d,) for d in dirs])
    t['axis_elem'] = (('a',), [(a,) for a in axes])
    t['diag_dir_elem'] = (('d',), [(d,) for d in diags])
    t['diag_axis_elem'] = (('da',), [(a,) for a in daxes])
    t['dir8_elem'] = (('d',), [(d,) for d in dirs + diags])
    t['axis4_elem'] = (('a',), [(a,) for a in axes + daxes])
    t['d4_elem'] = (('d',), [(D4V[n],) for n in D4N])
    t['c4_elem'] = (('d',), [(D4V[n],) for n in D4N[:4]])
    t['sense_elem'] = (('s',), [(SCW,), (SCC,)])
    t['sym_elem'] = (('s',), [(SYMV[n],) for n in SYMN])
    mem = {'1': ['ID'], 'LR': ['ID', 'LR'], 'TB': ['ID', 'TB'], 'HT': ['ID', 'HT'], 'DG': ['ID', 'DG'], 'AD': ['ID', 'AD'],
           'BOX': ['ID', 'LR', 'TB', 'HT'], 'X': ['ID', 'DG', 'AD', 'HT'], 'C4': D4N[:4], 'D4': D4N}
    t['sym_member'] = (('s', 'd'), [(SYMV[s], D4V[d]) for s, ds in mem.items() for d in ds])
    axis_of = [(T, V), (B, V), (L, H), (R, H)]
    diag_axis_of = [(TL, DG), (BR, DG), (TR, AD), (BL, AD)]
    t['axis_of'] = (('d', 'a'), axis_of)
    t['diag_axis_of'] = (('d', 'da'), diag_axis_of)
    t['axis4_of'] = (('d', 'a'), axis_of + diag_axis_of)
    dir_of = [(TL, V, T), (TL, H, L), (TR, V, T), (TR, H, R), (BL, V, B), (BL, H, L), (BR, V, B), (BR, H, R)]
    t['dir_of'] = (('d', 'a', 'dir'), dir_of)
    perp = [(V, H), (H, V)]
    t['perp'] = (('a', 'a2'), perp)
    t['diag_perp'] = (('da', 'da2'), [(DG, AD), (AD, DG)])
    t['diag_dirs'] = (('d', 'a', 'd1', 'd2'),
                      [(d, a, d1, d2) for d, a, d1 in dir_of for (d_, a2, d2) in dir_of if d_ == d and a2 != a])
    t['opposite'] = (('d', 'opp'), [(T, B), (B, T), (L, R), (R, L)])
    t['diag_opposite'] = (('d', 'opp'), [(TL, BR), (BR, TL), (TR, BL), (BL, TR)])
    t['dir8_opposite'] = (('d', 'd2'), t['opposite'][1] + t['diag_opposite'][1])
    t['perp_dir'] = (('d', 'd2'), [(d, d2) for d, a in axis_of for (d2, a2) in axis_of if a2 != a])
    t['flip_of'] = (('a', 'd'), [(V, D4V['TB']), (H, D4V['LR'])])
    t['diag_flip_of'] = (('da', 'd'), [(DG, D4V['DG']), (AD, D4V['AD'])])
    cw = [(T, R), (R, B), (B, L), (L, T)]
    t['turn'] = (('s', 'd', 'd_out'), [(SCW, a, b) for a, b in cw] + [(SCC, b, a) for a, b in cw])
    t['rotation'] = (('s', 'd'), [(SCW, D4V['CW']), (SCC, D4V['CC'])])
    inv = {'ID': 'ID', 'CW': 'CC', 'HT': 'HT', 'CC': 'CW', 'LR': 'LR', 'TB': 'TB', 'DG': 'DG', 'AD': 'AD'}
    t['d4_inverse'] = (('d', 'd_inv'), [(D4V[a], D4V[b]) for a, b in inv.items()])
    comp = {}
    # d4_compose(a, b, c): c is a after b. Rotation r^k, reflections s r^k as permutations of the corners.
    # Represent each element as a map on the square's 4 corners (0 TL, 1 TR, 2 BR, 3 BL).
    perm = {'ID': (0, 1, 2, 3), 'CW': (1, 2, 3, 0), 'HT': (2, 3, 0, 1), 'CC': (3, 0, 1, 2),
            'LR': (1, 0, 3, 2), 'TB': (3, 2, 1, 0), 'DG': (0, 3, 2, 1), 'AD': (2, 1, 0, 3)}
    inv_perm = {v: k for k, v in perm.items()}
    rows = []
    for a in D4N:
        for b in D4N:
            c = tuple(perm[a][perm[b][i]] for i in range(4))
            rows.append((D4V[a], D4V[b], D4V[inv_perm[c]]))
    t['d4_compose'] = (('a', 'b', 'c'), rows)
    return t


LIB = _tables()


ORI_TYPES = ('Dir', 'Axis', 'DiagDir', 'DiagAxis', 'Dir8', 'Axis4', 'D4', 'C4', 'Sense', 'Sym')
JOIN_CAP = 20000


def _positions(a):
    """[(index in the library table, label)] of the arguments of the atom `a` of an orientation relation, by the place
    of each argument's column in the relation's interface; None where an argument is a literal or the interface does
    not match the table."""
    cols = LIB[a.relation][0]
    iface = a.interface
    names = list(iface.columns) if iface is not None and getattr(iface, 'columns', None) else None
    if names is None or len(names) != len(cols):
        return None
    out = []
    for g in a.arguments:
        if g.label is None or g.is_zero or g.column not in names:
            return None
        out.append((names.index(g.column), g.label))
    return out


def _lib_atoms(p):
    """The positive, unconditional atoms of the candidate's body that read an orientation relation, each as
    (relation, [(table column index, label)]); an atom whose columns the table lacks is left out."""
    out = []
    try:
        body = p.clause.body
    except Exception:
        return out
    if body is None:
        return out
    for a in body.atoms:
        if a.relation not in LIB or a.negated or a.branch or a.quantifier or a.conditional or a.kind == 'comparison':
            continue
        pos = _positions(a)
        if pos:
            out.append((a.relation, pos))
    return out


def _join(atoms):
    """The join of the library tables of those atoms: a list of {label: value}; None past the cap."""
    cur = [{}]
    for rel, pos in atoms:
        rows = LIB[rel][1]
        nxt = []
        for b in cur:
            for row in rows:
                nb = dict(b)
                good = True
                for i, lab in pos:
                    v = row[i]
                    if nb.setdefault(lab, v) != v:
                        good = False
                        break
                if good:
                    nxt.append(nb)
        # set semantics: unique bindings
        seen = set()
        cur = []
        for b in nxt:
            k = tuple(sorted(b.items()))
            if k not in seen:
                seen.add(k)
                cur.append(b)
        if len(cur) > JOIN_CAP:
            return None
    return cur


def _x_contexts(p, labels):
    """For each context (assignment, example, model) of X: the set of value tuples over the X columns that hold those
    labels (a label held by several columns takes the first). None where a label has no column."""
    x = p.x
    cols = x.columns()
    var = getattr(p.clause, 'x_columns', None) or {}
    idx = {}
    for name, v in var.items():
        c = x.column(name)
        if c is not None and v is not None and v.label in labels and v.label not in idx:
            idx[v.label] = c.index
    if not idx:
        return None, None
    order = sorted(idx)
    out = {}
    for (asg, ex), models in x.examples().items():
        for mi, rows in enumerate(models):
            out[asg, ex, mi] = {tuple(r[idx[l]] for l in order) for r in rows}
    return order, out


def _fills(p):
    atoms = _lib_atoms(p)
    if not atoms:
        return None
    join = _join(atoms)
    if not join:
        return None
    labels = {lab for _, pos in atoms for _, lab in pos}
    order, ctxs = _x_contexts(p, labels)
    if not order:
        return None
    proj = {tuple(b[l] for l in order) for b in join}
    fills, viol = [], []
    for s in ctxs.values():
        if not s:
            continue
        fills.append(len(s & proj) / len(proj))
        viol.append(len(s - proj) / len(s))
    if not fills:
        return None
    return order, proj, fills, viol, ctxs


@feature
@_safe
def c1_lib_fill(p):
    """C1 Orientation fill. The orientation relations of the body (positive, unconditional atoms) joined alone give a
    table J. `fill`: the share of J's tuples, over the X columns that hold J's labels, that X has, averaged over
    the contexts (examples) with rows; `fill_min` the smallest; `full` 1 where every context has all of J (the
    relations enumerate and nothing else of the clause removes a value); `viol` the share of X's tuples outside J
    (0 when the library tables here agree with the engine's). `pure`: 1 where every non-Example column of X is named by an orientation atom and `full` is 1, so that X is the library join and holds nothing of the task. `ori_only`: 1 where every non-Example column of X has an orientation type. Without such an atom (or an X column for it) `full`, `pure` and `ori_only` are given, as 0."""
    r = _fills(p)
    if r is None:
        return {'full': 0.0, 'pure': 0.0, 'ori_only': 0.0}
    order, proj, fills, viol, _ = r
    x = p.x
    var = getattr(p.clause, 'x_columns', None) or {}
    labels = {lab for _, pos in _lib_atoms(p) for _, lab in pos}
    cols = [c for c in x.columns() if c.type != 'Example']
    named = bool(cols) and all(var.get(c.name) is not None and var[c.name].label in labels for c in cols)
    ori_only = bool(cols) and all(c.type in ORI_TYPES for c in cols)
    full = float(min(fills) >= 1.0)
    return {'fill': sum(fills) / len(fills), 'fill_min': min(fills), 'full': full,
            'viol': sum(viol) / len(viol), 'jn': float(len(proj)), 'pure': float(named and full == 1.0),
            'ori_only': float(ori_only)}


def _ori_split(p):
    """Per context (assignment, example, model) of X: the set of rows as (orientation part, rest part), where the
    orientation part holds the columns of an orientation type that an orientation relation of the body names, and the
    rest holds every other column except Example columns. None without an orientation column."""
    atoms = _lib_atoms(p)
    if not atoms:
        return None
    labels = {lab for _, pos in atoms for _, lab in pos}
    x = p.x
    var = getattr(p.clause, 'x_columns', None) or {}
    cols = x.columns()
    ori, rest, seen = [], [], set()
    for name, v in var.items():
        c = x.column(name)
        if c is None or c.index in seen:
            continue
        seen.add(c.index)
        if v is not None and v.label in labels and c.type in ORI_TYPES:
            ori.append(c.index)
        elif c.type != 'Example':
            rest.append(c.index)
    if not ori:
        return None
    ctx = {}
    for (asg, ex), models in x.examples().items():
        for mi, rows in enumerate(models):
            ctx[asg, ex, mi] = {(tuple(r[i] for i in ori), tuple(r[i] for i in rest)) for r in rows}
    return ori, rest, ctx


@feature
@_safe
def c2_ori_density(p):
    """C2 Orientation idle. Over the contexts of X with rows, the rows are split into the orientation columns (those
    that an orientation relation of the body names) and the rest. `dens`: the mean over contexts of rows / (distinct
    orientation parts x distinct rest parts); 1 where the orientation part and the rest are independent (the
    orientation columns multiply the rest and change none of it). `dens_min`: the smallest. `idle`: 1 where `dens` is
    1 in every context with two or more orientation parts. `uniq`: the mean share of rest parts that occur with one
    orientation part (the rest determines the orientation). `jac`: the mean Jaccard overlap of the rest sets of two
    orientation parts. `exvar`: 1 where the set of orientation parts differs between contexts (with 2 or more contexts).
    `nori`: the mean number of distinct orientation parts per context. Without an orientation relation in the body or an orientation column in X only `idle` is given, as 0."""
    r = _ori_split(p)
    if r is None:
        return {'idle': 0.0}
    ori, rest, ctx = r
    dens, nori, sets, uniq, jac = [], [], [], [], []
    for rows in ctx.values():
        if not rows:
            continue
        by = C.defaultdict(set)
        seen = C.Counter()
        for a, b in rows:
            by[a].add(b)
            seen[b] += 1
        po, pr = len(by), len(seen)
        dens.append(len(rows) / (po * pr))
        nori.append(po)
        sets.append(frozenset(by))
        if rest:
            uniq.append(sum(1 for c in seen.values() if c == 1) / pr)
        if po >= 2:
            keys = sorted(by, key=repr)[:12]
            js = []
            for i in range(len(keys)):
                for j in range(i + 1, len(keys)):
                    u = len(by[keys[i]] | by[keys[j]])
                    js.append(len(by[keys[i]] & by[keys[j]]) / u if u else 1.0)
            jac.append(sum(js) / len(js))
    if not dens:
        return {'idle': 0.0}
    multi = [d for d, n in zip(dens, nori) if n >= 2]
    out = {'dens': sum(dens) / len(dens), 'dens_min': min(dens),
           'idle': float(bool(multi) and min(multi) >= 1.0), 'nori': sum(nori) / len(nori),
           'rest': float(len(rest)), 'nctx': float(len(sets)), 'nori_all': float(len(frozenset().union(*sets)))}
    if len(sets) > 1:
        out['exvar'] = float(len(set(sets)) > 1)
    if uniq:
        out['uniq'] = sum(uniq) / len(uniq)
    if jac:
        out['jac'] = sum(jac) / len(jac)
    return out


# Relations that pair a value with its mirror, with the value map where the relation is a function of its first column.
PAIRED = {
    'opposite': {T: B, B: T, L: R, R: L},
    'diag_opposite': {TL: BR, BR: TL, TR: BL, BL: TR},
    'dir8_opposite': {T: B, B: T, L: R, R: L, TL: BR, BR: TL, TR: BL, BL: TR},
    'perp': {V: H, H: V},
    'diag_perp': {DG: AD, AD: DG},
    'perp_dir': None,
}


def _paired_atoms(p):
    """(relation, first label, second label) of the positive, unconditional atoms of a paired relation."""
    out = []
    try:
        body = p.clause.body
    except Exception:
        return out
    if body is None:
        return out
    for a in body.atoms:
        if a.relation not in PAIRED or a.negated or a.branch or a.quantifier or a.conditional:
            continue
        pos = _positions(a)
        if pos and len(pos) == 2:
            by = dict(pos)
            if 0 in by and 1 in by and by[0] != by[1]:
                out.append((a.relation, by[0], by[1]))
    return out


@feature
@_safe
def c3_paired_closure(p):
    """C3 Mirror closure. For each atom of `opposite`, `diag_opposite`, `dir8_opposite`, `perp`, `diag_perp` or
    `perp_dir` (positive, unconditional) with both labels at the atom: `closed`, the share of X's rows (mean over the
    contexts with rows) whose mirror row is also in X. The mirror row swaps the two labels' columns where both are in
    X, and replaces the first label's value by its pair where only the first is in X (the relations that are functions);
    the clause treats the pair symmetrically when the share is 1. Keys: `closed` (mean over the atoms), `closed_min`,
    `n` (atoms scored), `all_closed` (1 where every atom scored has share 1). Without a scorable atom only `all_closed` is given, as 0."""
    atoms = _paired_atoms(p)
    if not atoms:
        return {'all_closed': 0.0}
    x = p.x
    var = getattr(p.clause, 'x_columns', None) or {}
    lab = {}
    for name, v in var.items():
        c = x.column(name)
        if c is not None and v is not None and v.label not in lab:
            lab[v.label] = c.index
    ctx = [rows for models in x.examples().values() for rows in models if rows]
    if not ctx:
        return {'all_closed': 0.0}
    res = []
    for rel, a, b in atoms:
        ia, ib = lab.get(a), lab.get(b)
        mp = PAIRED[rel]
        if ia is None:
            continue
        shares = []
        for rows in ctx:
            rs = set(rows)
            n = ok = 0
            for r in rows:
                if ib is not None:
                    q = list(r)
                    q[ia], q[ib] = r[ib], r[ia]
                elif mp is not None and r[ia] in mp:
                    q = list(r)
                    q[ia] = mp[r[ia]]
                else:
                    continue
                n += 1
                ok += tuple(q) in rs
            if n:
                shares.append(ok / n)
        if shares:
            res.append(sum(shares) / len(shares))
    if not res:
        return {'all_closed': 0.0}
    return {'closed': sum(res) / len(res), 'closed_min': min(res), 'n': float(len(res)),
            'all_closed': float(min(res) >= 1.0)}


# For a DiagDir value, the signs (vertical, horizontal) of "nearer to that corner": -1 is the top or left edge.
CORNER = {TL: (-1, -1), TR: (-1, 1), BL: (1, -1), BR: (1, 1)}
GRID_TYPES = ('Position', 'Box')


def _corner_side(m, sv, sh):
    """(exact, quadrant, opposite) of one decoded Position or Box margins `m` against the corner (sv, sh)."""
    top, bottom, left, right = m.margins
    v = (bottom - top)  # > 0 when nearer the top
    h = (right - left)  # > 0 when nearer the left
    want_v, want_h = -sv, -sh  # nearer the top edge means v > 0
    exact = (top == 0 if sv < 0 else bottom == 0) and (left == 0 if sh < 0 else right == 0)
    quad = v * want_v > 0 and h * want_h > 0
    opp = v * want_v < 0 and h * want_h < 0
    return exact, quad, opp


@feature
@_safe
def c4_corner_fit(p):
    """C4 Corner fit. Over each pair of a DiagDir column and a Position or Box column of X (one frame tag), the rows'
    cell against the corner the row names. Keys, for the pair with the largest `exact`: `exact`, the share of rows whose
    cell touches that corner of its frame (both margins 0); `quad`, the share that lie nearer that corner on both
    axes; `opp`, the share nearer the opposite corner on both axes. `pairs`: how many pairs. None without a DiagDir
    column and a Position or Box column."""
    x = p.x
    cols = x.columns()
    diag = [c for c in cols if c.type == 'DiagDir']
    cells = [c for c in cols if c.type in GRID_TYPES]
    if not diag or not cells:
        return None
    rows = [r for models in x.examples().values() for m in models for r in m]
    if not rows:
        return None
    best = None
    npairs = 0
    for d in diag:
        for c in cells:
            n = ex = qd = op = 0
            for r in rows:
                dv, m = r[d.index], r[c.index]
                if dv not in CORNER or not hasattr(m, 'margins'):
                    continue
                e, q, o = _corner_side(m, *CORNER[dv])
                n += 1
                ex += e
                qd += q
                op += o
            if n:
                npairs += 1
                cur = (ex / n, qd / n, op / n)
                if best is None or cur > best:
                    best = cur
    if best is None:
        return None
    return {'exact': best[0], 'quad': best[1], 'opp': best[2], 'pairs': float(npairs)}
