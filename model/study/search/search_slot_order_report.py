#!/usr/bin/env python3
"""Reproduces the numbers of slot-order-read.md: would next_slot gain from resuming parked slots by score, or by score times rate, in place of by rate?

Reads saved records only, in one process and one thread, in about 6 minutes on a Mac. Writes under cache/ beside this file.

  OMP_NUM_THREADS=1 work/lm/.venv/bin/python search_slot_order_report.py [cache shares tape hazard hazard2 bias replays paired tables flow mech]

With no step named, all steps run in that order. A step reads the cache that the steps before it wrote.

Records: 37 held-out tasks (held/tasks.txt), 600 s wall, worker path. Arms cover_s0, cover_s1, base_s0, base_s1 of sampler-pool-extended-text-pass1-600s/out-all37, and ext_s0, ext_s1, extk_s0, extk_s1 of
sampler-pool-refit-ext-ramp-600s. Files: .visits, .cover, .bank (the policy's scores, forms, parents, births), .bank.slots.
"""
import collections
import glob
import hashlib
import json
import math
import os
import pickle
import random
import re
import sys
import time
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'
pd.set_option('display.width', 220, 'display.max_columns', 30, 'display.max_colwidth', 40)


class Stub:
    def __init__(self, *a, **k):
        pass

    def __setstate__(self, s):
        if isinstance(s, dict):
            self.__dict__.update(s)
        elif isinstance(s, tuple):
            for x in s:
                if isinstance(x, dict):
                    self.__dict__.update(x)


class U(pickle.Unpickler):
    """Bank files name classes of the kit. A stub stands in for each of them."""

    def find_class(self, m, n):
        if m.split('.')[0] in ('builtins', 'numpy', 'collections', 'copyreg'):
            try:
                return super().find_class(m, n)
            except Exception:  # noqa: BLE001
                pass
        return type(n, (Stub,), {})


def read_bank(path):
    return U(open(path, 'rb')).load()


NAME = re.compile(r'&[A-Za-z_]\w*')
A1 = W + 'sampler-pool-extended-text-pass1-600s/out-all37/'
A2 = W + 'sampler-pool-refit-ext-ramp-600s/out/'
K1 = W + 'kits/sampler-pool-extended-text-pass1-8be414670/'
RUNS = {'cover_s0': (A1, K1 + 'points-eval.json'), 'cover_s1': (A1, K1 + 'points-eval.json'), 'base_s0': (A1, K1 + 'points-eval.json'), 'base_s1': (A1, K1 + 'points-eval.json'),
        'ext_s0': (A2, W + 'sampler-extended-cut/points-with-ramp.json'), 'ext_s1': (A2, W + 'sampler-extended-cut/points-with-ramp.json'),
        'extk_s0': (A2, W + 'sampler-extended-cut/points-with-ramp.json'), 'extk_s1': (A2, W + 'sampler-extended-cut/points-with-ramp.json')}
tasks = open(W + 'held/tasks.txt').read().split()


def gold_forms(sexp):
    """[(kind, depth, reads)] by gold index, in the order of gold_keys: the lines that are no OUT."""
    lines = [str(f) for f in sexp.strip().split('\n') if not f.startswith('(OUT')]
    heads = [NAME.findall(x)[0] for x in lines]
    depth, reads, out = {}, {}, []
    for h, x in zip(heads, lines):
        reads[h] = {m for m in NAME.findall(x) if m in depth and m != h}
        depth[h] = 1 + max((depth[r] for r in reads[h]), default=0)
        out.append((x[1:].split(' ', 1)[0], depth[h], len(reads[h])))
    return out


def one(root, arm, t, gold):
    d = '%s%s/%s' % (root, arm, t)
    work = d + '/work/'
    start = float(open(d + '/start').read())
    st = read_bank(glob.glob(work + '*.out.jsonl.bank')[0])
    vs = []
    for l in open(glob.glob(work + '*.visits')[0]):
        try:
            vs.append(json.loads(l))
        except ValueError:
            pass
    vs.sort(key=lambda v: v['time'])
    covers, seen = [], set()
    for l in open(glob.glob(work + '*.out.jsonl.cover')[0]):
        try:
            c = json.loads(l)
        except ValueError:
            continue
        covers.append((c['gold'], c['draw'], c['time'] - start, c['depth']))
    pol = st['policy']
    forms = {}
    for f, x in st['forms'].items():
        ss = [pol['score'][n] for n in x.nodes if n in pol['score']]
        birth = min((st['nodes'][n].age for n in x.nodes), default=None)
        forms[f] = dict(kind=x.kind, depth=x.depth, parents=list(x.parents), score=max(ss) if ss else None, birth=birth, text=x.text[:80])
    nclauses = {n: st['nodes'][n].n_clauses for n in st['nodes']}
    vout = []
    last = start
    cum = 0
    for v in vs:
        vout.append(dict(fids=tuple(v['fids']), kind=v['kind'], resume=v['resume'], tries=v['tries'], new=v['new'], t0=last - start, t1=v['time'] - start, d0=cum, d1=cum + v['tries'], cum_seconds=v['seconds']))
        last = v['time']
        cum += v['tries']
    return dict(task=t, arm=arm, visits=vout, covers=covers, forms=forms, draws=st['draws'], generation=st['generation'], gold=gold, nclauses=nclauses,
                slots=json.load(open(glob.glob(work + '*.bank.slots')[0])), lives=open(d + '/supervisor.log').read().count('exited'))


def fold_check():
    b = U(open(K1 + 'policy/policy_model.pkl', 'rb')).load()
    out = {}
    for t in tasks:
        task = json.load(open(glob.glob('%scover_s0/%s/work/*.task.json' % (A1, t))[0]))
        key = hashlib.sha1(json.dumps(task['train'], sort_keys=True).encode()).hexdigest()
        out[t] = [key not in trained for trained, _ in b['folds']]
    return out



ARMS = ['cover_s0', 'cover_s1', 'base_s0', 'base_s1', 'ext_s0', 'ext_s1', 'extk_s0', 'extk_s1']


def load(arm):
    return pickle.load(open(HERE + 'cache/%s.pkl' % arm, 'rb'))


def scope_scores(r, fids):
    """(picked mean, max, mean) of the forms' scores. A picked form is one that no other form of the scope reads. Forms past the last bank write have no score and leave out."""
    F = r['forms']
    known = [f for f in fids if f in F and F[f]['score'] is not None]
    if not known:
        return None, None, None
    read = set()
    for f in known:
        read.update(F[f]['parents'])
    top = [f for f in known if f not in read] or known
    s = [F[f]['score'] for f in known]
    return float(np.mean([F[f]['score'] for f in top])), float(max(s)), float(np.mean(s))


def first_covers(r, cut=1e9):
    """{gold: (draw, seconds)} of the first cover."""
    got = {}
    for g, d, t, _ in r['covers']:
        if t <= cut and (g not in got or d < got[g][0]):
            got[g] = d, t
    return got


def visit_of(r):
    """A function from a draw to the index of its visit."""
    d1 = np.array([v['d1'] for v in r['visits']])
    return lambda d: int(np.searchsorted(d1, d, 'left'))


def slot_key(v):
    return v['fids'], v['kind']


def annotate(r):
    """Adds to each visit: slot, nth (visit number of the slot, from 0), rate (new per second), and the slots' tapes."""
    tapes = collections.defaultdict(list)
    exhausted = {(tuple(s[0]), s[1]) for s in r['slots'] if s[8]}
    for i, v in enumerate(r['visits']):
        k = slot_key(v)
        v['slot'], v['i'] = k, i
        v['nth'] = len(tapes[k])
        tapes[k].append(i)
        v['secs'] = max(v['t1'] - v['t0'], 1e-3)
        v['rate'] = v['new'] / v['secs']
        v['score'] = scope_scores(r, v['fids'])
    r['tapes'], r['exhausted'] = dict(tapes), exhausted
    cov = collections.defaultdict(list)
    vo = visit_of(r)
    for g, d, t, _ in r['covers']:
        cov[min(vo(d), len(r['visits']) - 1)].append((g, d, t))
    r['cov_at'] = cov
    return r

BINS = [30, 60, 120, 300, 1e9]


def tbin(t):
    for i, b in enumerate(BINS):
        if t < b:
            return i
    return len(BINS) - 1


def prepare(r, agg=0):
    """Cuts the run at the bank write and builds what a replay reads."""
    annotate(r)
    V = [v for v in r['visits'] if v['d1'] <= r['draws']]
    n = len(V)
    last = V[-1]
    goldv = collections.defaultdict(list)  # gold: [(visit, tries into the visit, seconds into it)]
    for i, c in r['cov_at'].items():
        if i < n:
            for g, d, t in c:
                goldv[g].append((i, d - V[i]['d0'], t - V[i]['t0']))
    vo = visit_of(r)
    birth = {}
    for f, x in r['forms'].items():
        birth[f] = min(vo(x['birth']), n) if x['birth'] is not None else n
    tapes = collections.defaultdict(list)
    for v in V:
        tapes[v['slot']].append(v['i'])
    need = {}
    for v in V:
        if not v['resume']:
            need[v['i']] = sorted({birth[f] for f in v['fids'] if f in birth and birth[f] < v['i']})
    kinds = collections.defaultdict(list)
    for v in V:
        if v['resume']:
            kinds[v['kind']].append((v['tries'], v['secs']))
    allr = [x for k in kinds.values() for x in k] or [(20, 4.0)]
    size = {k: (float(np.median([x[0] for x in w])), float(np.median([x[1] for x in w]))) for k, w in kinds.items()}
    dflt = float(np.median([x[0] for x in allr])), float(np.median([x[1] for x in allr]))
    golds_at = collections.defaultdict(set)
    for g, ev in goldv.items():
        for i, _, _ in ev:
            golds_at[i].add(g)
    # score of a slot, and the median over slots for those with no score
    sc = {}
    for v in V:
        sc.setdefault(v['slot'], v['score'][agg])
    known = [s for s in sc.values() if s is not None]
    med = float(np.median(known)) if known else 0.0
    sc = {k: (med if s is None else s) for k, s in sc.items()}
    return dict(V=V, n=n, goldv=goldv, tapes=tapes, need=need, size=size, dflt=dflt, golds_at=golds_at, score=sc, flags=[v['resume'] for v in V], Q=[v['i'] for v in V if not v['resume']],
                t_end=last['t1'], d_end=last['d1'], exhausted=r['exhausted'], gold=r['gold'], task=r['task'])


class Rule:
    """key(slot rate, slot visits, slot score, rng) gives the value a pick maximizes."""

    def __init__(self, name, beta=None, weights=None):
        self.name, self.beta, self.weights = name, beta, weights or {}

    def key(self, rate, visits, score, rng, kind='RULE'):
        n = self.name
        if n == 'kind':
            w = self.weights.get(kind, 1.0)
            return (math.log(rate) + math.log(w) + (self.beta or 0) * score if w > 0 else -1e9), -visits
        if n == 'rate':
            return rate, -visits
        if n == 'random':
            return rng.random(), 0
        if n == 'score':
            return score, rate
        if n == 'ratexscore':
            return math.log(rate) + self.beta * score, -visits
        if n == 'scoredraw':
            return self.beta * score - math.log(-math.log(rng.random() or 1e-12)), 0
        if n == 'ratedraw':
            return math.log(rate) - math.log(-math.log(rng.random() or 1e-12)), 0
        raise ValueError(n)


def rules():
    out = [('rate', Rule('rate')), ('random', Rule('random')), ('score', Rule('score'))]
    for b in (.0625, .125, .25, .5, 1, 2):
        out.append(('rate x e^(%gs)' % b, Rule('ratexscore', b)))
    for b in (.25, .5, 1, 2):
        out.append(('draw e^(%gs)' % b, Rule('scoredraw', b)))
    out.append(('rate, RIGID_DET 0', Rule('kind', None, dict(RIGID_DET=0))))
    out.append(('rate x kind, INIT 3', Rule('kind', None, dict(RIGID_DET=0, INIT=3))))
    out.append(('rate x kind, INIT 10', Rule('kind', None, dict(RIGID_DET=0, INIT=10))))
    out.append(('rate x kind x e^(.25s), INIT 3', Rule('kind', .25, dict(RIGID_DET=0, INIT=3))))
    return out


def replay(p, rule, mode='T', m=0.0, flags=None, seed=0, hazard=None, rho=.8, window=1, oracle=False, share=None, log=None):
    """Gives (first cover per gold as (tries, seconds), phantom covers by cut, counts). window > 1: a new scope is the best by score of the next window eligible ones."""
    V, tapes, flags = p['V'], p['tapes'], flags if flags is not None else p['flags']
    rng = random.Random(seed)
    coins = random.Random(seed + 7919)  # kept apart from rng, so a rule's draws don't move the coins
    pos = collections.Counter()
    state = {}  # slot: [rate, visits]
    done = [False] * (p['n'] + 1)
    at = {}  # visit: (start tries, start seconds)
    Q = list(p['Q'])
    d = t = 0.0
    c = collections.Counter()
    phantom = np.zeros(3)  # expected first covers by 60 s, 300 s, the end
    covered = set()
    step = 0
    n_steps = 0
    max_steps = 10 * p['n']
    t_end = p['t_end']
    score = p['score']
    lastrun = {}

    def run_tape(i):
        nonlocal d, t
        v = V[i]
        at[i] = d, t
        d += v['tries']
        t += v['secs']
        done[i] = True
        s = state.setdefault(v['slot'], [0.0, 0])
        s[0], s[1] = v['rate'], s[1] + 1
        pos[v['slot']] += 1
        covered.update(p['golds_at'].get(i, ()))
        if pos[v['slot']] == len(tapes[v['slot']]) and v['slot'] in p['exhausted']:
            s[0] = 0.0

    while t < t_end and n_steps < max_steps:
        if share is not None:
            coin = coins.random() < share(t)
        else:
            coin = flags[step] if step < len(flags) else coins.random() < .3
        step += 1
        n_steps += 1
        took = False
        if coin:
            if mode == 'T':
                live = [k for k, s in state.items() if s[0] > 0 and pos[k] < len(tapes[k])]
            else:
                live = [k for k, s in state.items() if s[0] > 0]
            if live:
                c['resumes'] += 1
                if oracle:
                    def lead(k):
                        for j, i in enumerate(tapes[k][pos[k]:]):
                            if p['golds_at'].get(i, set()) - covered:
                                return -j, state[k][0]
                        return -999, state[k][0]
                    best = max(live, key=lead)
                else:
                    best = max(live, key=lambda k: rule.key(state[k][0], state[k][1], score[k], rng, k[1]))
                if log is not None:
                    on = pos[best] < len(tapes[best])
                    sz = V[tapes[best][pos[best]]]['secs'] if on else p['size'].get(best[1], p['dflt'])[1]
                    log.append((t, best[1], score[best], state[best][0], n_steps - lastrun.get(best, 0), sz, on, tapes[best][pos[best]] if on else -1))
                lastrun[best] = n_steps
                if pos[best] < len(tapes[best]):
                    run_tape(tapes[best][pos[best]])
                else:
                    tr, sc = p['size'].get(best[1], p['dflt'])
                    c['off tape'] += 1
                    c['off tape tries'] += tr
                    b = tbin(t)
                    if mode == 'L':
                        state[best][0] = 0.0
                    else:
                        state[best][0] *= rho
                        add = m * hazard.get((b, best[1]), 0.0) * tr
                        if t + sc <= 60:
                            phantom[0] += add
                        if t + sc <= 300:
                            phantom[1] += add
                        if t + sc <= t_end:
                            phantom[2] += add
                    d += tr
                    t += sc
                took = True
        if not took:
            got = None
            if window <= 1:
                for j, i in enumerate(Q):
                    if all(done[b] for b in p['need'][i]):
                        got = j
                        break
                    c['blocked'] += 1
            else:
                el = []
                for j, i in enumerate(Q):
                    if all(done[b] for b in p['need'][i]):
                        el.append(j)
                        if len(el) == window:
                            break
                if el:
                    got = max(el, key=lambda j: (score[V[Q[j]]['slot']], -j))
            if got is not None:
                lastrun[V[Q[got]]['slot']] = n_steps
                run_tape(Q.pop(got))
            else:  # no new scope can run: a recorded resume runs, or the replay ends
                left = [k for k in state if pos[k] < len(tapes[k])]
                if left:
                    k = max(left, key=lambda k: state[k][0])
                    run_tape(tapes[k][pos[k]])
                    c['forced'] += 1
                else:
                    break
    first = {}
    for g, ev in p['goldv'].items():
        best = None
        for i, dt, tt in ev:
            if i in at:
                x = at[i][0] + dt, at[i][1] + tt
                if x[1] <= t_end and (best is None or x[0] < best[0]):
                    best = x
        first[g] = best
    c['steps same'] = sum(1 for j, i in enumerate(sorted(at, key=lambda i: at[i][1])) if j == i)
    c['visits run'] = len(at)
    return first, phantom, c, d


def arm_hazard(ps):
    """Recorded first covers per try on resumes, by time bin and the slot's kind, over the runs given; and the median change of rate at a resume."""
    hits, tries = collections.Counter(), collections.Counter()
    ratios = []
    for p in ps:
        V = p['V']
        first = {}
        for g, ev in p['goldv'].items():
            first[g] = min(e[0] for e in ev)
        fc = collections.Counter(first.values())
        prev = {}
        for v in V:
            if v['resume']:
                b = tbin(v['t0']), v['kind']
                hits[b] += fc[v['i']]
                tries[b] += v['tries']
                if prev.get(v['slot'], 0) > 0 and v['rate'] > 0:
                    ratios.append(v['rate'] / prev[v['slot']])
            prev[v['slot']] = v['rate']
    return {b: hits[b] / max(tries[b], 1) for b in tries}, float(np.median(ratios))

HBINS = [-1, 30, 60, 120, 300, 700]


def visit_table(arms):
    out = []
    for arm in arms:
        for t, r in load(arm).items():
            annotate(r)
            fc = first_covers(r)
            vo = visit_of(r)
            hit = collections.defaultdict(collections.Counter)
            for g, (d, _) in fc.items():
                kind, depth, reads = r['gold'][g]
                c = hit[min(vo(d), len(r['visits']) - 1)]
                c['all'] += 1
                c['d1' if depth == 1 else 'd2+'] += 1
                c['read0' if reads == 0 else 'reads'] += 1
                c[kind] += 1
                if reads:
                    c[kind + ' reads'] += 1
            prev = {}
            for v in r['visits']:
                h = hit[v['i']]
                out.append(dict(arm=arm, task=t, i=v['i'], resume=v['resume'], kind=v['kind'], tries=v['tries'], new=v['new'], secs=v['secs'], t0=v['t0'], nth=v['nth'], s_pick=v['score'][0], s_max=v['score'][1], s_mean=v['score'][2], prev_rate=prev.get(v['slot'], np.nan),
                                **{'h_' + k.replace(' ', '_'): h[k] for k in ('all', 'd1', 'd2+', 'read0', 'reads', 'RULE', 'DET', 'INIT', 'RULE reads', 'INIT reads', 'DET reads')}))
                prev[v['slot']] = v['rate']
    d = pd.DataFrame(out)
    d['tb'] = pd.cut(d.t0, HBINS, labels=False)
    return d


def fit(s, X, t, y, iters=30):
    """s: stratum numbers, X: n x p, t: tries, y: hits. Gives beta."""
    p = X.shape[1]
    beta = np.zeros(p)
    n = s.max() + 1
    lt = np.log(np.maximum(t, 1))
    Hs = np.bincount(s, y, n)
    for _ in range(iters):
        w = np.exp(lt + X @ beta)
        W = np.bincount(s, w, n)
        Wi = np.where(W > 0, 1 / W, 0)
        mean = np.stack([np.bincount(s, w * X[:, j], n) for j in range(p)], 1) * Wi[:, None]
        grad = (y[:, None] * X).sum(0) - (Hs[:, None] * mean).sum(0)
        # Hessian: sum over strata H_s x weighted covariance of X
        H = np.zeros((p, p))
        P = (Hs[s] * w * Wi[s])
        H = (X * P[:, None]).T @ X - (mean * Hs[:, None]).T @ mean
        H += 1e-6 * np.eye(p)
        step = np.linalg.solve(H, grad)
        beta = beta + step
        if np.abs(step).max() < 1e-6:
            break
    return beta


def banded(d, cols, ycol, B=300, seed=1):
    """beta and 95% band of a resample of tasks."""
    d = d[(d.tries > 0)].copy()
    keep = d.groupby('st')[ycol].transform('sum') > 0
    d = d[keep]
    tasks = d.task.unique()
    idx = {t: g.index.values for t, g in d.groupby('task')}
    X = d[cols].values.astype(float); t = d.tries.values.astype(float); y = d[ycol].values.astype(float); st = d.st.values
    pos = {k: i for i, k in enumerate(d.index)}
    loc = {tk: np.array([pos[i] for i in idx[tk]]) for tk in tasks}

    def go(ix, stid):
        _, inv = np.unique(stid, return_inverse=True)
        return fit(inv, X[ix], t[ix], y[ix])
    b0 = go(np.arange(len(d)), st)
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(B):
        pick = rng.choice(tasks, len(tasks))
        ix = np.concatenate([loc[tk] for tk in pick])
        tag = np.concatenate([np.full(len(loc[tk]), j) for j, tk in enumerate(pick)])
        bs.append(go(ix, st[ix] * 1000 + tag))
    bs = np.array(bs)
    return b0, np.percentile(bs, [2.5, 97.5], axis=0), int(y.sum())


def z_in(d, col, by):
    g = d.groupby(by)[col]
    return (d[col] - g.transform('mean')) / g.transform('std').replace(0, np.nan)


def step_hazard():
    arms = ARMS
    d = visit_table(arms)
    d.to_pickle(HERE + 'cache/visit-table.pkl')
    d = d.reset_index(drop=True)
    d['st'] = d.groupby(['arm', 'task', 'tb', 'resume']).ngroup()
    print('tries', d.tries.sum(), 'first covers', d.h_all.sum(), 'by path', d.groupby('resume').h_all.sum().to_dict(), 'of them reads', d.groupby('resume').h_reads.sum().to_dict())
    for name in ('s_pick', 's_max', 's_mean'):
        d['z_' + name] = z_in(d, name, ['arm', 'task', 'tb', 'resume'])
    d['z_rate'] = np.nan
    x = d[d.resume].copy()
    x['lr'] = np.log(np.maximum(x.prev_rate, .05))
    d.loc[x.index, 'z_rate'] = z_in(x, 'lr', ['arm', 'task', 'tb'])
    print('\nscore slope: change in log first-cover rate per 1 sd of slot score, inside arm, task, time bin, path; 95% band over tasks')
    for path, label in ((False, 'new scope'), (True, 'resume')):
        for name in ('z_s_pick', 'z_s_max', 'z_s_mean'):
            for ycol in ('h_all', 'h_reads', 'h_read0', 'h_RULE', 'h_INIT', 'h_DET', 'h_RULE_reads', 'h_INIT_reads'):
                for lab, q in (('all time', d.resume == path), ('t>=60', (d.resume == path) & (d.t0 >= 60))):
                    y = d[q & d[name].notna()]
                    b, band, n = banded(y, [name], ycol, B=120)
                    print('%-9s %-9s %-13s %-8s n=%4d beta %+.2f (%+.2f to %+.2f) rate ratio per sd %.2f' % (label, name, ycol, lab, n, b[0], band[0, 0], band[1, 0], np.exp(b[0])), flush=True)
    print('\nresume: score and last rate together')
    y = d[d.resume & d.z_s_pick.notna() & d.z_rate.notna()]
    for ycol in ('h_all', 'h_reads'):
        b, band, n = banded(y, ['z_s_pick', 'z_rate'], ycol, B=200)
        print(ycol, 'n', n, 'score %+.2f (%+.2f to %+.2f), last rate %+.2f (%+.2f to %+.2f)' % (b[0], band[0, 0], band[1, 0], b[1], band[0, 1], band[1, 1]), flush=True)
    print('\npath: rate ratio resume against new scope, inside arm, task, time bin')
    d['st2'] = d.groupby(['arm', 'task', 'tb']).ngroup()
    for ycol in ('h_all', 'h_reads', 'h_read0'):
        for tb in range(5):
            y = d[d.tb == tb].copy()
            y['st'] = y.st2
            y['res'] = y.resume.astype(float)
            b, band, n = banded(y, ['res'], ycol, B=200)
            print('%-8s %-11s n=%4d ratio %.2f (%.2f to %.2f)' % (ycol, ['0-30', '30-60', '60-120', '120-300', '300-600'][tb], n, np.exp(b[0]), np.exp(band[0, 0]), np.exp(band[1, 0])), flush=True)



CUTS = (60, 300, 1e9)


def bucket(g):
    k, dp, rd = g
    return k, ('d1' if dp == 1 else 'd2' if dp == 2 else 'd3+'), ('reads' if rd else 'read0')


def task_row(x, ctl, goldinfo, d_end):
    """Per-task numbers of replay x against control ctl."""
    o = collections.Counter()
    for g, a in x['first'].items():
        b = ctl['first'].get(g)
        k, dp, rd = bucket(goldinfo[g])
        da = a[0] if a else d_end
        db = b[0] if b else d_end
        ta = a[1] if a else np.inf
        tb = b[1] if b else np.inf
        if a is None and b is None:
            continue
        bits = np.log2(max(da, 1) / max(db, 1))
        o['forms'] += 1
        o['bits'] += bits
        o['abs'] += abs(bits)
        for tag in (k, dp, rd):
            o['forms ' + tag] += 1
            o['bits ' + tag] += bits
        for c, lab in zip(CUTS, ('60', '300', 'end')):
            o['dn ' + lab] += (ta <= c) - (tb <= c)
            for tag in (k, dp):
                o['dn %s %s' % (lab, tag)] += (ta <= c) - (tb <= c)
    for c, lab, a, b in zip(CUTS, ('60', '300', 'end'), x['phantom'], ctl['phantom']):
        o['dp ' + lab] += a - b
    o['off'] = x['off']
    o['ctl off'] = ctl['off']
    o['off tries'] = x['off_tries']
    o['resumes'] = x['resumes']
    return o


def load_all():
    rows = []
    for arm in ARMS:
        recs = pickle.load(open(HERE + 'cache/replay-%s.pkl' % arm, 'rb'))
        gold = load(arm)
        dend = {t: min(r['draws'], r['visits'][-1]['d1']) for t, r in gold.items()}
        ctl = {(x['task'], x['coin'], x['mode'], x['m']): x for x in recs if x['rule'] == 'rate' and x['agg'] == 'pick'}
        for x in recs:
            if x['rule'] == 'rate' and x['agg'] == 'pick':
                continue
            c = ctl[x['task'], x['coin'], x['mode'], x['m']]
            o = task_row(x, c, gold[x['task']]['gold'], dend[x['task']])
            rows.append(dict(arm=arm, task=x['task'], agg=x['agg'], rule=x['rule'], coin=x['coin'], mode=x['mode'], m=x['m'], **o))
        print(arm, len(rows), flush=True)
    return pd.DataFrame(rows).fillna(0)


def band(t, num, den=None, B=2000, seed=3):
    """t: per-task frame, indexed by task. Gives value, low, high of the sum of num (or sum num / sum den)."""
    a = t[num].values
    n = len(a)
    rng = np.random.default_rng(seed)
    ix = rng.integers(0, n, (B, n))
    if den is None:
        v, s = a.sum(), a[ix].sum(1)
    else:
        b = t[den].values
        v, s = a.sum() / max(b.sum(), 1), a[ix].sum(1) / np.maximum(b[ix].sum(1), 1)
    return v, *np.percentile(s, [2.5, 97.5])


def table(d, arms, rows, mode, m, agg='pick', coins=None, kinds=False):
    """Mean over arms and coins of each task's numbers, then a band over tasks. Counts are per run, summed over the 37 tasks."""
    out = []
    q = d[d.arm.isin(arms) & (d['mode'] == mode) & (d.m == m) & (d['agg'] == agg)]
    if coins is not None:
        q = q[q.coin.isin(coins)]
    for rule in rows:
        x = q[q.rule == rule]
        if x.empty:
            continue
        t = x.groupby('task').mean(numeric_only=True)
        o = dict(rule=rule)
        for lab, num in (('60 s', 'dn 60'), ('300 s', 'dn 300'), ('end', 'dn end')):
            v, lo, hi = band(t, num)
            ph = t['dp ' + lab.split()[0]].sum()
            o['forms ' + lab] = '%+.1f (%+.1f, %+.1f)' % (v, lo, hi)
            if mode == 'M':
                vv, lo, hi = band(t.assign(z=t[num] + t['dp ' + lab.split()[0]]), 'z')
                o['forms ' + lab] = '%+.1f (%+.1f, %+.1f)' % (vv, lo, hi)
        v, lo, hi = band(t, 'bits', 'forms')
        o['bits'] = '%+.3f (%+.3f, %+.3f)' % (v, lo, hi)
        o['off tape share'] = '%.0f%%' % (100 * t.off.sum() / max(t.resumes.sum(), 1))
        out.append(o)
    return pd.DataFrame(out)


def splits(d, arms, rule, mode, m, agg='pick'):
    q = d[d.arm.isin(arms) & (d['mode'] == mode) & (d.m == m) & (d['agg'] == agg) & (d.rule == rule)]
    t = q.groupby('task').mean(numeric_only=True)
    o = {}
    for tag in ('RULE', 'INIT', 'DET', 'd1', 'd2', 'd3+', 'reads', 'read0'):
        if 'forms ' + tag in t:
            v, lo, hi = band(t, 'bits ' + tag, 'forms ' + tag)
            o[tag] = '%+.3f (%+.3f, %+.3f) n=%.0f' % (v, lo, hi, t['forms ' + tag].sum())
    return o



GAP = [(1, 9.80), (2, 9.87), (6, 9.29), (20, 8.02), (60, 7.22), (1e12, 6.62)]  # read_bias.py, resumes past 60 s: tries per s by visits since the slot last ran


def tps(g):
    for a, b in GAP:
        if g <= a:
            return b


def strata(p):
    by = collections.defaultdict(list)
    for v in p['V']:
        if v['resume']:
            by[tbin(v['t0'])].append(p['score'][v['slot']])
    return {b: (float(np.mean(x)), max(float(np.std(x)), .5)) for b, x in by.items()}


def order_change(lr, lb):
    """Share of the rule's resume picks that are a different visit from the rate rule's pick at the same place, and the median place move of visits that are in both."""
    a = [x[7] for x in lr if x[7] >= 0]
    b = [x[7] for x in lb if x[7] >= 0]
    ix = {v: i for i, v in enumerate(a)}
    diff = sum(1 for i, v in enumerate(b) if i >= len(a) or a[i] != v)
    moves = [abs(i - ix[v]) for i, v in enumerate(b) if v in ix]
    return diff, len(b), moves


def step_flow():
    pooled = []
    for arm in ARMS:
        pooled += [prepare(r, 0) for r in load(arm).values()]
    haz, rho = arm_hazard(pooled)
    del pooled
    names = ['rate', 'random', 'score'] + ['rate x e^(%gs)' % b for b in (.0625, .125, .25, .5, 1, 2)] + ['draw e^(1s)', 'rate x kind, INIT 3', 'rate x kind, INIT 10', 'rate x kind x e^(.25s), INIT 3']
    R = dict(rules())
    betas = {'low': -.02, 'point': .15, 'high': .30}
    res = collections.defaultdict(list)
    orderT = collections.defaultdict(lambda: [0, 0, []])
    recorded = collections.Counter()
    zs = collections.defaultdict(list)
    offs = collections.Counter()
    for arm in ARMS:
        for r in load(arm).values():
            p = prepare(r)
            st = strata(p)
            recorded['resume fc'] += sum(1 for g, ev in p['goldv'].items() if p['V'][min(e[0] for e in ev)]['resume'])
            recorded['fc'] += len(p['goldv'])
            for coin in range(0, 6):
                share = None if coin == 0 else (lambda t: .3)
                base_t = []
                replay(p, R['rate'], 'T', 0, seed=coin or 11, hazard=haz, rho=rho, share=share, log=base_t)
                for name in names:
                    vals = {}
                    if name != 'rate':
                        lt = []
                        replay(p, R[name], 'T', 0, seed=coin or 11, hazard=haz, rho=rho, share=share, log=lt)
                        o = orderT[name]
                        a, b, mv = order_change(base_t, lt)
                        o[0] += a; o[1] += b; o[2] += mv
                    log = []
                    replay(p, R[name], 'M', 1.0, seed=coin or 11, hazard=haz, rho=rho, share=share, log=log)
                    for lab, beta in betas.items():
                        for cold in (0, 1):
                            for lgamma in (0, 1):
                                tot = 0.0
                                for t, kind, s, rate, gap, secs, on, _ in log:
                                    b = tbin(t)
                                    mu, sd = st.get(b, (s, 1.0))
                                    z = min(3.0, max(-3.0, (s - mu) / sd))
                                    speed = tps(gap) if cold else 8.6
                                    w = secs * speed * haz.get((b, kind), 0.0) * np.exp(beta * z)
                                    if lgamma:
                                        w *= np.exp(.12 * min(3.0, max(0.0, (np.log(5.2) - np.log(max(rate, .05))) / .27)))
                                    tot += w
                                vals[lab, cold, lgamma] = tot
                    if coin == 0 or True:
                        z = [min(3.0, max(-3.0, (x[2] - st.get(tbin(x[0]), (x[2], 1))[0]) / st.get(tbin(x[0]), (x[2], 1))[1])) for x in log]
                        zs[name] += z
                        offs[name, 'off'] += sum(1 for x in log if not x[6]); offs[name, 'all'] += len(log)
                        offs[name, 'init'] += sum(1 for x in log if x[1] == 'INIT'); offs[name, 'cold'] += sum(1 for x in log if x[4] > 20)
                    res[name].append(vals)
    R0, F = recorded['resume fc'] / len(ARMS), recorded['fc'] / len(ARMS)  # per run
    print('recorded per run: first covers %.1f, on resumes %.1f' % (F, R0))
    print('rule | mean z of picks | off tape | INIT share | gap past 20 visits | order in T: picks moved, median move | c, forms, bits: at beta -.02, .15, .30, no cold cost | with cold cost | with cold cost and the last rate term')
    base = res['rate']
    for name in names:
        rows = []
        for cold, lg in ((0, 0), (1, 0), (1, 1)):
            for lab in betas:
                a = sum(x[lab, cold, lg] for x in res[name])
                b = sum(x[lab, cold, lg] for x in base)
                c = a / b
                rows.append((c, (c - 1) * R0, np.log2(1 + (c - 1) * R0 / F)))
        o = orderT.get(name, [0, 1, [0]])
        print('%-30s z %+.2f off %3.0f%% INIT %3.0f%% gap>20 %3.0f%% | T moved %3.0f%%, %3.0f |' % (name, np.mean(zs[name]), 100 * offs[name, 'off'] / offs[name, 'all'], 100 * offs[name, 'init'] / offs[name, 'all'], 100 * offs[name, 'cold'] / offs[name, 'all'], 100 * o[0] / max(o[1], 1), np.median(o[2]) if o[2] else 0),
              ' ; '.join('c %.2f %+.1f %+.3f' % x for x in rows))



def step_cache():
    """Reads the saved records into one pickle per arm, and checks that the policy has a fold that left out each task."""
    os.makedirs(HERE + 'cache', exist_ok=True)
    try:
        f = fold_check()
        print('folds that left the task out, per task: min %d max %d over %d tasks; tasks with none: %s' % (min(sum(v) for v in f.values()), max(sum(v) for v in f.values()), len(f), [t for t, v in f.items() if not any(v)]))
    except Exception as e:
        print('fold check failed', repr(e)[:300])
    for arm, (root, gpath) in RUNS.items():
        pts = json.load(open(gpath))
        pts = pts if isinstance(pts, list) else pts.get('points', pts)
        golds = {x['task']: gold_forms(x['gold_sexp']) for x in pts if x['task'] in tasks}
        rows = {}
        for t in tasks:
            rows[t] = one(root, arm, t, golds.get(t))
        pickle.dump(rows, open(HERE + 'cache/%s.pkl' % arm, 'wb'))
        n = sum(len(r['visits']) for r in rows.values())
        print(arm, 'tasks', len(rows), 'visits', n, 'resumes', sum(v['resume'] for r in rows.values() for v in r['visits']), 'tries', sum(v['tries'] for r in rows.values() for v in r['visits']), 'draws in banks', sum(r['draws'] for r in rows.values()), 'gold forms', sum(len(r['gold'] or []) for r in rows.values()), 'lives', sum(r['lives'] for r in rows.values()), flush=True)


def step_shares():
    """Shares of visits, tries, seconds, new nodes and first covers by path, and whether the rate rule can be rebuilt from .visits."""


    def share(arm):
        rows = load(arm)
        c = collections.Counter()
        for t, r in rows.items():
            annotate(r)
            vo = visit_of(r)
            fc = first_covers(r)
            for v in r['visits']:
                w = 'resume' if v['resume'] else ('fresh' if v['nth'] == 0 else 'redraw')
                c[w, 'visits'] += 1; c[w, 'tries'] += v['tries']; c[w, 'secs'] += v['secs']; c[w, 'new'] += v['new']
            for g, (d, tm) in fc.items():
                v = r['visits'][min(vo(d), len(r['visits']) - 1)]
                w = 'resume' if v['resume'] else ('fresh' if v['nth'] == 0 else 'redraw')
                c[w, 'fc'] += 1
                kind = r['gold'][g][0] if r['gold'] and g < len(r['gold']) else '?'
                c[w, 'fc', kind] += 1
                c[w, 'fc', 'd%d' % min(r['gold'][g][1], 4)] += 1
                c[w, 'fc', 't<60' if tm < 60 else 't>=60'] += 1
        return c


    for arm in ARMS:
        c = share(arm)
        tv, tt, ts, tn, tf = [sum(c[w, x] for w in ('resume', 'fresh', 'redraw')) for x in ('visits', 'tries', 'secs', 'new', 'fc')]
        print(arm, 'tot visits', tv, 'tries', tt, 'secs %.0f' % ts, 'new', tn, 'fc', tf)
        for w in ('resume', 'fresh', 'redraw'):
            print('  %-7s visits %5.1f%% tries %5.1f%% secs %5.1f%% new %5.1f%% first covers %5.1f%% (%d) | per 1000 tries %.2f | by kind %s depth %s t %s' % (w, 100 * c[w, 'visits'] / tv, 100 * c[w, 'tries'] / tt, 100 * c[w, 'secs'] / ts, 100 * c[w, 'new'] / tn, 100 * c[w, 'fc'] / tf, c[w, 'fc'], 1000 * c[w, 'fc'] / max(c[w, 'tries'], 1),
                  {k: c[w, 'fc', k] for k in ('RULE', 'DET', 'INIT', 'CHOOSE', 'BRANCH') if c[w, 'fc', k]}, {k: c[w, 'fc', k] for k in ('d1', 'd2', 'd3', 'd4') if c[w, 'fc', k]}, (c[w, 'fc', 't<60'], c[w, 'fc', 't>=60'])))

    # B: can the rate rule be rebuilt
    print('\nrate rule rebuilt from the records: recorded resume is the argmax of (rate, -visits) over live parked')
    for arm in ARMS:
        rows = load(arm)
        ok = n = 0; ranks = []; cands = []
        for t, r in rows.items():
            annotate(r)
            state = {}
            for v in r['visits']:
                if v['resume']:
                    live = {k: s for k, s in state.items() if s[0] > 0 and not s[2]}
                    n += 1
                    if live:
                        best = max(live, key=lambda k: (live[k][0], -live[k][1]))
                        ok += best == v['slot']
                        cands.append(len(live))
                        if v['slot'] in live:
                            order = sorted(live, key=lambda k: (-live[k][0], live[k][1]))
                            ranks.append(order.index(v['slot']))
                        else:
                            ranks.append(-1)
                st = state.get(v['slot'], (0, 0, False))
                done = v['nth'] == len(r['tapes'][v['slot']]) - 1 and v['slot'] in r['exhausted']
                state[v['slot']] = (v['rate'], st[1] + 1, done)
        print(arm, 'resumes', n, 'argmax match %.1f%%' % (100 * ok / n), 'median live parked', np.median(cands), 'rank of recorded pick quantiles', np.percentile(ranks, [50, 90, 99]), 'not live', sum(x < 0 for x in ranks))


def step_tape():
    """Slots with one visit and with more, first covers per try by score fifth, by visit number, by last rate, by time and by kind."""
    AGG = {'pick': 0, 'max': 1, 'mean': 2}


    def rows_of(arm):
        """One row per visit, with the live parked set at the pick."""
        out = []
        tape = collections.Counter()
        rows = load(arm)
        for t, r in rows.items():
            annotate(r)
            fc = first_covers(r)
            vo = visit_of(r)
            hits = collections.Counter(min(vo(d), len(r['visits']) - 1) for d, _ in fc.values())
            hits_k = collections.defaultdict(collections.Counter)
            for g, (d, _) in fc.items():
                hits_k[min(vo(d), len(r['visits']) - 1)][r['gold'][g][0]] += 1
            state = {}
            sn = len(r['tapes'])
            tape['slots'] += sn
            tape['slots 1 visit'] += sum(len(x) == 1 for x in r['tapes'].values())
            tape['slots 2+ visits'] += sum(len(x) >= 2 for x in r['tapes'].values())
            tape['tries in slots 2+'] += sum(r['visits'][i]['tries'] for x in r['tapes'].values() if len(x) >= 2 for i in x)
            tape['tries'] += sum(v['tries'] for v in r['visits'])
            tape['yielding slots (any visit new>0)'] += sum(any(r['visits'][i]['new'] > 0 for i in x) for x in r['tapes'].values())
            tape['max tape'] = max(tape['max tape'], max(len(x) for x in r['tapes'].values()))
            tape['max 5 slot tries share'] += sum(sorted((sum(r['visits'][i]['tries'] for i in x) for x in r['tapes'].values()), reverse=True)[:5])
            for v in r['visits']:
                live = {k: s for k, s in state.items() if s['rate'] > 0 and not s['done']}
                row = dict(task=t, arm=arm, i=v['i'], resume=v['resume'], kind=v['kind'], tries=v['tries'], new=v['new'], secs=v['secs'], t0=v['t0'], hits=hits[v['i']], hits_k=hits_k[v['i']], nth=v['nth'], score=v['score'], nlive=len(live), prev=state.get(v['slot']), rate=v['rate'])
                if v['score'][0] is not None and live:
                    sc = np.array([s['score'][0] if s['score'][0] is not None else np.nan for s in live.values()])
                    row['pct_live'] = float(np.nanmean(sc <= v['score'][0]))
                out.append(row)
                done = v['nth'] == len(r['tapes'][v['slot']]) - 1 and v['slot'] in r['exhausted']
                state[v['slot']] = dict(rate=v['rate'], visits=v['nth'] + 1, done=done, score=v['score'], kind=v['kind'])
        return out, tape


    ALL = []
    for arm in ARMS:
        o, tape = rows_of(arm)
        ALL += o
        print(arm, dict(tape), 'share tries top5 per task %.3f' % (tape['max 5 slot tries share'] / tape['tries']))

    d = pd.DataFrame([{k: v for k, v in x.items() if k not in ('hits_k', 'prev', 'score')} | {'s_pick': x['score'][0], 's_max': x['score'][1], 's_mean': x['score'][2], 'prev_rate': (x['prev'] or {}).get('rate', np.nan), 'hRULE': x['hits_k'].get('RULE', 0), 'hINIT': x['hits_k'].get('INIT', 0), 'hDET': x['hits_k'].get('DET', 0)} for x in ALL])
    d.to_pickle(HERE + 'cache/visits.pkl')
    print(d.s_pick.describe())
    d['tb'] = pd.cut(d.t0, [-1, 30, 60, 120, 300, 700], labels=False)
    # within (arm, task, time bin) ranks of score
    for name in ('s_pick', 's_max', 's_mean'):
        d['r_' + name] = d.groupby(['arm', 'task', 'tb', 'resume'])[name].rank(pct=True)
    print('\nfirst covers per 1000 tries, by score fifth within arm, task, time bin and path')
    for path in (False, True):
        x = d[(d.resume == path) & (d.s_pick.notna())]
        for name in ('r_s_pick', 'r_s_max', 'r_s_mean'):
            b = pd.cut(x[name], [0, .2, .4, .6, .8, 1.0], labels=False)
            g = x.groupby(b).agg(hits=('hits', 'sum'), tries=('tries', 'sum'), new=('new', 'sum'), n=('hits', 'size'))
            print('resume' if path else 'new   ', name, ' '.join('%d/%.1fk=%.2f' % (a, b / 1000, 1000 * a / b) for a, b in zip(g.hits, g.tries)), ' new/try', ' '.join('%.2f' % (a / b) for a, b in zip(g.new, g.tries)))
    print('\nsame with time bin t>=60 only')
    for path in (False, True):
        x = d[(d.resume == path) & (d.s_pick.notna()) & (d.t0 >= 60)]
        b = pd.cut(x['r_s_pick'], [0, .2, .4, .6, .8, 1.0], labels=False)
        g = x.groupby(b).agg(hits=('hits', 'sum'), tries=('tries', 'sum'))
        print('resume' if path else 'new   ', ' '.join('%d/%.1fk=%.2f' % (a, b / 1000, 1000 * a / b) for a, b in zip(g.hits, g.tries)))
    print('\nresumes: chosen slot score percentile among live parked: quantiles', d[d.resume].pct_live.quantile([.1, .25, .5, .75, .9]).round(2).tolist())
    print('resumes: by nth visit', d[d.resume].groupby(d.nth.clip(upper=6)).agg(hits=('hits', 'sum'), tries=('tries', 'sum'), n=('hits', 'size'), new=('new', 'sum')).assign(rate=lambda g: 1000 * g.hits / g.tries, newp=lambda g: g.new / g.tries).round(2).to_string())
    print('resumes: by previous rate bin', d[d.resume].groupby(pd.qcut(d.prev_rate, 5, duplicates='drop'), observed=True).agg(hits=('hits', 'sum'), tries=('tries', 'sum'), n=('hits', 'size'), new=('new', 'sum')).assign(rate=lambda g: 1000 * g.hits / g.tries, newp=lambda g: g.new / g.tries).round(2).to_string())
    print('all paths by time bin', d.groupby(['tb', 'resume']).agg(hits=('hits', 'sum'), tries=('tries', 'sum'), n=('hits', 'size'), new=('new', 'sum')).assign(rate=lambda g: 1000 * g.hits / g.tries, newp=lambda g: g.new / g.tries).round(2).to_string())
    print('kinds of visit by path, tries share', d.groupby(['resume', 'kind']).agg(tries=('tries', 'sum'), hits=('hits', 'sum'), hR=('hRULE', 'sum'), hI=('hINIT', 'sum'), hD=('hDET', 'sum')).to_string())


def step_hazard2():
    """Visit number on resumes, finer time strata for score, kind by path and time."""
    d = pd.read_pickle(HERE + 'cache/visit-table.pkl').reset_index(drop=True)
    r = d[d.resume].copy()
    r['st'] = r.groupby(['arm', 'task', 'tb']).ngroup()
    r['n1'] = (r.nth == 1).astype(float)
    r['n2'] = (r.nth == 2).astype(float)
    r['n3'] = (r.nth >= 3).astype(float)
    print('resume: rate ratio by visit number, against visit 4 and on, inside arm, task, time bin')
    for ycol in ('h_all', 'h_reads'):
        x = r.copy()
        x['a'] = (x.nth == 1).astype(float)
        x['b'] = (x.nth == 2).astype(float)
        b, band, n = banded(x, ['a', 'b'], ycol, B=300)
        print(ycol, 'n', n, 'second visit %.2f (%.2f to %.2f), third %.2f (%.2f to %.2f), against later visits' % (np.exp(b[0]), *np.exp(band[:, 0]), np.exp(b[1]), *np.exp(band[:, 1])), flush=True)
        b, band, n = banded(x, ['a'], ycol, B=300)
        print(ycol, 'second visit against all later: %.2f (%.2f to %.2f)' % (np.exp(b[0]), *np.exp(band[:, 0])), flush=True)
    print('\nshare of resume tries on the second visit', r[r.nth == 1].tries.sum() / r.tries.sum())
    print('first covers per 1000 tries on resumes, by visit number and time past 120 s')
    x = r[r.t0 >= 120]
    print(x.groupby(x.nth.clip(upper=5)).agg(hits=('h_all', 'sum'), tries=('tries', 'sum')).assign(rate=lambda g: 1000 * g.hits / g.tries).round(2).to_string())
    print('\nscore slope with time strata of 10 s under 60 s and the same bins after')
    d2 = d.copy()
    d2['fb'] = np.where(d2.t0 < 60, (d2.t0 // 10).astype(int), 10 + d2.tb)
    d2['st'] = d2.groupby(['arm', 'task', 'fb', 'resume']).ngroup()
    d2['z'] = z_in(d2, 's_pick', ['arm', 'task', 'fb', 'resume'])
    for path, lab in ((False, 'new scope'), (True, 'resume')):
        for ycol in ('h_all', 'h_reads', 'h_RULE_reads', 'h_INIT_reads', 'h_DET'):
            y = d2[(d2.resume == path) & d2.z.notna()]
            b, band, n = banded(y, ['z'], ycol, B=150)
            print(lab, ycol, 'n', n, 'ratio per sd %.2f (%.2f to %.2f)' % (np.exp(b[0]), *np.exp(band[:, 0])), flush=True)
    print('\nscore sd of slots inside a stratum, by path', d.groupby('resume').apply(lambda g: g.groupby(['arm', 'task', 'tb']).s_pick.std().median()).round(2).to_dict())
    print('\nkind of slot by path and time, tries share and first covers per 1000 tries')
    for lab, q in (('t<60', d.t0 < 60), ('60-300', (d.t0 >= 60) & (d.t0 < 300)), ('t>=300', d.t0 >= 300)):
        print(lab)
        print(d[q].groupby(['resume', 'kind']).agg(tries=('tries', 'sum'), hits=('h_all', 'sum')).assign(rate=lambda g: 1000 * g.hits / g.tries).round(2).to_string())


def step_bias():
    """What a cold resume costs, what a renewal does to new, repeat covers, the rates of parked slots."""
    out = []
    cov = collections.Counter()
    rank = []
    for arm in ARMS:
        for t, r in load(arm).items():
            annotate(r)
            last, prev_rate = {}, {}
            ren = 0
            prev_cum = 0
            since = 0
            state = {}
            fc = first_covers(r)
            cov['events'] += len(r['covers']); cov['forms'] += len(fc)
            ev = collections.Counter(c[0] for c in r['covers'])
            cov['forms with 2+ events'] += sum(x >= 2 for x in ev.values())
            slots_of = collections.defaultdict(set)
            vo = visit_of(r)
            for g, d, _, _ in r['covers']:
                slots_of[g].add(r['visits'][min(vo(d), len(r['visits']) - 1)]['slot'])
            cov['forms on 2+ slots'] += sum(len(x) >= 2 for x in slots_of.values())
            for v in r['visits']:
                if v['cum_seconds'] < prev_cum:
                    ren += 1
                    since = 0
                prev_cum = v['cum_seconds']
                gap = v['i'] - last[v['slot']] if v['slot'] in last else None
                out.append(dict(arm=arm, task=t, resume=v['resume'], gap=gap, tries=v['tries'], secs=v['secs'], new=v['new'], kind=v['kind'], t0=v['t0'], since=since, nth=v['nth'], gen=ren))
                since += 1
                last[v['slot']] = v['i']
                if v['resume']:
                    live = [x for k, x in state.items() if x > 0]
                    if live:
                        rank.append((v['t0'], np.mean(np.array(live) < prev_rate.get(v['slot'], 0)), prev_rate.get(v['slot'], 0), float(np.median(live))))
                prev_rate[v['slot']] = v['rate']
                state[v['slot']] = v['rate']
    d = pd.DataFrame(out)
    print(dict(cov))
    print('renewals per task', d.groupby(['arm', 'task']).gen.max().mean())
    x = d[d.resume & d.gap.notna()].copy()
    x['gb'] = pd.cut(x.gap, [0, 1, 2, 6, 20, 60, 1e9])
    g = x[x.t0 >= 60].groupby('gb', observed=True).agg(visits=('tries', 'size'), tries=('tries', 'sum'), secs=('secs', 'sum'), new=('new', 'sum'))
    g['tries per s'] = g.tries / g.secs
    g['new per try'] = g.new / g.tries
    print('resumes past 60 s, by visits since the slot last ran\n', g.round(2).to_string())
    f = d[(~d.resume) & (d.t0 >= 60)]
    print('new scopes past 60 s: tries per s %.2f, new per try %.2f' % (f.tries.sum() / f.secs.sum(), f.new.sum() / f.tries.sum()))
    y = d[d.t0 >= 60].copy()
    y['sb'] = pd.cut(y.since, [-1, 2, 5, 10, 20, 40, 80, 1e9])
    g = y.groupby(['resume', 'sb'], observed=True).agg(tries=('tries', 'sum'), new=('new', 'sum'), secs=('secs', 'sum'))
    g['new per try'] = g.new / g.tries
    g['tries per s'] = g.tries / g.secs
    print('by visits since the last renewal\n', g.round(2).to_string())
    R = pd.DataFrame(rank, columns=['t0', 'pct', 'rate', 'med'])
    print('resumed slot: rate percentile among live parked', R.pct.quantile([.1, .5, .9]).round(3).tolist(), 'resumed rate / median parked rate', (R.rate / R.med).quantile([.1, .5, .9]).round(2).tolist())
    print('recorded parked rates, past 60 s: median of median parked rate %.2f, median resumed rate %.2f' % (R[R.t0 >= 60].med.median(), R[R.t0 >= 60].rate.median()))


def step_replays():
    """All replays, one output file per arm."""
    COINS = 6
    MODES = [('T', 0.0), ('L', 0.0), ('M', .5), ('M', 1.0), ('M', 2.0)]
    t0 = time.time()
    pooled = []
    for arm in ARMS:
        pooled += [prepare(r, 0) for r in load(arm).values()]
    haz, rho = arm_hazard(pooled)
    del pooled
    print('per 1000 tries off the tape', {k: round(1000 * v, 2) for k, v in sorted(haz.items())}, 'rho', round(rho, 3), flush=True)


    def row(out, arm, p, agg, rule, coin, mode, m, got):
        f, ph, c, d = got
        out.append(dict(arm=arm, task=p['task'], agg=agg, rule=rule, coin=coin, mode=mode, m=m, first=f, phantom=ph, off=c['off tape'], off_tries=c['off tape tries'], resumes=c['resumes'], visits=c['visits run'], d=d, forced=c['forced']))


    for arm in ARMS:
        out = []
        rows = load(arm)
        for agg, aggname in ((0, 'pick'), (1, 'max'), (2, 'mean')):
            for r in rows.values():
                p = prepare(r, agg)
                for name, rule in rules():
                    if agg and ('score' not in name and 'e^' not in name):
                        continue
                    for coin in range(COINS):
                        if agg and coin > 0:
                            continue
                        for mode, m in MODES:
                            got = replay(p, rule, mode, m, seed=coin or 11, hazard=haz, rho=rho, share=None if coin == 0 else (lambda t: .3))
                            row(out, arm, p, aggname, name, coin, mode, m, got)
                if agg:
                    continue
                for coin in range(COINS):
                    share = None if coin == 0 else (lambda t: .3)
                    row(out, arm, p, aggname, 'best order, reads the future', coin, 'T', 0, replay(p, Rule('rate'), 'T', 0, seed=coin or 11, hazard=haz, rho=rho, oracle=True, share=share))
                    for w in (2, 4, 8, 16):
                        row(out, arm, p, aggname, 'new scopes by score, window %d' % w, coin, 'T', 0, replay(p, Rule('rate'), 'T', 0, seed=coin or 11, hazard=haz, rho=rho, window=w, share=share))
                for lab, sh in (('share .5 past 120 s', lambda t: .5 if t >= 120 else .3), ('share .7 past 120 s', lambda t: .7 if t >= 120 else .3), ('share .1 to 60 s, .5 after', lambda t: .1 if t < 60 else .5), ('share .5', lambda t: .5), ('share .15', lambda t: .15)):
                    for coin in range(1, COINS):
                        for mode, m in MODES[1:]:
                            row(out, arm, p, aggname, lab, coin, mode, m, replay(p, Rule('rate'), mode, m, seed=coin, hazard=haz, rho=rho, share=sh))
        pickle.dump(out, open(HERE + 'cache/replay-%s.pkl' % arm, 'wb'))
        print(arm, 'done', round(time.time() - t0), 's', len(out), flush=True)


def step_tables():
    """The paired tables."""
    d = pd.read_pickle(HERE + 'cache/paired.pkl')
    RULES = ['random', 'score'] + ['rate x e^(%gs)' % b for b in (.0625, .125, .25, .5, 1, 2)] + ['draw e^(%gs)' % b for b in (.25, .5, 1, 2)]
    KIND = ['rate, RIGID_DET 0', 'rate x kind, INIT 3', 'rate x kind, INIT 10', 'rate x kind x e^(.25s), INIT 3']
    NEW = ['best order, reads the future'] + ['new scopes by score, window %d' % w for w in (2, 4, 8, 16)]
    SHARE = ['share .15', 'share .5 past 120 s', 'share .7 past 120 s', 'share .1 to 60 s, .5 after', 'share .5']
    COVER = ['cover_s0', 'cover_s1']
    REFIT = ['ext_s0', 'ext_s1', 'extk_s0', 'extk_s1']
    BASE = ['base_s0', 'base_s1']
    for lab, arms in (('all 8 arms', ARMS), ('cover, 2 seeds', COVER), ('ext and extk, 2 seeds each', REFIT)):
        for mode, m in (('T', 0), ('L', 0), ('M', .5), ('M', 1), ('M', 2)):
            print('\n== %s, mode %s m %s: forms covered against rate (band over tasks), per run over 37 tasks; bits: mean log2 of proposals to first cover against rate' % (lab, mode, m))
            print(table(d, arms, RULES + KIND + (NEW if mode == 'T' else SHARE), mode, m).to_string(index=False))
    print('\n== by kind and depth, all 8 arms: bits against rate')
    for rule, mode, m in (('score', 'T', 0), ('rate x e^(0.25s)', 'T', 0), ('rate x e^(1s)', 'T', 0), ('score', 'M', 1), ('rate x e^(0.25s)', 'M', 1), ('rate x kind, INIT 3', 'T', 0), ('rate x kind, INIT 3', 'M', 1)):
        print(rule, mode, m, splits(d, ARMS, rule, mode, m))
    print('\n== form counts by kind and depth, T and M1: forms at end against rate')
    for rule, mode, m in (('score', 'L', 0), ('rate x e^(0.25s)', 'L', 0), ('rate x kind, INIT 3', 'L', 0)):
        q = d[(d.rule == rule) & (d['mode'] == mode) & (d.m == m) & (d['agg'] == 'pick')]
        t = q.groupby('task').mean(numeric_only=True)
        print(rule, mode, {k: round(float(t['dn end ' + k].sum()), 2) for k in ('RULE', 'INIT', 'DET', 'd1', 'd2', 'd3+') if 'dn end ' + k in t})
    print('\n== per arm, recorded coins and coin redraws: bits and forms at 300 s, T')
    for rule in ('score', 'rate x e^(0.25s)', 'rate x kind, INIT 3', 'random'):
        for arm in ARMS:
            q = d[(d.rule == rule) & (d['mode'] == 'T') & (d['agg'] == 'pick') & (d.arm == arm)]
            rec = q[q.coin == 0].sum(numeric_only=True)
            red = q[q.coin > 0].groupby('coin').sum(numeric_only=True)
            print('%-22s %-9s recorded coins bits %+.3f, 60 s %+d, 300 s %+d | redrawn coins bits %+.3f, 300 s %+.1f (coin sd %.1f)' % (rule, arm, rec['bits'] / rec['forms'], rec['dn 60'], rec['dn 300'], (red.bits / red.forms).mean(), red['dn 300'].mean(), red['dn 300'].std()))
    print('\n== other slot scores, recorded coins, all 8 arms, T and M1')
    for agg in ('max', 'mean'):
        for mode, m in (('T', 0), ('M', 1)):
            print(agg, mode)
            print(table(d, ARMS, ['score', 'rate x e^(0.25s)', 'rate x e^(1s)', 'draw e^(1s)'], mode, m, agg=agg, coins=[0]).to_string(index=False))


def step_mech():
    """Whether a slot that holds a covered gold form yields more, whether score marks such slots, the kind signal by run, and resume share by time."""

    d = pd.read_pickle(HERE + 'cache/visit-table.pkl').reset_index(drop=True)
    # Does the slot hold a gold form already covered? Read from cover draws, and the forms born at them.
    hold = {}
    for arm in ARMS:
        for t, r in load(arm).items():
            annotate(r)
            at = collections.defaultdict(set)
            for f, x in r['forms'].items():
                if x['birth'] is not None:
                    at[x['birth']].add(f)
            gf = {}
            for g, dr, tm, dp in r['covers']:
                for f in at.get(dr, ()):
                    gf.setdefault(f, dr)
            for v in r['visits']:
                n = sum(1 for f in v['fids'] if f in gf and gf[f] <= v['d0'])
                hold[arm, t, v['i']] = n, len(v['fids'])
    d['gold_held'] = [hold[a, t, i][0] for a, t, i in zip(d.arm, d.task, d.i)]
    d['forms_held'] = [hold[a, t, i][1] for a, t, i in zip(d.arm, d.task, d.i)]
    d['any_gold'] = (d.gold_held > 0).astype(float)
    print('share of tries in a slot that holds a covered gold form, t>=60: new %.3f, resume %.3f' % (d[(~d.resume) & (d.t0 >= 60)].pipe(lambda x: (x.tries * x.any_gold).sum() / x.tries.sum()), d[d.resume & (d.t0 >= 60)].pipe(lambda x: (x.tries * x.any_gold).sum() / x.tries.sum())))
    print('slot rate by whether it holds a covered gold form (rate ratio holds / not, inside arm, task, time bin, path), t>=60')
    d['st'] = d.groupby(['arm', 'task', 'tb', 'resume']).ngroup()
    for lab, q in (('new scope', ~d.resume & (d.t0 >= 60)), ('resume', d.resume & (d.t0 >= 60))):
        for y in ('h_all', 'h_reads', 'h_RULE_reads', 'h_INIT_reads'):
            b, band, n = banded(d[q], ['any_gold'], y, B=200)
            print('  %-9s %-13s n=%3d ratio %.2f (%.2f to %.2f)' % (lab, y, n, np.exp(b[0]), *np.exp(band[:, 0])), flush=True)
    print('does slot score mark the slots that hold a covered gold form? AUC inside arm, task, time bin, t>=60')
    x = d[(d.t0 >= 60) & d.s_pick.notna()]
    aucs = {}
    for path in (False, True):
        got = []
        for _, g in x[x.resume == path].groupby(['arm', 'task', 'tb']):
            a = g[g.any_gold > 0].s_pick.values; b = g[g.any_gold == 0].s_pick.values
            if len(a) >= 3 and len(b) >= 3:
                r = pd.Series(np.r_[a, b]).rank().values
                got.append((r[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b)))
        aucs[path] = (float(np.mean(got)), len(got))
    print(' new', aucs[False], 'resume', aucs[True])
    print('\nsd of log last rate on resumes inside arm, task, time bin: median', float(d[d.resume].assign(lr=lambda q: np.log(np.maximum(q.prev_rate, .05))).groupby(['arm', 'task', 'tb']).lr.std().median()))
    print('\nfirst covers per 1000 tries on resumes by slot kind, by run, past 120 s')
    late = d[d.resume & (d.t0 >= 120)]
    tab = late.groupby(['arm', 'kind']).agg(h=('h_all', 'sum'), tr=('tries', 'sum'))
    print((tab.h / tab.tr * 1000).unstack().round(2).to_string())
    print(tab.h.unstack().to_string())
    print('\nsame on new scopes')
    late = d[~d.resume & (d.t0 >= 120)]
    tab = late.groupby(['arm', 'kind']).agg(h=('h_all', 'sum'), tr=('tries', 'sum'))
    print((tab.h / tab.tr * 1000).unstack().round(2).to_string())
    print('\nby time bin, per run: tries, resume tries share, first covers on each path, per 1000 tries')
    g = d.groupby(['tb', 'resume']).agg(tr=('tries', 'sum'), h=('h_all', 'sum'), s=('secs', 'sum')).unstack()
    print(g.to_string())
    n = len(ARMS)
    print('\nflow for a share of resumes by time bin: tries in a bin hold; resume tries per visit vs new tries per visit by recorded means')
    SHARES = {'.3 (today)': [.3] * 5, '.5 past 120 s': [.3, .3, .3, .5, .5], '.7 past 120 s': [.3, .3, .3, .7, .7], '0 to 60 s, then .3': [0, 0, .3, .3, .3], '.1 to 60 s, .5 after': [.1, .1, .5, .5, .5], '.5': [.5] * 5}
    out = {}
    for lab, sh in SHARES.items():
        tot = 0.0
        for b in range(5):
            rr = d[(d.tb == b) & d.resume]
            nn = d[(d.tb == b) & ~d.resume]
            hr, hn = rr.h_all.sum() / rr.tries.sum(), nn.h_all.sum() / nn.tries.sum()
            T = (rr.tries.sum() + nn.tries.sum()) / n
            mr, mn = rr.tries.mean(), nn.tries.mean()
            s = sh[b] * mr / (sh[b] * mr + (1 - sh[b]) * mn)
            tot += T * (s * hr + (1 - s) * hn)
        out[lab] = tot
    for lab, v in out.items():
        print('  %-22s first covers per run %.1f, change %+.1f, bits %+.3f' % (lab, v, v - out['.3 (today)'], np.log2(v / out['.3 (today)'])))

    # resume share on the tape: mode L, coins redrawn, against share .3
    print('\nresume share in replays, mode L, 5 coins, all 8 arms, against share .3 on the same coins')
    rows = collections.defaultdict(list)
    R = Rule('rate')
    for arm in ARMS:
        for r in load(arm).values():
            p = prepare(r)
            for coin in range(1, 6):
                ctl = replay(p, R, 'L', 0, seed=coin, share=lambda t: .3)
                for lab, sh in (('0 to 60 s, then .3', lambda t: 0 if t < 60 else .3), ('.15 to 60 s, then .3', lambda t: .15 if t < 60 else .3), ('0 to 30 s, then .3', lambda t: 0 if t < 30 else .3)):
                    got = replay(p, R, 'L', 0, seed=coin, share=sh)
                    o = collections.Counter()
                    for g, a in got[0].items():
                        b = ctl[0].get(g)
                        if a is None and b is None:
                            continue
                        da, db = (a[0] if a else p['d_end']), (b[0] if b else p['d_end'])
                        o['forms'] += 1
                        o['bits'] += np.log2(max(da, 1) / max(db, 1))
                        for c, tag in ((60, '60'), (300, '300'), (1e12, 'end')):
                            o[tag] += (a is not None and a[1] <= c) - (b is not None and b[1] <= c)
                    rows[lab].append(dict(task=p['task'], arm=arm, coin=coin, **o, forced=got[2]['forced']))
    for lab, x in rows.items():
        q = pd.DataFrame(x).fillna(0).groupby('task').mean(numeric_only=True)
        rng = np.random.default_rng(5)
        ix = rng.integers(0, len(q), (2000, len(q)))
        txt = []
        for c in ('60', '300', 'end'):
            s = q[c].values[ix].sum(1)
            txt.append('%s s %+.1f (%+.1f, %+.1f)' % (c, q[c].sum(), *np.percentile(s, [2.5, 97.5])))
        s = q.bits.values[ix].sum(1) / q.forms.values[ix].sum(1)
        print(' ', lab, ' '.join(txt), 'bits %+.3f (%+.3f, %+.3f)' % (q.bits.sum() / q.forms.sum(), *np.percentile(s, [2.5, 97.5])), 'forced', round(q.forced.sum(), 1))


def step_paired():
    """The replays against the rate rule, task by task."""
    load_all().to_pickle(HERE + 'cache/paired.pkl')


if __name__ == '__main__':
    ALL = ['cache', 'shares', 'tape', 'hazard', 'hazard2', 'bias', 'replays', 'paired', 'tables', 'flow', 'mech']
    for name in sys.argv[1:] or ALL:
        print('\n#### %s' % name, flush=True)
        globals()['step_' + name]()
