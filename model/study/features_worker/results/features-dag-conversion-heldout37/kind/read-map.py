"""The read on the held map, once, with the frozen fit, on facts of a scope as a set (scope_facts.py of this folder). It reads map-visit-rows.tsv, map-cover-rows.tsv and map-exposure-rows.tsv of build-map-rows.py and writes map-reads.jsonl, one line per section, and cells-map-leaf-stage.tsv. A rerun skips finished sections.

Every section but check_exposure reads held events. Before it loads a held event, a section stops unless the manifest of the record holds the sha256 of frozen-fit.json and scope_facts.py under `kind_frozen` (kind/record-frozen.py), and unless held-reads.jsonl of the record has no line of its name `kind-map_SECTION`; it then adds that line. The ceiling section fits on held events and is a ceiling only.

  check_exposure  held exposure and right-kind exposure of each form against form-rows.tsv of the base-cost record
  cover_events    per cover event, base arms: bits under pi and under the frozen conditional on gold's kind, for the chain and each fact alone
  pooled          the kind term with the exposures of the map, base arms, s fixed per kind as in decompose.py: actual, under pi, under the conditional; for the chain and each fact alone
  control         the same two reads from 20 fits on shuffled non-held kinds
  ceiling         leave-one-task-out over the cover events, chain and each fact alone, labelled a ceiling

Rules are those of fit-read.py: m = 8, the chain of frozen-fit.json, the marginal with add-one, 2,000 task resamples, thin under 50 rows or under 8 tasks. A visit with a scope form missing from the bank is left out of the reads and counted.

With --selftest, it writes no map rows: it builds one visit per held gold-scope row and one cover per row, and checks that the per-event bits equal the frozen read of fit-read.py.
"""
import collections
import csv
import json
import math
import os
import subprocess
import sys

import numpy as np

H = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, H)
import scope_facts as F  # noqa: E402

BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-base-cost-read-heldout37/'
OUT = H + 'map-reads.jsonl'
SEED = 20261101
CLASSES = ('RULE', 'DET', 'INIT', 'RIGID_DET')
CI = {k: i for i, k in enumerate(CLASSES)}
PI = np.array([6413, 3468, 4297, 10], float)
PI /= PI.sum()
M_ = 8.0
S_FIXED = dict(any=0.30, RULE=0.30, DET=0.50, INIT=0.12)
FZ = json.load(open(H + 'frozen-fit.json'))
CHAIN = [tuple(x) for x in FZ['chain']]
HEADS = set(FZ['heads'])
ALONE = {f: [(f,)] for f in F.FACTS}
R_DIR = H.rsplit('/kind/', 1)[0] + '/'
LEDGER = R_DIR + 'held-reads.jsonl'


def sha(path):
    import hashlib
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def held_gate(name):
    """Stops unless the frozen files have their hashes in the manifest and the ledger has no line of this name; then adds the line."""
    import time
    fz = json.load(open(R_DIR + 'manifest.json')).get('kind_frozen', {})
    for f in ('frozen-fit.json', 'scope_facts.py'):
        if fz.get(f) != sha(H + f):
            sys.exit('refused %s: manifest.json has no kind_frozen hash of %s that equals the file' % (name, f))
    if os.path.exists(LEDGER) and any(json.loads(l).get('name') == name for l in open(LEDGER) if l.strip()):
        sys.exit('refused %s: held-reads.jsonl has a line of that name' % name)
    with open(LEDGER, 'a') as f:
        f.write(json.dumps(dict(name=name, group='kind', arm='frozen-chain', tier='scope', control=name.endswith('control'), time=time.strftime('%Y-%m-%dT%H:%M:%S'))) + '\n')


def gold_rows():
    if os.path.exists(H + 'gold-scope-rows.tsv'):
        return list(csv.DictReader(open(H + 'gold-scope-rows.tsv'), delimiter='\t'))
    p = subprocess.Popen(['zstd', '-dc', H + 'gold-scope-rows.tsv.zst'], stdout=subprocess.PIPE, text=True)
    return list(csv.DictReader(p.stdout, delimiter='\t'))


def norm(r):
    q = dict(r)
    if q['leaf_heads'] != 'none':
        q['leaf_heads'] = '+'.join(sorted({h if h in HEADS else 'other' for h in q['leaf_heads'].split('+')}))
    return q


class Fit:
    """Counts per level over rows of (facts, y, w)."""

    def __init__(self, rows, y, w, levels):
        self.levels = levels
        self.n0 = np.zeros(4)
        np.add.at(self.n0, y, w)
        self.t = []
        for lv in levels:
            d = collections.defaultdict(lambda: np.zeros(4))
            for r, a, b in zip(rows, y, w):
                d['|'.join(r[k] for k in lv)][a] += b
            self.t.append(d)
        self.memo = {}

    def p(self, r):
        k = tuple(r[f] for lv in self.levels[-1:] for f in lv)
        if k not in self.memo:
            P = (self.n0 + 1) / (self.n0.sum() + 4)
            for lv, d in zip(self.levels, self.t):
                c = d.get('|'.join(r[f] for f in lv))
                P = (P * M_ + (c if c is not None else 0)) / ((c.sum() if c is not None else 0) + M_)
            self.memo[k] = P
        return self.memo[k]


def ci(s, n):
    i = np.random.default_rng(SEED).integers(0, len(s), (2000, len(s)))
    v = s[i].sum(1) / np.maximum(n[i].sum(1), 1e-12)
    return [round(float(np.quantile(v, .025)), 3), round(float(np.quantile(v, .975)), 3)]


def event_read(E, fit, label=None):
    """E: rows with task, kind, facts. Mean bits, all and per kind, with ranges."""
    tasks = sorted({e['task'] for e in E})
    ti = {t: i for i, t in enumerate(tasks)}
    t = np.array([ti[e['task']] for e in E])
    y = np.array([CI[e['kind']] for e in E])
    P = np.array([fit.p(e) for e in E])
    bits = -np.log2(P[np.arange(len(E)), y])
    now = -np.log2(PI[y])
    res = {}
    for name, m in [('any', np.ones(len(E), bool))] + [(k, y == CI[k]) for k in CLASSES[:3]]:
        n = np.bincount(t, m.astype(float), minlength=len(tasks))
        res[name] = dict(events=int(m.sum()), tasks=int((n > 0).sum()), bits_now=round(float(now[m].mean()), 3), bits_cond=round(float(bits[m].mean()), 3), saving=round(float((now - bits)[m].mean()), 3), saving_range=ci(np.bincount(t, (now - bits) * m, minlength=len(tasks)), n))
    return res


def pooled(FR, EXP, fit):
    """The kind term per group. EXP[(arm, task, form)] is a list of (facts row, visit kind, n)."""
    tasks = sorted({r['task'] for r in FR})
    ti = {t: i for i, t in enumerate(tasks)}
    res = {}
    for name, s in S_FIXED.items():
        A = np.zeros((len(tasks), 4))  # W held, W right kind, W under pi, W under the conditional
        rows = 0
        for r in FR:
            if name != 'any' and r['kind'] != name:
                continue
            k = CI[r['kind']]
            w = 2.0 ** (-s * r['bits'])
            for facts, vk, n in EXP.get((r['arm'], r['task'], r['form']), ()):
                A[ti[r['task']]] += w * n * np.array([1.0, float(vk == r['kind']), PI[k], fit.p(facts)[k]])
            rows += 1
        i = np.random.default_rng(SEED).integers(0, len(tasks), (2000, len(tasks)))
        B = A[i].sum(1)
        q = lambda v: [round(float(np.nanquantile(v, .025)), 3), round(float(np.nanquantile(v, .975)), 3)]  # noqa: E731
        T = A.sum(0)
        ka, kp, kc = (float(np.log2(T[0] / T[j])) for j in (1, 2, 3))
        res[name] = dict(rows=rows, s=s, kind_actual=round(ka, 3), kind_under_pi=round(kp, 3), kind_cond=round(kc, 3), saving_vs_actual=round(ka - kc, 3), saving_vs_actual_range=q(np.log2(B[:, 0] / B[:, 1]) - np.log2(B[:, 0] / B[:, 3])), saving_vs_pi=round(kp - kc, 3), saving_vs_pi_range=q(np.log2(B[:, 0] / B[:, 2]) - np.log2(B[:, 0] / B[:, 3])))
    return res


def fits(rows):
    y = np.array([CI[r['kind']] for r in rows])
    cnt = collections.Counter((r['task'], r['form']) for r in rows)
    w = np.array([1.0 / cnt[r['task'], r['form']] for r in rows])
    return y, w


def main():
    gold = [norm(r) for r in gold_rows() if r['kind'] in CI and r['rule'] == 'picks6']
    non = [r for r in gold if r['split'] == 'nonheld']
    y, w = fits(non)
    together = Fit(non, y, w, CHAIN)
    if '--selftest' in sys.argv:
        held = [r for r in gold if r['split'] == 'held']
        r = event_read(held, together)
        print(json.dumps(r['any']))
        want = {json.loads(l)['section']: json.loads(l)['value'] for l in open(H + 'reads.jsonl')}['held_read']['together']['per_form']['any']
        print('frozen read of fit-read.py: now %s cond %s' % (want['bits_now'], want['bits_cond']))
        assert abs(r['any']['bits_cond'] - want['bits_cond']) < .002
        print('selftest passed')
        return
    have = {json.loads(l)['section'] for l in open(OUT)} if os.path.exists(OUT) else set()
    out = open(OUT, 'a')
    for s in ('cover_events', 'pooled', 'control', 'ceiling'):
        if s not in have:
            held_gate('kind-map_' + s)

    def emit(n, v):
        out.write(json.dumps(dict(section=n, value=v)) + '\n')
        out.flush()
        print(n, json.dumps(v)[:2000], flush=True)
    V = {}
    miss = tries = 0
    for r in csv.DictReader(open(H + 'map-visit-rows.tsv'), delimiter='\t'):
        tries += int(r['tries'])
        if r['missing'] != '0':
            miss += int(r['tries'])
            continue
        V[r['arm'], r['task'], int(r['visit'])] = norm(r)
    E = []
    for r in csv.DictReader(open(H + 'map-cover-rows.tsv'), delimiter='\t'):
        v = V.get((r['arm'], r['task'], int(r['visit']))) if r['visit'] else None
        if v and r['kind'] in CI and r['arm'].startswith('base'):
            E.append(dict(v, kind=r['kind'], first=r['first'], form=r['form'], visit_kind=v['kind']))
    X = collections.defaultdict(list)
    for r in csv.DictReader(open(H + 'map-exposure-rows.tsv'), delimiter='\t'):
        v = V.get((r['arm'], r['task'], int(r['visit'])))
        if v and r['arm'].startswith('base'):
            X[r['arm'], r['task'], int(r['form'])].append((v, v['kind'], int(r['n'])))
    FR = []
    for r in csv.DictReader(open(BASE + 'form-rows.tsv'), delimiter='\t'):
        if r['bits'] in ('', 'None') or r['own_key'] != '1' or not r['arm'].startswith('base') or r['kind'] not in CI:
            continue
        FR.append(dict(arm=r['arm'], task=r['task'], form=int(r['form']), kind=r['kind'], bits=float(r['bits']), e_hk=int(r['e_hk']), e_hx=int(r['e_hx'])))
    if 'check_exposure' not in have:
        bad = 0
        for r in FR:
            q = X.get((r['arm'], r['task'], r['form']), ())
            bad += (sum(n for *_, n in q) != r['e_hk'] + r['e_hx']) or (sum(n for _, k, n in q if k == r['kind']) != r['e_hk'])
        emit('check_exposure', dict(forms=len(FR), differ=bad, tries_scope_missing=miss, tries=tries))
    if 'cover_events' not in have:
        res = dict(events=len(E), together=event_read(E, together))
        for f, lv in ALONE.items():
            res['alone ' + f] = event_read(E, Fit(non, y, w, lv))
        emit('cover_events', res)
    if 'pooled' not in have:
        res = dict(together=pooled(FR, X, together))
        for f, lv in ALONE.items():
            res['alone ' + f] = pooled(FR, X, Fit(non, y, w, lv))
        emit('pooled', res)
    if 'control' not in have:
        fid = np.array([r['task'] + ' ' + r['form'] for r in non])
        u, inv = np.unique(fid, return_inverse=True)
        fy = np.zeros(len(u), int)
        fy[inv] = y
        got, po = [], []
        for i in range(20):
            ys = np.random.default_rng(SEED + i).permutation(fy)[inv]
            f = Fit(non, ys, w, CHAIN)
            got.append(event_read(E, f)['any']['saving'])
            po.append(pooled(FR, X, f)['any']['saving_vs_pi'])
        emit('control', dict(cover_saving_each=got, cover_mean=round(float(np.mean(got)), 3), pooled_vs_pi_each=po, pooled_mean=round(float(np.mean(po)), 3)))
    if 'ceiling' not in have:
        tasks = sorted({e['task'] for e in E})
        res = dict(label='ceiling only: leave-one-task-out over the cover events')
        y2 = np.array([CI[e['kind']] for e in E])
        t2 = np.array([tasks.index(e['task']) for e in E])
        one = np.ones(len(E))
        for name, lv in [('together', CHAIN)] + [('alone ' + f, v) for f, v in ALONE.items()]:
            bits = np.zeros(len(E))
            base = np.zeros(len(E))
            for i, t in enumerate(tasks):
                tr = t2 != i
                ft = Fit([e for e, x in zip(E, tr) if x], y2[tr], one[tr], lv)
                m0 = (ft.n0 + 1) / (ft.n0.sum() + 4)
                for j in np.flatnonzero(~tr):
                    bits[j] = -math.log2(ft.p(E[j])[y2[j]])
                    base[j] = -math.log2(m0[y2[j]])
            n = np.bincount(t2, minlength=len(tasks)).astype(float)
            res[name] = dict(bits_marginal=round(float(base.mean()), 3), bits_cond=round(float(bits.mean()), 3), saving_over_marginal=round(float((base - bits).mean()), 3), saving_over_marginal_range=ci(np.bincount(t2, base - bits, minlength=len(tasks)), n))
        emit('ceiling', res)
    with open(H + 'cells-map-leaf-stage.tsv', 'w', newline='') as f:
        wr = csv.writer(f, delimiter='\t')
        wr.writerow(['cell', 'events', 'tasks', 'thin'] + ['share_' + k for k in CLASSES] + ['entropy_in_cell', 'bits_now', 'bits_cond', 'saving'])
        by = collections.defaultdict(list)
        for e in E:
            by[e['leaf_kinds'] + '|' + e['stage']].append(e)
        for c in sorted(by):
            q = by[c]
            ts = len({e['task'] for e in q})
            k = np.array([CI[e['kind']] for e in q])
            sh = np.bincount(k, minlength=4) / len(q)
            ent = -sum(x * math.log2(x) for x in sh if x > 0)
            now = float((-np.log2(PI[k])).mean())
            cond = float(np.mean([-math.log2(together.p(e)[CI[e['kind']]]) for e in q]))
            wr.writerow([c, len(q), ts, int(len(q) < 50 or ts < 8)] + [round(float(x), 3) for x in sh] + [round(ent, 3), round(now, 3), round(cond, 3), round(now - cond, 3)])


main()
