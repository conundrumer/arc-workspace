"""Facts of the derived pick model (design.md, "The facts"). One module, imported by rows.py, fit.py and job3.py, so that a training row and a read pick take their facts from the same code.

Pure part (no engine): Scope(texts, rels) holds the DAG and table facts of a scope; option_facts(scope, st, bases) gives, for the derived options of one atom start, a sparse
dict of raw facts each (a fact that is 0 is left out); gate_facts(...) the same for the atom start. A pick state `st` is a dict:
    hk  head kind (DET, INIT, RULE),  pl  place (RULE, DET, port, key, other),  ph  phase (root, root2),
    sty sorted list of the label types in scope,  dd  sorted list of [head, j] of the derived relations drawn so far (a set),  bd  whether a builtin relation was drawn.
The facts read the atom start as sets and flags only: never the atom index, the last atom, a position in a body, a slot or token number, a label name or a binder mark.
Build order enters as the rank of a form's fid among the scope's fids (recency); the fid value itself is never read.

Engine part: replay(texts, sess, d, env) gives the relations of a scope, with the row counts of each table, as REC/job.py:relations does plus those and the tables that do not parse.
Vectorising: Std holds the feature names, the means and scales; Std.matrix(dicts) gives the standardized matrix.

    python3 feats.py            runs the unit tests (facts are sets; renumbering; the facts do not equal or determine the atom index)
"""
import collections
import math
import re
import sys
import time

HEAD = re.compile(r'^\((\w+) (&f(\d+))')
REF = re.compile(r'&f(\d+)')
KINDS = ('DET', 'INIT', 'RULE')
PLACES = ('RULE', 'DET', 'port', 'key', 'other')
LIB_KINDS = ('lib relation', 'relation macro', 'fact relation')
DIAG = ('_k', '_nd', '_nb')  # per-row diagnostics (atom index, counts drawn): stored for the checks, never a fact


def kind_of(text):
    k = text.split()[0][1:]
    return 'DET' if k == 'RIGID_DET' else k


def place_of(p):
    return p if p in PLACES else 'other'


def r4(x):
    return round(float(x), 4)


class Scope:
    """The DAG and table facts of a scope. texts: the scope's form texts, in any order. rels: {(head, j): dict(key, types, nrows, labels, no_table)} of the tables replayed."""

    def __init__(self, texts, rels):
        forms = {}
        for t in texts:
            m = HEAD.match(t)
            fid = int(m.group(3))
            forms[fid] = (kind_of(t), {int(x) for x in REF.findall(t)} - {fid})
        self.fids = sorted(forms)
        self.parents = {f: forms[f][1] & forms.keys() for f in forms}
        self.kind = {f: forms[f][0] for f in forms}
        depth = {}

        def dep(f):
            if f not in depth:
                depth[f] = 1 + max((dep(p) for p in self.parents[f]), default=0)
            return depth[f]
        for f in forms:
            dep(f)
        self.depth, self.maxdepth = depth, max(depth.values()) if depth else 1
        anc = {}

        def ancs(f):
            if f not in anc:
                anc[f] = set()
                for p in self.parents[f]:
                    anc[f] |= {p} | ancs(p)
            return anc[f]
        for f in forms:
            ancs(f)
        self.anc = anc
        self.readers = collections.Counter(p for f in forms for p in self.parents[f])
        n = len(forms)
        self.nforms = n
        nrel = collections.Counter(h_fid(h) for (h, _) in rels if h_fid(h) in forms)
        self._forms, self._nrel = forms, nrel
        self.rel = {}
        for (h, j), r in rels.items():
            if h_fid(h) in forms:
                self.rel[(h, j)] = self._mk(h, j, r)

    def _mk(self, h, j, r):
        forms, depth, n = self._forms, self.depth, self.nforms
        f = h_fid(h)
        nr = r.get('nrows') or []
        types = list(r.get('types') or [])
        ct = collections.Counter(types)
        larger = sum(1 for g in forms if g > f)
        return dict(
            fid=f, kind=forms[f][0], sub=j is not None, key=r.get('key'), types=tuple(sorted(types)), nt=int(r.get('no_table', 0)),
            arity=len(types), lmean=math.log1p(sum(nr) / len(nr)) if nr else 0.0, lmax=math.log1p(max(nr)) if nr else 0.0,
            share=sum(1 for x in nr if x > 0) / len(nr) if nr else 0.0, ct=ct, blank=int('' in (r.get('labels') or [])),
            depth=depth[f], leaf=int(self.readers[f] == 0), root=int(not self.parents[f]), lread=math.log1p(self.readers[f]),
            lnrel=math.log(max(self._nrel[f], 1)), rec=larger / (n - 1) if n > 1 else 0.0, newest=int(larger == 0))

    def get(self, base):
        """The facts of the relation (head, j); a relation of a form of the scope that the replay gave no table for (for example an INIT's sub-relation without one) gets the form's
        facts with no_table 1; None where the form is not in the scope."""
        b = (base[0], base[1])
        if b not in self.rel and h_fid(b[0]) in self._forms:
            self.rel[b] = self._mk(b[0], b[1], dict(no_table=1))
        return self.rel.get(b)

    def has(self, base):
        return (base[0], base[1]) in self.rel


def drel_ex(sc, drawn, b):
    return [x for x in (sc.get(d) for d in drawn if d != b) if x is not None]


def h_fid(h):
    return int(h[2:])


def option_facts(sc, st, bases, miss=None):
    """[sparse dict of raw facts] for the derived options (ws > 0) of one atom start, aligned with bases ([head, j] each, in any order)."""
    bases = [(b[0], b[1]) for b in bases]
    stys = set(st['sty'])
    drawn = [(b[0], b[1]) for b in st['dd']]
    dset = set(drawn)
    dfids = {h_fid(b[0]) for b in drawn}
    drel = [x for x in (sc.get(b) for b in drawn) if x is not None]
    dtypes = set().union(*[set(r['types']) for r in drel]) if drel else set()
    danc = set().union(*[sc.anc.get(f, set()) for f in dfids]) if dfids else set()
    dpar = {f: sc.parents.get(f, set()) for f in dfids}
    nod = not drawn
    hk, pl, r2 = st['hk'], st['pl'], st['ph'] == 'root2'
    rs = [sc.get(b) for b in bases]
    out = []
    for i, (b, r) in enumerate(zip(bases, rs)):
        f = {}
        if r is None:  # an option with no table or form in the scope: no fact but the flag
            if miss is not None:
                miss[0] += 1
            f['notab'] = 1.0
            f['nosc'] = float(not stys)
            out.append(f)
            continue
        a = r['arity']
        f['ar%d' % min(max(a, 1), 4)] = 1.0 if a else 0.0
        f['lmean'], f['lmax'], f['share'] = r['lmean'], r['lmax'], r['share']
        for t, c in r['ct'].items():
            f['ct:' + t] = float(c)
        f['blank'], f['notab'] = float(r['blank']), float(r['nt'])
        tin = sum(c for t, c in r['ct'].items() if t in stys)
        f['tin'], f['tinf'] = float(tin), tin / a if a else 0.0
        f['nosc'] = float(not stys)
        others = [x for j, x in enumerate(rs) if j != i and x is not None]
        f['dupt'] = math.log1p(sum(1 for x in others if x['types'] == r['types']))
        f['dupk'] = float(r['key'] is not None and any(x['key'] == r['key'] for x in others))
        f['d%d' % min(r['depth'], 4)] = 1.0
        f['dmax'] = float(r['depth'] - sc.maxdepth)
        f['deep'] = float(r['depth'] == sc.maxdepth)
        f['leaf'], f['root'], f['lread'] = float(r['leaf']), float(r['root']), r['lread']
        f['kk:%sx%s' % (r['kind'], hk)] = 1.0
        f['sub'], f['lnrel'] = float(r['sub']), r['lnrel']
        f['rec'], f['newest'] = r['rec'], float(r['newest'])
        fid = r['fid']
        f['dr_self'] = float(b in dset)
        f['dr_sib'] = float(any(h_fid(d[0]) == fid and d != b for d in drawn))
        f['dr_anc'] = float(fid in danc)
        f['dr_desc'] = float(any(df in sc.anc.get(fid, ()) for df in dfids))
        f['dr_par'] = float(any(df != fid and dpar[df] & sc.parents.get(fid, set()) for df in dfids))
        f['dr_key'] = float(r['key'] is not None and any(x['key'] == r['key'] for x in drel_ex(sc, drawn, b)))
        f['dr_type'] = float(bool(set(r['types']) & dtypes))
        if nod:
            f['x_nod_leaf'], f['x_nod_deep'], f['x_nod_tin'] = f['leaf'], f['deep'], f['tin']
        f['x_%s_leaf' % pl], f['x_%s_sub' % pl], f['x_%s_dmax' % pl] = f['leaf'], f['sub'], f['dmax']
        if r2:
            f['x_r2_self'], f['x_r2_leaf'] = f['dr_self'], f['leaf']
        out.append({k: r4(v) for k, v in f.items() if v})
    return out


def gate_facts(sc, st, nD):
    """Raw gate facts of an atom start (variant M2), without the two that read the rank scores."""
    dd, bd = bool(st['dd']), bool(st['bd'])
    f = {'hk:' + st['hk']: 1.0, 'pl:' + st['pl']: 1.0, 'lnD': math.log(max(nD, 1)), 'lnf': math.log(max(sc.nforms, 1))}
    f.update(r2=float(st['ph'] == 'root2'), dd=float(dd), bd=float(bd), both=float(dd and bd), nosc=float(not st['sty']))
    return {k: r4(v) for k, v in f.items() if v}


def all_option_names():
    n = ['ar1', 'ar2', 'ar3', 'ar4', 'lmean', 'lmax', 'share', 'blank', 'notab', 'tin', 'tinf', 'nosc', 'dupt', 'dupk', 'd1', 'd2', 'd3', 'd4', 'dmax', 'deep', 'leaf', 'root', 'lread',
         'sub', 'lnrel', 'rec', 'newest', 'dr_self', 'dr_sib', 'dr_anc', 'dr_desc', 'dr_par', 'dr_key', 'dr_type', 'x_nod_leaf', 'x_nod_deep', 'x_nod_tin', 'x_r2_self', 'x_r2_leaf']
    n += ['kk:%sx%s' % (k, h) for k in KINDS for h in KINDS]
    n += ['x_%s_%s' % (p, s) for p in PLACES for s in ('leaf', 'sub', 'dmax')]
    return n


def all_gate_names():
    return ['hk:' + k for k in KINDS] + ['pl:' + p for p in PLACES] + ['r2', 'lnD', 'dd', 'bd', 'both', 'nosc', 'lnf', 'lse', 'mx']


class Std:
    """Feature names, means and scales. names are the columns; 'ct:T' columns for T in coltypes and 'ct:other' for the rest are part of the option names."""

    def __init__(self, names, mean, scale, coltypes=(), ignore=()):
        self.names, self.mean, self.scale, self.coltypes = list(names), list(mean), list(scale), list(coltypes)
        self.ignore = set(ignore)  # fact names that the model does not use (dropped from the fit): skipped by dense
        self.ix = {n: i for i, n in enumerate(self.names)}

    @staticmethod
    def column_names(base, coltypes):
        return list(base) + ['ct:' + t for t in coltypes] + (['ct:other'] if coltypes is not None else [])

    def dense(self, dicts):
        import numpy as np
        X = np.zeros((len(dicts), len(self.names)), dtype=np.float64)
        ct = set(self.coltypes)
        for r, d in enumerate(dicts):
            for k, v in d.items():
                if k in self.ignore:
                    continue
                if k.startswith('ct:') and k[3:] not in ct and k != 'ct:other':
                    X[r, self.ix['ct:other']] += v
                else:
                    X[r, self.ix[k]] += v  # an unknown name is an error
        return X

    def matrix(self, dicts):
        import numpy as np
        return (self.dense(dicts) - np.array(self.mean)) / np.array(self.scale)

    def to_json(self):
        return dict(names=self.names, mean=self.mean, scale=self.scale, coltypes=self.coltypes, ignore=sorted(self.ignore))

    @staticmethod
    def from_json(d):
        return Std(d['names'], d['mean'], d['scale'], d['coltypes'], d.get('ignore', ()))


# ---------------------------------------------------------------- replay (engine)

def replay(texts, sess, d, env):
    """{(head, j): dict(slot, form, key, labels, sigs, types, nrows, no_table)} of the relation tables of the texts replayed. A table that does not parse (past the work cap) gets no_table 1,
    key None and no rows. env: dict(D, live, sampler, col_sigs)."""
    D, live = env['D'], env['live']
    run = D.Run(env['sampler'].pri, sess, 0, time.monotonic() + 60, d, live.Limits())
    run.collect = []
    dec, pg = run.scope(texts)
    out = {}
    for i, ct in enumerate(run.collect):
        for s, j in D.relation_tables(ct):
            nm = pg.names.get('&r%d' % s, '&r%d' % s)
            h, _, sub = nm.partition('.')
            k = (pg.written.get(h, h), int(sub) if sub else None)
            try:
                tb = D.S.parse_table(D.OneTable(ct, j))
            except Exception:  # noqa: BLE001  a table past the work cap, as gold_keys counts it
                out[k] = dict(slot=s, form=i, key=None, labels=[], sigs=[], types=[], nrows=[], no_table=1)
                continue
            out[k] = dict(slot=s, form=i, key=D.table_key(tb)[0], labels=list(tb['labels']), sigs=env['col_sigs'](tb), types=[str(t) for t in tb['types']],
                          nrows=[len(e[2]) for e in tb['entries']], no_table=0)
    return out


def drawn_state(dr, pg, kind_tok_is_lib=LIB_KINDS):
    """(derived [[head, j]] sorted set, builtin flag, derived count, builtin count) of the tokens of dr.p_key. dr: a Drawer at an atom start."""
    V, KIND = dr.V, dr.fr.KIND
    der, nd, nb = set(), 0, 0
    for t in dr.p_key:
        try:
            k = KIND[t]
        except (IndexError, KeyError, TypeError):
            continue
        if k == 'relation':
            name = V.name(t)
            if re.fullmatch(r'&r\d+', name or ''):
                nm = dr.prog_names.get(name, name)
                h, _, sub = nm.partition('.')
                der.add((pg.written.get(h, h), int(sub) if sub.isdigit() else (sub or None)))
                nd += 1
        elif k in kind_tok_is_lib:
            nb += 1
    return sorted([list(b) for b in der], key=lambda b: (b[0], -1 if b[1] is None else b[1])), nb > 0, nd, nb


# ---------------------------------------------------------------- checks of the facts

def check_not_index(rows):
    """rows: [(k, {fact name: value})] with k the atom index. Fails if a fact equals k on any row set with 2 or more values of k, or is a function of k's inverse (each of its values
    occurs with one k only, and it takes 2 or more values). Gives the list of offending names."""
    bad = []
    names = set()
    for _, f in rows:
        names |= set(f)
    ks = {k for k, _ in rows}
    if len(ks) < 2:
        return bad
    for n in sorted(names):
        vals = [(k, f.get(n, 0.0)) for k, f in rows]
        if all(abs(v - k) < 1e-9 for k, v in vals):
            bad.append((n, 'equals k'))
            continue
        by = collections.defaultdict(set)
        for k, v in vals:
            by[v].add(k)
        if len(by) >= 2 and all(len(s) == 1 for s in by.values()):
            bad.append((n, 'determines k'))
    return bad


def _toy():
    texts = ['(DET &f10 A)', '(DET &f12 B)', '(RULE &f15 (input (:P *P)) (&f10 (:C P)))', '(RULE &f20 (input (:P *P)) (&f15 (:C P)) (&f12 (:D P)))', '(INIT &f30 X (cell ((:P P)) (&f20 (:C P))))']
    mk = lambda key, types, nr, labels=('',): dict(key=key, types=types, nrows=nr, labels=list(labels), no_table=0)  # noqa: E731
    rels = {('&f10', None): mk('k10', ['Color'], [1, 1]), ('&f12', None): mk('k12', ['Color'], [1, 1]), ('&f15', None): mk('k15', ['Position', 'Color'], [5, 7], ['P', 'C']),
            ('&f20', None): mk('k20', ['Position', 'Color', 'Color'], [5, 0], ['P', 'C', 'D']), ('&f30', None): mk('k30', ['Position'], [3, 3]), ('&f30', 0): mk('k30s', ['Position'], [3, 3])}
    return texts, rels


def renumber(texts, rels, mp):
    sub = lambda s: re.sub(r'&f(\d+)', lambda m: '&f%d' % mp[int(m.group(1))], s)  # noqa: E731
    return [sub(t) for t in texts], {(sub(h), j): v for (h, j), v in rels.items()}, sub


def selftest():
    import itertools
    import random
    texts, rels = _toy()
    sc = Scope(texts, rels)
    bases = [list(b) for b in rels]
    st = dict(hk='RULE', pl='RULE', ph='root', sty=['Color', 'Position'], dd=[['&f10', None], ['&f15', None]], bd=True)
    ref = option_facts(sc, st, bases)
    gref = gate_facts(sc, st, len(bases))
    # a set: the order of the drawn list, of the scope texts and of the options does not matter
    for _ in range(20):
        random.shuffle(texts)
        sc2 = Scope(texts, dict(random.sample(list(rels.items()), len(rels))))
        st2 = dict(st, dd=random.sample(st['dd'], len(st['dd'])), sty=random.sample(st['sty'], len(st['sty'])))
        perm = random.sample(range(len(bases)), len(bases))
        got = option_facts(sc2, st2, [bases[i] for i in perm])
        assert all(got[n] == ref[i] for n, i in enumerate(perm)), 'the facts depend on an order'
        assert gate_facts(sc2, st2, len(bases)) == gref
    # renumbering by a map that keeps the order of the fids
    mp = {10: 3, 12: 40, 15: 41, 20: 99, 30: 100}
    t3, r3, sub = renumber(texts, rels, mp)
    sc3 = Scope(t3, r3)
    st3 = dict(st, dd=[[sub(h), j] for h, j in st['dd']])
    got = option_facts(sc3, st3, [[sub(h), j] for h, j in bases])
    assert got == ref, 'the facts change when the fids are renumbered'
    # a renumbering that changes the order must change the recency ranks (the fact reads the order and nothing else)
    t4, r4_, sub4 = renumber(texts, rels, {10: 100, 12: 41, 15: 40, 20: 3, 30: 2})
    got4 = option_facts(Scope(t4, r4_), dict(st, dd=[[sub4(h), j] for h, j in st['dd']]), [[sub4(h), j] for h, j in bases])
    assert got4 != ref
    # not the atom index: a fact must not equal it or determine it, over all the draws of a toy body
    rows = []
    allb = [b for b in bases]
    for k in range(1, 6):
        for dd in itertools.chain.from_iterable(itertools.combinations(allb, m) for m in range(0, min(k, 3))):
            for bd in (False, True):
                if len(dd) + int(bd) > k - 1:
                    continue
                stx = dict(st, dd=[list(b) for b in dd], bd=bd)
                nD = len(allb)
                for f in option_facts(sc, stx, allb) + [gate_facts(sc, stx, nD)]:
                    rows.append((k, f))
    bad = check_not_index(rows)
    assert not bad, bad
    # the check catches an index
    assert check_not_index([(k, {'idx': float(k)}) for k in (1, 2, 3)]) and check_not_index([(k, {'f': 2.0 * k}) for k in (1, 2, 3)])
    # every raw name is a known column
    known = set(all_option_names())
    for f in ref:
        for k in f:
            assert k in known or k.startswith('ct:'), k
    for k in gref:
        assert k in set(all_gate_names()), k
    std = Std(Std.column_names(all_option_names(), ['Color']), [0.0] * (len(known) + 2), [1.0] * (len(known) + 2), ['Color'])
    M = std.matrix(ref)
    assert M.shape == (len(ref), len(known) + 2)
    print('feats selftest ok: set order, renumbering, order-sensitive recency, not the atom index (%d toy rows), names' % len(rows))


if __name__ == '__main__':
    selftest()
