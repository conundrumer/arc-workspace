#!/usr/bin/env python
"""Find at the pick (item 19): a tilt on the pick of a derived relation, on real visit contexts, in random valid order, with junk options and no reader columns. A firm row of the pool scope refit.

  features_dagc_env.sh 1 features_dagc_find.py fit  [--seconds S] [--no-final]       fit on fit-pool (off walks), tune gamma on the fit-pool test tasks, then refit on all fit-pool rows; writes find-model.json, find-tune.json
  features_dagc_env.sh 1 features_dagc_find.py read --part held-wide|held-pool [--final] [--seconds S]     the held read of the frozen model: saved bits per form under the tilt on live weights (primary) and on off weights, controls, table recall
  features_dagc_env.sh 1 features_dagc_find.py pilot [--seconds S]            a mechanical read on the fit-pool test tasks of a model fit on the fit-pool train tasks. Not a held read, and its numbers are not a result

The model. Candidates of a pick are the derived options that the walk offers there, the visit's junk forms among them. The label is gold's option, at the picks where gold's relation is derived. A conditional logit with weight on three keys,
each crossed with the target's kind and a d_depth band (arm `holeb` of candidate_model.py, with no reader column and no output key):
  fitl   whether the known types of the hole fit in the candidate's column types, as multisets: `all`, `part`, `none`, or `unknown` where there are none. The hole's known types, `want`, are the types of the labels that have one site in D:
         lib atoms from sig_table of backward_edges.py, derived atoms from the types of their option in `rowopts`. A derived atom has no column names in `rowopts`, so its labels take the option's types by position, where the count of
         labelled sites equals the count of types (and the option is the only one of its form, or the only one with that many types); else they stay untyped. `want` reads D alone: a search has it at the pick.
  arity  the candidate's column count less the count of `want`: `<0`, 0, 1, 2, 3+
  ckind  the kind of the candidate's form
The tilt. Each derived option's weight is multiplied by lift^gamma, the weights inside the derived options are renormalized, so the share of derived against lib options stays; a pick whose gold is not derived saves 0.
Gamma is from .4 .6 .8 1.0 1.25 1.5 and is tuned on the fit-pool test tasks (mean saved per form, off weights). The logit reads facts alone. The primary number acts on live weights, the second on off weights.
Weights: a pick weighs its walks over the point's finished walks, so a form weighs what one order weighs; a form's saving is the sum over its picks of weight times saving, the mean over its orders.
Measures: saved bits per form, 95% by task, at 25 bits or more by bits_mean under live (form-bits-dag.tsv) and on all forms, by kind. A kind with under 8 tasks at 25 bits or more is thin. Table recall for non-DET forms through the fitted proposal cost
of features_holding_reader_cover.py of features-search-holding-reader-with-hole-design (hazard 2^-(a + s b), 4522 proposals), as an estimate: its fit is for the census text at 600 s, it overstates DET by about 10, and INIT's slope is .12.
Controls: a fit on labels drawn uniformly among the candidates must read 0. Bars: under .5 bits per form at 25 bits or more closes the row, 2 bits sends it to a steer, between the two it stands as a finding.
held-pool has a median form of 16 bits, so held-wide carries the bars. held-wide is an oracle context (measures.md): gold's parents and the forms of one late visit.
"""
import argparse
import collections
import json
import math
import os
import sys
import time

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backward_edges as E  # noqa: E402
import features_dag_order as D  # noqa: E402
import features_dagc_rows as RW  # noqa: E402

ME = RW.ME
LN2 = math.log(2)
GAMMAS = (.4, .6, .8, 1.0, 1.25, 1.5)
L2 = 1e-4
KEYS = ('fitl', 'arity', 'ckind')
KINDS = ('RULE', 'DET', 'INIT')
BAR = 25.0
# the proposal cost of features_holding_reader_cover.py: hazard per proposal 2^-(a + s * bits), a and s by kind
FIT = {'RULE': (11.3, .30), 'DET': (6.0, .50), 'INIT': (11.9, .12)}
COST12 = {'RULE': 15.0, 'DET': 12.0, 'INIT': 13.4}
STEEP = {'RULE': .78, 'DET': .78, 'INIT': .26}
PROPOSALS = 4522  # the median of a 600 s run


# ---- the candidates of a pick ----

def scope_info(scope):
    cp = D.ProgramDag(list(scope))
    name_ck = {k: cp.content[k] for k in cp.lines}
    ck_kind = {}
    for k in cp.lines:
        ck_kind.setdefault(cp.content[k], cp.kinds[k])
    return name_ck, ck_kind


def fit_of(want, have):
    """Whether the known types of a hole fit in the candidate's column types, as multisets."""
    w = collections.Counter(t for t in want if t not in ('?', 'none'))
    if not w:
        return 'unknown'
    h = collections.Counter(E.norm_type(t) for t in have)
    miss = sum((w - h).values())
    return 'all' if miss == 0 else 'part' if miss < sum(w.values()) else 'none'


def want_types(downset, by_ck, name_ck):
    """The known types of the labels that have one site in D."""
    sites, typ = collections.Counter(), {}
    for x in downset:
        tree = E.parse(x.split('|', 1)[1])
        if tree and tree[0] == 'NOT' and len(tree) > 1 and isinstance(tree[1], list):
            tree = tree[1]
        if not tree or not isinstance(tree[0], str) or tree[0] in E.CMP or tree[0] == 'NOT':
            continue
        head = tree[0]
        ss = E.sites_of(tree[1:])
        for s in ss:
            if s[1] is not None:
                sites[s[1]] += 1
        if head.startswith('&'):
            ck = name_ck.get(head.partition('.')[0])
            opts = by_ck.get(ck, [])
            labelled = [s for s in ss if s[1] is not None]
            use = None
            if len(opts) == 1:
                use = opts[0]
            else:
                same = [t for t in opts if len(t) == len(labelled)]
                if len(same) == 1:
                    use = same[0]
            if use is not None and len(use) == len(labelled):
                for s, t in zip(labelled, use):
                    typ.setdefault(s[1], E.norm_type(t))
        else:
            for s in ss:
                if s[1] is not None:
                    t = E.col_type(dict(name=head), s)
                    if t:
                        typ.setdefault(s[1], E.norm_type(t))
    return [typ[l] for l, c in sites.items() if c == 1 and l in typ]


class Compactor:
    """The pick of the find: gold derived, with the derived options as candidates. Returns None for any other pick."""

    def __init__(self, points_path):
        self.pts = {}
        for x in open(points_path):
            p = json.loads(x)
            self.pts[p['line']] = p
        self.sc = {}

    def __call__(self, d, point):
        g = d['gold_idx']
        if g is None or d['opts'][g][1] != 'relation':
            return None
        p = self.pts[point]
        if point not in self.sc:
            if len(self.sc) > 200:
                self.sc.clear()
            self.sc[point] = scope_info(p['scope'])
        name_ck, ck_kind = self.sc[point]
        di = [i for i, o in enumerate(d['opts']) if o[1] == 'relation']
        ro = d['rowopts']
        types = [list(ro[i].get('types') or []) for i in di]
        by_ck = collections.defaultdict(list)
        for i, t in zip(di, types):
            by_ck[d['opts'][i][0][2:].partition('.')[0]].append(t)
        want = want_types(d['downset'], by_ck, name_ck)
        fitl, arity, ckind = [], [], []
        for i, t in zip(di, types):
            fitl.append(fit_of(want, t))
            a = len(t) - len(want)
            arity.append('<0' if a < 0 else str(min(a, 3)))
            ckind.append(ck_kind.get(d['opts'][i][0][2:].partition('.')[0], 'unknown'))
        c = RW.conj_size(d)
        return dict(point=point, task=d['task'], line_id=d['line_id'], kind=d['kind'], scope_id=d['scope_id'], band=RW.band_of(d['d_depth'], c), g=di.index(g), w=[d['opts'][i][2] for i in di], fitl=fitl, arity=arity, ckind=ckind, nwant=len(want), key=RW.key_of(d))


# ---- the conditional logit ----

class Set:
    """Picks with their candidates, and the key index of each candidate."""

    def __init__(self, entries, nok, vocab=None, grow=True, control_seed=None):
        self.entries = entries
        self.n = len(entries)
        rng = np.random.RandomState(control_seed) if control_seed is not None else None
        starts, y, pw, strs = [0], [], [], []
        for e in entries:
            m = len(e['w'])
            for j in range(m):
                strs.append(tuple('%s=%s|%s|%s' % (k, e['kind'], e['band'], e[k][j]) for k in KEYS))
            starts.append(starts[-1] + m)
            y.append(int(rng.randint(m)) if rng is not None else e['g'])
            pw.append(e['cnt'] / max(nok[e['point']], 1))
        self.start, self.y, self.pw = np.array(starts), np.array(y), np.array(pw)
        self.seg = np.repeat(np.arange(self.n), np.diff(self.start))
        self.task = np.array([e['task'] for e in entries])
        self.vocab = {} if vocab is None else vocab
        X = np.zeros((len(strs), len(KEYS)), np.int64)
        for i, row in enumerate(strs):
            for j, k in enumerate(row):
                g = self.vocab.get(k)
                if g is None:
                    if grow:
                        g = self.vocab[k] = len(self.vocab)
                    else:
                        g = -1
                X[i, j] = g
        self.X = X


def seg_softmax(z, start, n):
    mx = np.maximum.reduceat(z, start[:-1])
    ez = np.exp(z - np.repeat(mx, np.diff(start)))
    s = np.add.reduceat(ez, start[:-1])
    return z - np.repeat(mx, np.diff(start)) - np.repeat(np.log(s), np.diff(start)), ez / np.repeat(s, np.diff(start))


def fit_logit(S, nv, keep, l2=L2):
    """Weights by L-BFGS on the picks in keep, each pick weighing pw."""
    idx = np.nonzero(keep)[0]
    cand = np.concatenate([np.arange(S.start[i], S.start[i + 1]) for i in idx])
    counts = np.diff(S.start)[idx]
    st = np.concatenate([[0], np.cumsum(counts)])
    X = S.X[cand]
    ok = X >= 0
    w = S.pw[idx]
    gold = st[:-1] + S.y[idx]
    seg = np.repeat(np.arange(len(idx)), counts)
    W = w.sum()

    def f(th):
        z = (th[np.maximum(X, 0)] * ok).sum(1)
        lp, p = seg_softmax(z, st, len(idx))
        loss = -(w * lp[gold]).sum() / W + l2 * (th ** 2).sum()
        g = np.zeros(nv)
        pw_ = p * w[seg]
        for j in range(X.shape[1]):
            g += np.bincount(X[ok[:, j], j], pw_[ok[:, j]], nv)
            g -= np.bincount(X[gold, j][ok[gold, j]], w, nv) if len(gold) else 0
        return loss, g / W + 2 * l2 * th
    return minimize(f, np.zeros(nv), jac=True, method='L-BFGS-B', options=dict(maxiter=80)).x


def scores(S, th):
    return (th[np.maximum(S.X, 0)] * (S.X >= 0)).sum(1)


def pick_saved(z, wc, g, gamma):
    """Bits saved at one pick by the tilt inside the derived options: the weights are multiplied by exp(gamma z) and renormalized inside them."""
    z = z - z.max()
    den = float((wc * np.exp(gamma * z)).sum() / wc.sum())
    return (gamma * z[g] - math.log(den)) / LN2


def form_savings(S, th, gamma, weights_of):
    """{point: sum over the picks of weight * saving} where weights_of(entry) gives the derived options' weights under a steer."""
    z = scores(S, th)
    out = collections.defaultdict(float)
    for i, e in enumerate(S.entries):
        wc = weights_of(e)
        if wc is None:
            continue
        out[e['point']] += S.pw[i] * pick_saved(z[S.start[i]:S.start[i + 1]], np.asarray(wc, float), e['g'], gamma)
    return out


def forms_of(T):
    """One row per point with a finished walk: its task, line, kind and mean bits."""
    acc = collections.defaultdict(list)
    meta = {}
    for w in T.walks:
        if w['ok'] and w['total'] is not None:
            acc[w['point']].append(w['total'])
            meta[w['point']] = w
    return {pt: dict(point=pt, task=meta[pt]['task'], line_id=meta[pt]['line_id'], scope_id=meta[pt]['scope_id'], kind=meta[pt]['kind'], bits=sum(v) / len(v)) for pt, v in acc.items()}


def summarize(forms, sav, cut_bits):
    """Rows of saved bits per form: all forms, and forms at 25 bits or more by cut_bits[(task, line_id, scope_id)] (the live bits_mean), by kind."""
    rows = []
    for f in forms.values():
        b = cut_bits.get((f['task'], f['line_id'], f['scope_id']))
        rows.append((f['task'], f['kind'], b, sav.get(f['point'], 0.0), f['bits']))
    task = np.array([r[0] for r in rows])
    kind = np.array([r[1] for r in rows])
    cut = np.array([(r[2] if r[2] is not None else np.nan) for r in rows], float)
    s = np.array([r[3] for r in rows])
    one = np.ones(len(rows))
    out = {}
    groups = [('all forms', np.ones(len(rows), bool)), ('25 bits or more', cut >= BAR), ('under 25 bits', cut < BAR)]
    groups += [('%s, 25 bits or more' % k, (kind == k) & (cut >= BAR)) for k in KINDS] + [('%s, all forms' % k, kind == k) for k in KINDS]
    for nm, m in groups:
        if not m.any():
            continue
        t = len(set(task[m].tolist()))
        out[nm] = dict(forms=int(m.sum()), tasks=t, thin=bool(t < 8), saved=[round(x, 3) for x in RW.boot(s, one, task, m)], mean_bits=round(float(np.nanmean(cut[m])), 2), no_live_bits=int(np.isnan(cut[m]).sum()))
    return out, rows


def recall(rows, savings=None, steep=False):
    """Expected forms covered at PROPOSALS proposals, non-DET and DET, with the form's bits lowered by its saving (features_holding_reader_cover.recall with lam 0 and M 1)."""
    g = collections.Counter()
    for task, kind, cutb, x, bits in rows:
        a, s = FIT[kind]
        if steep:
            s, a = STEEP[kind], COST12[kind] - STEEP[kind] * 12
        b = bits if cutb is None else cutb
        bb = b - (x if savings else 0.0)
        g['DET' if kind == 'DET' else 'nonDET'] += 1 - math.exp(-PROPOSALS * 2 ** -(a + s * bb))
    return round(g['nonDET'], 1), round(g['DET'], 1)


# ---- commands ----

def load_part(part, steers, seconds, points, tasks=None):
    comp = Compactor(ME + points)
    T = RW.load(part, steers, kinds=KINDS, seconds=seconds, tasks=tasks, tag='find', compactor=comp)
    entries = list(T.entries.values())
    return T, entries


def task_sets():
    tr = {json.loads(x)['task'] for x in open(ME + 'points-fit-pool-train-0of1.jsonl')}
    te = {json.loads(x)['task'] for x in open(ME + 'points-fit-pool-test-0of1.jsonl')}
    assert not (tr | te) & RW.HELD
    return tr, te


def cmd_fit(a):
    t0 = time.time()
    tr, te = task_sets()
    T, entries = load_part('fit-pool', 'off', a.seconds, 'points-fit-pool.jsonl')
    print('fit-pool off: %d candidate picks (gold derived), %d points with walks, %d walks; %.0fs; files %s' % (len(entries), len(T.nok), sum(T.nok.values()), time.time() - t0, T.files), flush=True)
    train = [e for e in entries if e['task'] in tr]
    test = [e for e in entries if e['task'] in te]
    S = Set(entries, T.nok)
    nv = len(S.vocab)
    is_tr = np.array([e['task'] in tr for e in entries])
    is_te = np.array([e['task'] in te for e in entries])
    th = fit_logit(S, nv, is_tr)
    forms = {pt: f for pt, f in forms_of(T).items() if f['task'] in te}
    curve = {}
    for g in GAMMAS:
        sav = form_savings(S, th, g, lambda e: e['w'] if e['task'] in te else None)
        curve[str(g)] = round(float(np.mean([sav.get(pt, 0.0) for pt in forms])), 4) if forms else None
    best = max(GAMMAS, key=lambda g: curve[str(g)] if curve[str(g)] is not None else -1e9)
    z = scores(S, th)
    gold_rank = []
    bits = []
    for i in np.nonzero(is_te)[0]:
        zz = z[S.start[i]:S.start[i + 1]]
        lp, _ = seg_softmax(zz, np.array([0, len(zz)]), 1)
        bits.append(-lp[S.y[i]] / LN2)
        gold_rank.append(int((zz > zz[S.y[i]]).sum()))
    which = dict(uniform=round(float(np.mean([math.log2(len(e['w'])) for e in test])), 3) if test else None, model=round(float(np.mean(bits)), 3) if bits else None, top1=round(float(np.mean([r == 0 for r in gold_rank])), 3) if gold_rank else None)
    print('tune: curve %s best gamma %s; which candidate on the test picks: %s; %.0fs' % (curve, best, which, time.time() - t0), flush=True)
    json.dump(dict(curve=curve, gamma=best, test_forms=len(forms), test_picks=len(test), train_picks=len(train), train_tasks=len({e['task'] for e in train}), test_tasks=len({e['task'] for e in test}), which_candidate_test=which, files=T.files, l2=L2), open(ME + 'find-tune.json', 'w'), indent=1)
    vocab = S.vocab
    if a.no_final:
        final = th
        cth = fit_logit(Set(entries, T.nok, vocab=dict(vocab), grow=False, control_seed=11), nv, is_tr)
    else:
        final = fit_logit(S, nv, np.ones(len(entries), bool))
        cth = fit_logit(Set(entries, T.nok, vocab=dict(vocab), grow=False, control_seed=11), nv, np.ones(len(entries), bool))
    inv = {v: k for k, v in vocab.items()}
    model = dict(gamma=best, l2=L2, final_fit_on=('train tasks only (pilot)' if a.no_final else 'all fit-pool rows'), vocab=vocab, weights=[round(float(x), 5) for x in final], control_weights=[round(float(x), 5) for x in cth], keys=KEYS, files=T.files, picks=len(entries))
    json.dump(model, open(ME + 'find-model%s.json' % ('-pilot' if a.no_final else ''), 'w'), indent=1)
    top = sorted(((abs(final[i]), inv[i], round(float(final[i]), 2)) for i in range(nv)), reverse=True)[:12]
    print('model: %d keys, top weights %s; written; %.0fs' % (nv, [(k, v) for _, k, v in top], time.time() - t0), flush=True)


def read_model(path):
    m = json.load(open(path))
    return m['vocab'], np.array(m['weights']), np.array(m['control_weights']), m['gamma']


def read_on(entries, T, vocab, th, cth, gamma, weights_of, cut_bits):
    S = Set(entries, T.nok, vocab=dict(vocab), grow=False)
    forms = forms_of(T)
    res = {}
    for name, w_ in (('model', th), ('control', cth)):
        sav = form_savings(S, w_, gamma, weights_of)
        summ, rows = summarize(forms, sav, cut_bits)
        res[name] = dict(summary=summ, recall_base=recall(rows), recall_tilt=recall(rows, True), recall_base_steep=recall(rows, steep=True), recall_tilt_steep=recall(rows, True, True))
    z = scores(S, th)
    unseen = float((S.X < 0).any(axis=1).mean()) if len(S.X) else 0.0
    res['unseen_key_share'] = round(unseen, 4)
    res['picks'] = len(entries)
    res['forms'] = len(forms)
    return res


def cmd_read(a):
    t0 = time.time()
    part = a.part
    if part.startswith('held') and a.model != 'find-model.json':
        sys.exit('a held part is read with the frozen find-model.json alone')
    path = ME + 'find-read-%s.json' % part
    if a.final and os.path.exists(path) and json.load(open(path)).get('final'):
        sys.exit('%s holds the final read: this held read is done' % path)
    vocab, th, cth, gamma = read_model(ME + a.model)
    points = 'points-%s.jsonl' % part
    out = dict(part=part, gamma=gamma, final=bool(a.final), note='held-wide is an oracle context (gold parents plus the forms of one late visit)' if part == 'held-wide' else '')
    cut = RW.form_bits('live', part)
    T_off, ent_off = load_part(part, 'off', a.seconds, points)
    T_live, ent_live = load_part(part, 'live', a.seconds, points)
    print('%s: off %d candidate picks, live %d; %.0fs' % (part, len(ent_off), len(ent_live), time.time() - t0), flush=True)
    out['files'] = dict(off=T_off.files, live=T_live.files)
    # primary: live weights, on the picks that both steers reach (the same pick keys), the forms of the live walks
    out['live'] = read_on(ent_live, T_live, vocab, th, cth, gamma, lambda e: e['w'], cut)
    out['off'] = read_on(ent_off, T_off, vocab, th, cth, gamma, lambda e: e['w'], cut)
    forms_tbl = collections.Counter()
    for f in forms_of(T_live).values():
        b = cut.get((f['task'], f['line_id'], f['scope_id']))
        if b is not None and b >= BAR:
            forms_tbl[f['kind']] += 1
    out['forms_25_by_kind'] = dict(forms_tbl)
    json.dump(out, open(path, 'w'), indent=1)
    if a.final:
        with open(ME + 'held-reads.jsonl', 'a') as f:
            for steers in ('live', 'off'):
                f.write(json.dumps(dict(name='find-held_read-%s' % part, group='find at the pick', arm='holeb', tier='tilt', steers=steers, control=False, time=time.strftime('%Y-%m-%dT%H:%M:%S'))) + '\n')
            f.write(json.dumps(dict(name='find-held_control-%s' % part, group='find at the pick', arm='holeb', tier='tilt', steers='live', control=True, time=time.strftime('%Y-%m-%dT%H:%M:%S'))) + '\n')
    print(write_md(out))


def write_md(o):
    L_ = ['# Find at the pick, %s, gamma %s' % (o['part'], o['gamma']), '', o.get('note', ''), '', 'Bars: under .5 bits per form at 25 bits or more closes the row; 2 bits sends it to a steer. Forms at 25 bits or more by kind (live bits_mean): %s. Walk files: %s.' % (o.get('forms_25_by_kind'), json.dumps(o.get('files'))), '']
    for steers in ('live', 'off'):
        r = o[steers]
        L_ += ['## Tilt on %s weights' % steers, '', '%d candidate picks (gold derived), %d forms; share of candidates with a key the fit never saw %.3f.' % (r['picks'], r['forms'], r['unseen_key_share']), '']
        rows = []
        for nm in r['model']['summary']:
            m, c = r['model']['summary'][nm], r['control']['summary'].get(nm)
            rows.append([nm, m['forms'], m['tasks'], 'thin' if m['thin'] else '', m['mean_bits'], RW.fmt3(m['saved']), RW.fmt3(c['saved']) if c else ''])
        L_.append(RW.table_md(['Forms', 'Count', 'Tasks', '', 'Mean live bits', 'Saved bits per form, model', 'Control'], rows))
        L_.append('Expected non-DET and DET forms covered at 4522 proposals (fitted cost, as an estimate; its fit is for the census text at 600 s and is over by about 10 on DET): base %s, tilt %s; on the steeper slopes base %s, tilt %s.' % (r['model']['recall_base'], r['model']['recall_tilt'], r['model']['recall_base_steep'], r['model']['recall_tilt_steep']))
        L_.append('')
    return '\n'.join(L_) + '\n'


def cmd_pilot(a):
    """A model fit on the fit-pool train tasks, read on the fit-pool test tasks (non-held). Mechanical: shows that the read runs and what the pieces return."""
    t0 = time.time()
    tr, te = task_sets()
    pm = ME + 'find-model-pilot.json'
    if not os.path.exists(pm):
        sys.exit('run `fit --no-final` first')
    vocab, th, cth, gamma = read_model(pm)
    T, ent = load_part('fit-pool', 'off', a.seconds, 'points-fit-pool.jsonl', tasks=te)
    T_all, _ = None, None
    cut = {}
    for f in forms_of(T).values():
        cut[f['task'], f['line_id'], f['scope_id']] = f['bits']
    r = read_on(ent, T, vocab, th, cth, gamma, lambda e: e['w'], cut)
    out = dict(part='fit-pool test tasks (pilot)', gamma=gamma, files=T.files, off=r, live=r, forms_25_by_kind={}, final=False, note='PILOT: model fit on the fit-pool train tasks, read on the fit-pool test tasks with off bits for the 25 cut. Not a held read.')
    json.dump(out, open(ME + 'find-read-pilot.json', 'w'), indent=1)
    print(write_md(out).split('## Tilt on off')[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['fit', 'read', 'pilot'])
    ap.add_argument('--part', default='held-wide')
    ap.add_argument('--seconds', type=float, default=22)
    ap.add_argument('--final', action='store_true')
    ap.add_argument('--model', default='find-model.json', help='read: the model file. A non-held part (dev-cut) with the pilot model runs the read mechanically')
    ap.add_argument('--no-final', action='store_true', help='fit: skip the refit on all fit-pool rows; the model stays the train-task fit (pilot)')
    a = ap.parse_args()
    dict(fit=cmd_fit, read=cmd_read, pilot=cmd_pilot)[a.cmd](a)


if __name__ == '__main__':
    main()
