"""The fit of kind given scope contents, and its reads, on facts of a scope as a set (scope_facts.py of this folder; no fact reads the order of a scope or of a form's text). Each section writes one JSON line to reads.jsonl as soon as it has it, and a rerun skips finished sections.

  features_dagc_env.sh 1 kind/fit-read.py [SECTION ...]        (or the venv python of work/lm: numpy, sklearn)

Sections that read non-held rows run by default. The sections that read held rows (held_read, held_cells, held_control, held_loto_ceiling, secondary_held) run only when named. Each one stops unless the manifest of the record holds the sha256 of frozen-fit.json and scope_facts.py under `kind_frozen` (kind/record-frozen.py writes them), and unless held-reads.jsonl of the record has no line of its name; it then adds that line before it loads a held row. held_loto_ceiling and the ceiling of cover-read.py and read-map.py fit on held events; they are ceilings only, and no number in them goes to a model.

Fixed before any read:
  classes     RULE, DET, INIT, RIGID_DET, the kinds a pool draws. A gold form of another kind is left out as a target and stays in scopes.
  now         pi(k) = (corpus count + 1) / sum, the weights of Pool.kind under models-base, with every kind admitted
  smoothing   a chain of levels, each a tuple of facts. L0, the marginal: (n_k + 1) / (n + 4). Level i: (n_k + m p_(i-1)(k)) / (n + m), m = 8, n in forms: a form's replicate scopes share a weight of 1.
  together    chain leaf_kinds; leaf_kinds stage size; + kinds; + ident key; + leaves; + leaf_heads leaf_cols
  fact alone  the chain of that one fact
  heads       the 16 commonest head names of non-held forms, others `other`. A leaf_heads cell holds the sorted set of its heads mapped so.
  interval    2,000 task resamples, seed 20261101, 2.5% and 97.5% quantiles. On a held read the fit stays fixed.
  control     non-held kinds permuted across forms, 20 permutations, the fit and read repeated; held LOTO with held kinds permuted the same way
  thin        a cell with under 50 forms or under 8 tasks

Units:
  per form    mean of -log2 P(gold's kind) over forms, unweighted
  pooled      the `kind` term of decompose.py: log2(W held / W held in the form's kind), W summing 2^(-s bits) x exposure over forms with a table of their own in the base arms. A conditional replaces a form's right-kind share of held exposure by P(gold's kind).
"""
import collections
import csv
import json
import math
import os
import subprocess
import sys
import time

import numpy as np

H = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, H)
import scope_facts as F  # noqa: E402

BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-base-cost-read-heldout37/'
OUT = H + 'reads.jsonl'
SEED = 20261101
CLASSES = ('RULE', 'DET', 'INIT', 'RIGID_DET')
CI = {k: i for i, k in enumerate(CLASSES)}
W_NOW = dict(RULE=6412, DET=3467, INIT=4296, RIGID_DET=9)
PI = np.array([W_NOW[k] + 1 for k in CLASSES], float)
PI /= PI.sum()
M_ = 8.0
BOOT = 2000
CHAIN = [('leaf_kinds',), ('leaf_kinds', 'stage', 'size'), ('leaf_kinds', 'stage', 'size', 'kinds'), ('leaf_kinds', 'stage', 'size', 'kinds', 'ident', 'key'), ('leaf_kinds', 'stage', 'size', 'kinds', 'ident', 'key', 'leaves'), ('leaf_kinds', 'stage', 'size', 'kinds', 'ident', 'key', 'leaves', 'leaf_cols', 'leaf_heads')]
ALONE = {f: [(f,)] for f in F.FACTS}
S_FIXED = dict(any=0.30, RULE=0.30, DET=0.50, INIT=0.12)
SECTIONS = sys.argv[1:]  # sections to run; none means every section that reads no held row
R_DIR = H.rsplit('/kind/', 1)[0] + '/'
LEDGER = R_DIR + 'held-reads.jsonl'

have = {json.loads(l)['section'] for l in open(OUT)} if os.path.exists(OUT) else set()
out = open(OUT, 'a')


def emit(name, value):
    out.write(json.dumps(dict(section=name, value=value)) + '\n')
    out.flush()
    print('section', name, 'done', round(time.time() - T0, 1), 's', flush=True)


def want(name):
    return name not in have and (not SECTIONS or name in SECTIONS)


T0 = time.time()


def read_rows():
    path = H + 'gold-scope-rows.tsv'
    if os.path.exists(path):
        src = open(path)
    else:
        src = subprocess.Popen(['zstd', '-dc', path + '.zst'], stdout=subprocess.PIPE, text=True).stdout
    return csv.DictReader(src, delimiter='\t')


heads = collections.Counter()
for r in csv.DictReader(open(H + 'gold-form-rows.tsv'), delimiter='\t'):
    if r['split'] == 'nonheld' and r['head'] != 'None':
        heads[r['head']] += 1
HEADS = sorted(x for x, _ in heads.most_common(16))
assert not any('+' in x for x in HEADS)


def norm_fact(k, v):
    """leaf_heads: the set of heads with the names outside HEADS as `other`, sorted."""
    if k != 'leaf_heads' or v == 'none':
        return v
    return '+'.join(sorted({h if h in HEADS else 'other' for h in v.split('+')}))


def sha(path):
    import hashlib
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def held_gate(name):
    """Stops unless the frozen files have their hashes in the manifest and the ledger has no line of this name; then adds the line."""
    fz = json.load(open(R_DIR + 'manifest.json')).get('kind_frozen', {})
    for f in ('frozen-fit.json', 'scope_facts.py'):
        if not os.path.exists(H + f) or fz.get(f) != sha(H + f):
            sys.exit('refused %s: manifest.json has no kind_frozen hash of %s that equals the file' % (name, f))
    if os.path.exists(LEDGER) and any(json.loads(l).get('name') == name for l in open(LEDGER) if l.strip()):
        sys.exit('refused %s: held-reads.jsonl has a line of that name' % name)
    with open(LEDGER, 'a') as f:
        f.write(json.dumps(dict(name=name, group='kind', arm='frozen-chain', tier='scope', control=name.endswith('control'), time=time.strftime('%Y-%m-%dT%H:%M:%S'))) + '\n')


class Data:
    """Rows of one split and scope rule."""

    def __init__(self, rows):
        self.task = np.array([r['task'] for r in rows])
        self.form = np.array([int(r['form']) for r in rows])
        self.y = np.array([CI[r['kind']] for r in rows])
        cnt = collections.Counter((r['task'], r['form']) for r in rows)
        self.w = np.array([1.0 / cnt[r['task'], r['form']] for r in rows])
        self.tasks, self.ti = np.unique(self.task, return_inverse=True)
        self.f = {k: np.array([norm_fact(k, r[k]) for r in rows], dtype=object) for k in F.FACTS}
        self.n = len(rows)
        u, inv = np.unique(np.char.add(np.char.add(self.task.astype(str), ' '), self.form.astype(str)), return_inverse=True)
        self.fi, self.nforms = inv, len(u)

    def key(self, level):
        s = self.f[level[0]].astype(str)
        for k in level[1:]:
            s = np.char.add(np.char.add(s, '|'), self.f[k].astype(str))
        return s


def fit_read(tr, te, levels, y=None):
    """P of te's rows over the classes, fit on tr."""
    y = tr.y if y is None else y
    N0 = np.zeros(4)
    np.add.at(N0, y, tr.w)
    P = np.tile((N0 + 1) / (N0.sum() + 4), (te.n, 1))
    for lv in levels:
        cells, inv = np.unique(np.concatenate([tr.key(lv), te.key(lv)]), return_inverse=True)
        a, b = inv[:tr.n], inv[tr.n:]
        N = np.zeros((len(cells), 4))
        np.add.at(N, (a, y), tr.w)
        n = N[b]
        P = (n + M_ * P) / (n.sum(1, keepdims=True) + M_)
    return P


def loto(d, levels, y=None):
    """P of d's rows, each from the rows of the other tasks."""
    y = d.y if y is None else y
    nt = len(d.tasks)
    T = np.zeros((nt, 4))
    np.add.at(T, (d.ti, y), d.w)
    n0 = T.sum(0) - T[d.ti]
    P = (n0 + 1) / (n0.sum(1, keepdims=True) + 4)
    for lv in levels:
        cells, c = np.unique(d.key(lv), return_inverse=True)
        N = np.zeros((len(cells), 4))
        np.add.at(N, (c, y), d.w)
        tc = c.astype(np.int64) * nt + d.ti
        ut, tci = np.unique(tc, return_inverse=True)
        Q = np.zeros((len(ut), 4))
        np.add.at(Q, (tci, y), d.w)
        n = N[c] - Q[tci]
        n = np.clip(n, 0, None)
        P = (n + M_ * P) / (n.sum(1, keepdims=True) + M_)
    return P


def by_task(d, values, mask=None):
    w = d.w if mask is None else d.w * mask
    return np.bincount(d.ti, w * values, minlength=len(d.tasks)), np.bincount(d.ti, w, minlength=len(d.tasks))


RNG = np.random.default_rng(SEED)
DRAWS = None


def draws(nt):
    return np.random.default_rng(SEED).integers(0, nt, (BOOT, nt))


def ci_mean(s, n):
    """95% range of sum s over sum n, resampling tasks."""
    i = draws(len(s))
    v = s[i].sum(1) / np.maximum(n[i].sum(1), 1e-12)
    return [round(float(np.quantile(v, .025)), 3), round(float(np.quantile(v, .975)), 3)]


def per_form(d, P, y=None, marg=None):
    """Bits under now, under the conditional, under the marginal where given: all forms and per class, with ranges."""
    y_true = d.y if y is None else y
    p = P[np.arange(d.n), y_true]
    bits = -np.log2(np.maximum(p, 1e-12))
    now = -np.log2(PI[y_true])
    res = {}
    full = (d.f['leaf_kinds'] != 'none').astype(float)  # the empty scope: a form that reads nothing with a `cut` of no forms, or the first form of a program; a live search gives it about 1.4% of its tries
    for name, mask in [('any', np.ones(d.n))] + [(k, (y_true == CI[k]).astype(float)) for k in CLASSES[:3]] + [('any nonempty', full)] + [(k + ' nonempty', (y_true == CI[k]) * full) for k in CLASSES[:3]]:
        s, n = by_task(d, now - bits, mask)
        c, _ = by_task(d, bits, mask)
        a, _ = by_task(d, now, mask)
        q = dict(forms=round(float(n.sum()), 1), tasks=int((n > 0).sum()), bits_now=round(float(a.sum() / n.sum()), 3), bits_cond=round(float(c.sum() / n.sum()), 3), bits_cond_range=ci_mean(c, n), saving=round(float(s.sum() / n.sum()), 3), saving_range=ci_mean(s, n))
        if marg is not None:
            pm = marg[np.arange(d.n), y_true]
            bm = -np.log2(np.maximum(pm, 1e-12))
            sm, _ = by_task(d, bm - bits, mask)
            b0, _ = by_task(d, bm, mask)
            q.update(bits_marginal=round(float(b0.sum() / n.sum()), 3), saving_over_marginal=round(float(sm.sum() / n.sum()), 3), saving_over_marginal_range=ci_mean(sm, n))
        res[name] = q
    return res


def form_rows():
    rows = []
    for r in csv.DictReader(open(BASE + 'form-rows.tsv'), delimiter='\t'):
        if r['bits'] in ('', 'None') or r['own_key'] != '1' or not r['arm'].startswith('base'):
            continue
        rows.append(dict(arm=r['arm'], task=r['task'], form=int(r['form']), kind=r['kind'], bits=float(r['bits']), ek=int(r['e_hk']), eh=int(r['e_hk']) + int(r['e_hx']), nreads=int(r['nreads'])))
    return rows


def pooled(d, P, frows):
    """The kind term at fixed s, actual, under pi, under P, with ranges, per group."""
    p = P[np.arange(d.n), d.y]
    S = np.bincount(d.fi, d.w * p, minlength=d.nforms)
    ids = {}
    for i in range(d.n):
        ids[d.task[i], int(d.form[i])] = d.fi[i]
    tasks = sorted({r['task'] for r in frows})
    ti = {t: i for i, t in enumerate(tasks)}
    res = {}
    groups = [(k, k, None, False) for k in S_FIXED] + [(k + ' reads', k, True, False) for k in ('any', 'RULE')] + [(k + ' no reads', k, False, False) for k in ('any', 'RULE')] + [(k + ' no-read forms at pi', k, None, True) for k in ('any', 'RULE')]
    for label, name, reads, hold in groups:
        s = S_FIXED[name]
        R = [r for r in frows if (name == 'any' or r['kind'] == name) and r['kind'] in CI and (reads is None or (r['nreads'] > 0) == reads)]
        t = np.array([ti[r['task']] for r in R])
        w = np.array([2.0 ** (-s * r['bits']) for r in R])
        eh = np.array([r['eh'] for r in R], float)
        ek = np.array([r['ek'] for r in R], float)
        pi = np.array([PI[CI[r['kind']]] for r in R])
        pc = np.array([PI[CI[r['kind']]] if hold and r['nreads'] == 0 else S[ids[r['task'], r['form']]] for r in R])
        A = [np.bincount(t, w * x, minlength=len(tasks)) for x in (eh, ek, eh * pi, eh * pc)]
        i = draws(len(tasks))

        def terms(u):
            h, k, a, c = u
            return np.log2(h / k), np.log2(h / a), np.log2(h / c)
        x = terms([q.sum() for q in A])
        b = np.array(terms([q[i].sum(1) for q in A]))
        q = lambda v: [round(float(np.nanquantile(v, .025)), 3), round(float(np.nanquantile(v, .975)), 3)]  # noqa: E731
        res[label] = dict(rows=len(R), s=s, kind_actual=round(float(x[0]), 3), kind_actual_range=q(b[0]), kind_under_pi=round(float(x[1]), 3), kind_cond=round(float(x[2]), 3), kind_cond_range=q(b[2]), saving_vs_actual=round(float(x[0] - x[2]), 3), saving_vs_actual_range=q(b[0] - b[2]), saving_vs_pi=round(float(x[1] - x[2]), 3), saving_vs_pi_range=q(b[1] - b[2]))
    return res


def cells(path, d, Pcond, level):
    """One row per cell of level: forms, tasks, thin mark, kind shares, plug-in entropy, bits now, bits under the conditional."""
    key = d.key(level)
    p = Pcond[np.arange(d.n), d.y]
    with open(path, 'w', newline='') as f:
        wr = csv.writer(f, delimiter='\t')
        wr.writerow(['cell', 'forms', 'tasks', 'thin'] + ['share_' + k for k in CLASSES] + ['entropy_in_cell', 'bits_now', 'bits_cond', 'saving'])
        for c in np.unique(key):
            m = key == c
            w = d.w[m]
            n = w.sum()
            tasks = len(set(d.task[m]))
            sh = np.bincount(d.y[m], w, minlength=4) / n
            ent = -sum(x * math.log2(x) for x in sh if x > 0)
            now = float((w * -np.log2(PI[d.y[m]])).sum() / n)
            cond = float((w * -np.log2(p[m])).sum() / n)
            wr.writerow([c, round(n, 1), tasks, int(n < 50 or tasks < 8)] + [round(float(x), 3) for x in sh] + [round(ent, 3), round(now, 3), round(cond, 3), round(now - cond, 3)])


def entropy_of_cells(d, level):
    """Plug-in entropy of kind given level, in-sample, over all cells and over cells that aren't thin, with the forms in each."""
    key = d.key(level)
    tot = n_ok = h_all = h_ok = 0.0
    for c in np.unique(key):
        m = key == c
        w = d.w[m]
        n = w.sum()
        sh = np.bincount(d.y[m], w, minlength=4) / n
        e = -sum(x * math.log2(x) for x in sh if x > 0)
        tot += n
        h_all += n * e
        if n >= 50 and len(set(d.task[m])) >= 8:
            n_ok += n
            h_ok += n * e
    return dict(cells=len(np.unique(key)), plug_in_all=round(h_all / tot, 3), plug_in_not_thin=round(h_ok / max(n_ok, 1e-9), 3), forms_not_thin_share=round(n_ok / tot, 3))


def check_complete(have_tasks):
    """The rows of build-gold-rows.py are whole when every task of its column-types cache has rows. A fit on partial rows stops, unless KIND_PARTIAL=1 (a pilot)."""
    want = {tuple(k.split(' ')[:2]) for k in json.load(open(H + 'column-types-cache.json'))}
    miss = want - have_tasks
    if miss and os.environ.get('KIND_PARTIAL') != '1':
        sys.exit('refused: gold-scope-rows.tsv lacks %d of %d tasks; build-gold-rows.py has not finished (KIND_PARTIAL=1 allows a pilot)' % (len(miss), len(want)))


# ---- rows
HELD = [s for s in ('held_read', 'held_cells', 'held_control', 'held_loto_ceiling') if s in SECTIONS and s not in have]
SEC_HELD = 'secondary_held' in SECTIONS and 'secondary_held' not in have
for s in HELD + (['secondary_held'] if SEC_HELD else []):
    held_gate('kind-' + s)  # before a held row is loaded
by = collections.defaultdict(list)
seen_tasks = set()
for r in read_rows():
    seen_tasks.add((r['split'], r['task']))
    if r['split'] == 'held' and not (HELD or SEC_HELD):
        continue
    if r['kind'] in CI:
        by[r['split'], r['rule']].append(r)
check_complete(seen_tasks)
print('rows', {k: len(v) for k, v in by.items()}, round(time.time() - T0, 1), 's', flush=True)
D = Data(by['nonheld', 'picks6'])
RULES = {k[1]: Data(v) for k, v in by.items() if k[0] == 'nonheld'}
print('data ready', round(time.time() - T0, 1), 's', flush=True)


def permuted(d, seed):
    """Kinds permuted across forms, one kind per form: a form's replicate rows share it."""
    rng = np.random.default_rng(seed)
    fy = np.zeros(d.nforms, int)
    fy[d.fi] = d.y
    return rng.permutation(fy)[d.fi]


if want('baseline'):
    emit('baseline', dict(pi=dict(zip(CLASSES, np.round(PI, 4).tolist())), bits_at_pi={k: round(float(-math.log2(PI[CI[k]])), 3) for k in CLASSES}, heads=HEADS, chain=CHAIN, m=M_,
                          nonheld=dict(rows=D.n, forms=D.nforms, tasks=len(D.tasks), kind_forms={k: round(float(D.w[D.y == CI[k]].sum()), 1) for k in CLASSES}, entropy_marginal=round(float(-(lambda s: (s * np.log2(s)).sum())(np.bincount(D.y, D.w, minlength=4) / D.w.sum())), 3))))

if want('nonheld_loto'):
    res = {}
    M0 = loto(D, [])
    for name, lv in [('together', CHAIN)] + [('upto ' + '+'.join(CHAIN[i][len(CHAIN[i - 1]) if i else 0:]), CHAIN[:i + 1]) for i in range(len(CHAIN) - 1)] + [('alone ' + k, v) for k, v in ALONE.items()]:
        res[name] = per_form(D, loto(D, lv), marg=M0)
    res['plug_in'] = {'+'.join(CHAIN[i]): entropy_of_cells(D, CHAIN[i]) for i in range(len(CHAIN))}
    emit('nonheld_loto', res)

if want('freeze'):
    fz = dict(heads=HEADS, m=M_, chain=CHAIN, classes=CLASSES, n0=np.round(np.bincount(D.y, D.w, minlength=4), 6).tolist(), levels=[])
    for lv in CHAIN:
        cells_, inv = np.unique(D.key(lv), return_inverse=True)
        N = np.zeros((len(cells_), 4))
        np.add.at(N, (inv, D.y), D.w)
        fz['levels'].append({str(c): np.round(N[i], 6).tolist() for i, c in enumerate(cells_)})
    json.dump(fz, open(H + 'frozen-fit.json', 'w'))
    emit('freeze', dict(file='frozen-fit.json', cells=[len(x) for x in fz['levels']]))

if want('nonheld_rules'):
    res = {}
    for rule, d in RULES.items():
        res[rule] = per_form(d, loto(d, CHAIN), marg=loto(d, []))
    emit('nonheld_rules', res)

if want('nonheld_control'):
    got, last = [], None
    for i in range(20):
        y = permuted(D, SEED + i)
        P = loto(D, CHAIN, y)
        M0 = loto(D, [], y)
        q = per_form(D, P, y, M0)
        got.append(q['any']['saving_over_marginal'])
        last = last or q
    emit('nonheld_control', dict(first=last, saving_over_marginal_each=got, mean=round(float(np.mean(got)), 3), low=min(got), high=max(got)))

if want('nonheld_cells'):
    P = loto(D, CHAIN)
    cells(H + 'cells-nonheld-leaf-stage.tsv', D, P, ('leaf_kinds', 'stage'))
    cells(H + 'cells-nonheld-together.tsv', D, P, CHAIN[-1])
    emit('nonheld_cells', dict(files=['cells-nonheld-leaf-stage.tsv', 'cells-nonheld-together.tsv']))

if HELD:
    H_ = Data(by['held', 'picks6'])
    FR = form_rows()
    dropped = sum(r['kind'] not in CI for r in FR)
    if 'held_read' in HELD:
        res = dict(rows=H_.n, forms=H_.nforms, tasks=len(H_.tasks), kind_forms={k: round(float(H_.w[H_.y == CI[k]].sum()), 1) for k in CLASSES}, form_rows_not_a_class=dropped)
        M0 = fit_read(D, H_, [])
        for name, lv in [('together', CHAIN)] + [('upto ' + '+'.join(CHAIN[i][len(CHAIN[i - 1]) if i else 0:]), CHAIN[:i + 1]) for i in range(len(CHAIN) - 1)] + [('alone ' + k, v) for k, v in ALONE.items()]:
            P = fit_read(D, H_, lv)
            res[name] = dict(per_form=per_form(H_, P, marg=M0), pooled=pooled(H_, P, FR))
        res['marginal'] = dict(pooled=pooled(H_, M0, FR))
        res['perfect'] = 'kind term at zero'
        emit('held_read', res)
    if 'held_cells' in HELD:
        P = fit_read(D, H_, CHAIN)
        cells(H + 'cells-held-leaf-stage.tsv', H_, P, ('leaf_kinds', 'stage'))
        cells(H + 'cells-held-together.tsv', H_, P, CHAIN[-1])
        emit('held_cells', dict(files=['cells-held-leaf-stage.tsv', 'cells-held-together.tsv'], plug_in={'+'.join(CHAIN[i]): entropy_of_cells(H_, CHAIN[i]) for i in range(len(CHAIN))}))
    if 'held_control' in HELD:
        pf, po = [], []
        first = None
        M0 = fit_read(D, H_, [])
        for i in range(20):
            y = permuted(D, SEED + i)
            P = fit_read(D, H_, CHAIN, y)
            q = dict(per_form=per_form(H_, P, marg=M0), pooled=pooled(H_, P, FR))
            first = first or q
            pf.append(q['per_form']['any']['saving_over_marginal'])
            po.append(q['pooled']['any']['saving_vs_actual'])
        emit('held_control', dict(first=first, per_form_saving_over_marginal_each=pf, mean=round(float(np.mean(pf)), 3), pooled_saving_vs_actual_each=po, pooled_mean=round(float(np.mean(po)), 3)))
    if 'held_loto_ceiling' in HELD:
        P = loto(H_, CHAIN)
        M0 = loto(H_, [])
        res = dict(label='ceiling only: leave-one-task-out on held rows', together=dict(per_form=per_form(H_, P, marg=M0), pooled=pooled(H_, P, FR)))
        for name, lv in ALONE.items():
            Q = loto(H_, lv)
            res['alone ' + name] = dict(per_form=per_form(H_, Q, marg=M0), pooled=pooled(H_, Q, FR))
        got = []
        for i in range(20):
            y = permuted(H_, SEED + i)
            got.append(per_form(H_, loto(H_, CHAIN, y), y, loto(H_, [], y))['any']['saving_over_marginal'])
        res['control_saving_over_marginal_each'] = got
        res['control_mean'] = round(float(np.mean(got)), 3)
        emit('held_loto_ceiling', res)


# ---- second estimator: gradient boosted trees over the same facts, fixed settings, to check the chain doesn't lose signal by its cells
TOP = {}
def hgb_x(d, tabs):
    # the trees take at most 255 values per fact, so all but the 254 commonest values of a fact share one code
    out = []
    for k in F.FACTS:
        code = np.searchsorted(tabs[k], d.f[k].astype(str))
        common = TOP.setdefault(k, np.argsort(-np.bincount(code, minlength=len(tabs[k])))[:254])
        back = np.full(len(tabs[k]), 254)
        back[common] = np.arange(len(common))
        out.append(back[code])
    return np.column_stack(out)


def hgb_fit(X, y, w):
    from sklearn.ensemble import HistGradientBoostingClassifier as G
    m = G(max_iter=150, learning_rate=.1, max_leaf_nodes=15, min_samples_leaf=200, categorical_features=list(range(len(F.FACTS))), early_stopping=False, random_state=SEED)
    return m.fit(X, y, sample_weight=w)


def hgb_p(m, X):
    q = m.predict_proba(X)
    P = np.full((len(X), 4), 1e-4)
    P[:, m.classes_] = q
    return P / P.sum(1, keepdims=True)


if want('secondary_nonheld') or SEC_HELD:
    if SEC_HELD:
        held_d = Data(by['held', 'picks6'])
        tabs = {k: np.unique(np.concatenate([D.f[k].astype(str), held_d.f[k].astype(str)])) for k in F.FACTS}
    else:
        tabs = {k: np.unique(D.f[k].astype(str)) for k in F.FACTS}
    X = hgb_x(D, tabs)
    if want('secondary_nonheld'):
        P = np.zeros((D.n, 4))
        fold = np.random.default_rng(SEED).integers(0, 5, len(D.tasks))[D.ti]
        for i in range(5):
            t1 = time.time()
            m = hgb_fit(X[fold != i], D.y[fold != i], D.w[fold != i])
            P[fold == i] = hgb_p(m, X[fold == i])
            print('fold', i, round(time.time() - t1, 1), 's', flush=True)
        emit('secondary_nonheld', per_form(D, P, marg=loto(D, [])))
    if SEC_HELD:
        FR = form_rows()
        m = hgb_fit(X, D.y, D.w)
        P = hgb_p(m, hgb_x(held_d, tabs))
        emit('secondary_held', dict(per_form=per_form(held_d, P, marg=fit_read(D, held_d, [])), pooled=pooled(held_d, P, FR)))
