"""In-context statistics of a partial clause: its table read against the task's train pairs, conditioned on what the input already says, and across examples, plus the way its atoms join. No gold, no label, no task name.

  features(r, text, pairs) -> {name: value or None}
"""
import collections
import math
import re
import sys

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/model/study/policy')
from outfeat import table

CAP = 400
FEATURES = {
    'ctx.cmi_changed': 'Information a Position set gives on whether a cell changes, given its input color, over the entropy of that change given the input color. Best Position column.',
    'ctx.cmi_out': 'Information a Position set gives on a cell\'s output color, given its input color, over the entropy of output color given input color. Best Position column.',
    'ctx.col_det': 'Rise in the majority share of output color at a row\'s cell, when grouped by another column\'s value across examples, over the share with no grouping. Best pair of columns.',
    'ctx.col_det_ch': 'The same rise for whether the cell changes.',
    'ctx.rec_min': 'Smallest share over train examples of target cells that a Position set covers. Target: changed cells, or output foreground where sizes differ.',
    'ctx.prec_min': 'Smallest share over train examples of a Position set that is target cells.',
    'ctx.rows_eq': 'One when rows per example equal one count of the output or input in every example.',
    'ctx.rows_ratio': 'One when rows per example are a fixed multiple of such a count in every example.',
    'ctx.rows_rank': 'Largest absolute rank correlation across examples between rows and such a count.',
    'ctx.dist_eq': 'One when a column\'s distinct values per example equal such a count in every example.',
    'ctx.val_eq': 'One when a one-valued number column equals such a count in every example.',
    'ctx.color_new': 'Share of output-only colors that a Color column holds, smallest over examples.',
    'ctx.rows_cv': 'Spread of rows per example over their mean.',
    'shape.binds': 'Labels the atoms bind.',
    'shape.reads': 'Label reads in the atoms.',
    'shape.join': 'Reads over binds plus reads.',
    'shape.unjoined': 'Atoms after the first that read no earlier label.',
    'shape.neg': 'NOT atoms.',
    'shape.scope': 'Atoms that read a scope table.',
    'shape.input': 'Atoms that read the input grid.',
    'shape.dup': 'Atoms that repeat a relation of an earlier atom.',
    'shape.cmp': 'Comparison atoms.',
}
ATOM = re.compile(r'\((?:NOT \()?(\S+)')
BIND = re.compile(r'\*[A-Za-z]')
READ = re.compile(r'\(:\w+ ([A-Za-z]\w*)\)')
CMP = {'!=', '<', '<=', '>', '>=', '='}


def ent(c):
    n = sum(c.values())
    return -sum(v / n * math.log2(v / n) for v in c.values() if v) if n else 0.


def facts(pairs):
    k = getattr(pairs[0], 'ctx_facts', None)
    if k is not None:
        return k
    O = [dict(changed=len(p.changed), ofg=len(p.ofg), ocolors=len(p.ocolors), new=len(p.newcolors), oh=len(p.b), ow=len(p.b[0]), oobj=len(p.oobj), iobj=len(p.iobj), area=p.area, icolors=len(p.colors), ifg=len(p.fg)) for p in pairs]
    ch = collections.Counter(); co = collections.Counter(); cc = collections.Counter(); coo = collections.Counter()
    for p in pairs:
        if p.same:
            for i in range(p.h):
                for j in range(p.w):
                    a, b = p.a[i][j], p.b[i][j]
                    ch[a, a != b] += 1; cc[a] += 1; coo[a, b] += 1
    k = dict(O=O, ch=ch, cc=cc, coo=coo, names=list(O[0]))
    pairs[0].ctx_facts = k
    return k


def cond_ent(joint, keys):
    """H(y | x) from counts {(x, y): n}."""
    by = collections.defaultdict(collections.Counter)
    for (x, y), n in joint.items():
        by[x][y] += n
    N = sum(joint.values()) or 1
    return sum(sum(c.values()) / N * ent(c) for c in by.values())


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.] * len(v); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sa = sum((x - ma) ** 2 for x in a); sb = sum((x - mb) ** 2 for x in b)
    if not sa or not sb:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sa * sb)


def shape(text, out):
    seen, rels, bind, read, unj, neg, sc, inp, dup, cmp_ = set(), set(), 0, 0, 0, 0, 0, 0, 0, 0
    for i, t in enumerate(text):
        m = ATOM.match(t); rel = m[1] if m else t
        b = BIND.findall(t); r = READ.findall(t)
        bind += len(b); read += len(r)
        if i and not any(x in seen for x in r):
            unj += 1
        seen.update(x[1:] for x in re.findall(r'\*\w+', t))
        neg += t.startswith('(NOT'); sc += rel.startswith('&'); inp += rel in ('input', 'ex_input'); dup += rel in rels; cmp_ += rel in CMP
        rels.add(rel)
    out.update({'shape.binds': bind, 'shape.reads': read, 'shape.join': read / (bind + read) if bind + read else None, 'shape.unjoined': unj, 'shape.neg': neg, 'shape.scope': sc, 'shape.input': inp, 'shape.dup': dup, 'shape.cmp': cmp_})


def features(r, text, pairs):
    out = {k: None for k in FEATURES}
    try:
        shape(text, out)
        types, tab = table(r, pairs)
        if tab:
            content(out, types, tab, pairs)
    except Exception:  # noqa: BLE001
        pass
    return out


def content(out, types, tab, pairs):
    F = facts(pairs); O = F['O']
    pos = [i for i, t in enumerate(types) if t == 'Position']
    rows = [len(tab.get(e, ())) for e in range(len(pairs))]
    m = sum(rows) / len(rows)
    out['ctx.rows_cv'] = (sum((x - m) ** 2 for x in rows) / len(rows)) ** .5 / m if m else None
    vec = {k: [o[k] for o in O] for k in F['names']}
    out['ctx.rows_eq'] = float(any(rows == v for v in vec.values()))
    out['ctx.rows_ratio'] = float(any(all(x and y and rows[0] * y == x * v[0] for x, y in zip(v, rows)) for v in vec.values() if v[0]))
    if len(rows) >= 3:
        c = [corr(rank(rows), rank(v)) for v in vec.values()]
        c = [abs(x) for x in c if x is not None]
        out['ctx.rows_rank'] = max(c) if c else None
    tabs = [tab.get(e, ())[:CAP] for e in range(len(pairs))]
    d_eq = v_eq = 0.; cn = None
    for j, t in enumerate(types):
        dist = [len({x[j] for x in rs}) for rs in tabs]
        if any(dist == v for v in vec.values()):
            d_eq = 1.
        if t in ('Nat', 'Int') and all(d == 1 for d in dist):
            vals = [x[0][j][0] for x in tabs]
            if any(vals == v for v in vec.values()):
                v_eq = 1.
        if t == 'Color':
            s = [min((len({x[j][0] for x in rs} & p.newcolors) / len(p.newcolors)) for _ in (0,)) for rs, p in zip(tabs, pairs) if p.newcolors]
            if s:
                cn = max(cn or 0., min(s))
    out['ctx.dist_eq'] = d_eq; out['ctx.val_eq'] = v_eq; out['ctx.color_new'] = cn
    if not pos:
        return
    H_ch = cond_ent(F['ch'], None); H_o = cond_ent(F['coo'], None)
    best = {k: None for k in ('ctx.cmi_changed', 'ctx.cmi_out', 'ctx.col_det', 'ctx.col_det_ch', 'ctx.rec_min', 'ctx.prec_min')}
    up = lambda k, v: best.__setitem__(k, v if best[k] is None or v > best[k] else best[k])
    for pi in pos:
        rec, prec = [], []; ch_in = collections.Counter(); o_in = collections.Counter(); groups = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
        for e, (p, rs) in enumerate(zip(pairs, tabs)):
            S = {(x[pi][0], x[pi][2]) for x in rs}
            T = p.changed if p.same else p.ofg
            if T:
                rec.append(len(S & T) / len(T))
            if S:
                prec.append(len(S & T) / len(S))
            if p.same:
                for i, j in S:
                    if 0 <= i < p.h and 0 <= j < p.w:
                        a, b = p.a[i][j], p.b[i][j]
                        ch_in[a, a != b] += 1; o_in[a, b] += 1
            for x in rs:
                i, j = x[pi][0], x[pi][2]
                if 0 <= i < len(p.b) and 0 <= j < len(p.b[0]):
                    for c, t in enumerate(types):
                        if c != pi:
                            groups[c][x[c]][p.b[i][j]] += 1
                            if p.same:
                                groups[-1 - c][x[c]][p.a[i][j] != p.b[i][j]] += 1
        if rec:
            up('ctx.rec_min', min(rec))
        if prec:
            up('ctx.prec_min', min(prec))
        if F['ch']:
            if H_ch:
                j = collections.Counter()
                for (a, c), n in F['ch'].items():
                    k = ch_in.get((a, c), 0)
                    j[(a, 1), c] += k; j[(a, 0), c] += n - k
                up('ctx.cmi_changed', max(0., (H_ch - cond_ent(j, None)) / H_ch))
            if H_o:
                j = collections.Counter()
                for (a, b), n in F['coo'].items():
                    k = o_in.get((a, b), 0)
                    j[(a, 1), b] += k; j[(a, 0), b] += n - k
                up('ctx.cmi_out', max(0., (H_o - cond_ent(j, None)) / H_o))
        for c, g in groups.items():
            tot = collections.Counter()
            for v in g.values():
                tot.update(v)
            n = sum(tot.values())
            if n and len(g) > 1:
                gain = sum(max(v.values()) for v in g.values()) / n - max(tot.values()) / n
                up('ctx.col_det' if c >= 0 else 'ctx.col_det_ch', gain)
    out.update(best)
