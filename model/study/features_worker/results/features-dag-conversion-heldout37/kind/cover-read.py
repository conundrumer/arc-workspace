"""The cover events of cover-rows.tsv, with the scope fields the record has: scope_forms and resume. One JSON line per section in cover-reads.jsonl; a rerun skips finished sections.

The record has, per cover event: gold's kind, the visit's kind, the count of forms in the scope, whether the visit resumed, whether the scope held the gold form's read forms. It has no kinds or heads of scope forms.

  paid        bits under pi on gold's kind, per cover event, and how often the visit's kind was gold's kind
  size        the frozen fit's `size` chain, read on the event's scope_forms in the buckets of scope_facts.py; and a leave-one-task-out fit of kind on those buckets over the events, labelled a ceiling

The size fit reads the non-held picks6 rows of gold-scope-rows.tsv (or .tsv.zst) of this folder, and it writes frozen-size-fit.json once. The section reads held events, so it stops unless the manifest of the record holds the sha256 of frozen-size-fit.json and scope_facts.py under `kind_frozen` (kind/record-frozen.py), and unless held-reads.jsonl of the record has no line `kind-cover_events`; it then adds that line. The ceiling in it fits on held events and is a ceiling only.
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
BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-base-cost-read-heldout37/'
OUT = H + 'cover-reads.jsonl'
SEED = 20261101
CLASSES = ('RULE', 'DET', 'INIT', 'RIGID_DET')
CI = {k: i for i, k in enumerate(CLASSES)}
PI = np.array([6413, 3468, 4297, 10], float)
PI /= PI.sum()
M_ = 8.0
R_DIR = H.rsplit('/kind/', 1)[0] + '/'
LEDGER = R_DIR + 'held-reads.jsonl'
have = {json.loads(l)['section'] for l in open(OUT)} if os.path.exists(OUT) else set()


def emit(n, v):
    out.write(json.dumps(dict(section=n, value=v)) + '\n')
    out.flush()
    print(n, json.dumps(v)[:2500], flush=True)


def bucket(size):
    return next(name for lim, name in ((0, '0'), (1, '1'), (2, '2'), (4, '3-4'), (8, '5-8'), (16, '9-16'), (1 << 40, '17+')) if size <= lim)


def check_complete(have_tasks):
    """The rows of build-gold-rows.py are whole when every task of its column-types cache has rows. A fit on partial rows stops, unless KIND_PARTIAL=1 (a pilot)."""
    want = {tuple(k.split(' ')[:2]) for k in json.load(open(H + 'column-types-cache.json'))}
    miss = want - have_tasks
    if miss and os.environ.get('KIND_PARTIAL') != '1':
        sys.exit('refused: gold-scope-rows.tsv lacks %d of %d tasks; build-gold-rows.py has not finished (KIND_PARTIAL=1 allows a pilot)' % (len(miss), len(want)))


def freeze_size():
    """frozen-size-fit.json: non-held picks6 counts of kind by size, each form with weight 1 over its replicates."""
    if os.path.exists(H + 'gold-scope-rows.tsv'):
        src = open(H + 'gold-scope-rows.tsv')
    else:
        src = subprocess.Popen(['zstd', '-dc', H + 'gold-scope-rows.tsv.zst'], stdout=subprocess.PIPE, text=True).stdout
    allrows = list(csv.DictReader(src, delimiter='\t'))
    check_complete({(r['split'], r['task']) for r in allrows})
    rows = [r for r in allrows if r['split'] == 'nonheld' and r['rule'] == 'picks6' and r['kind'] in CI]
    w = collections.Counter((r['task'], r['form']) for r in rows)
    c = collections.defaultdict(lambda: [0.0] * 4)
    n = [0.0] * 4
    for r in rows:
        x = 1 / w[r['task'], r['form']]
        c[r['size']][CI[r['kind']]] += x
        n[CI[r['kind']]] += x
    json.dump(dict(n0=n, cells=c), open(H + 'frozen-size-fit.json', 'w'))


def sha(path):
    import hashlib
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def held_gate(name):
    """Stops unless the frozen files have their hashes in the manifest and the ledger has no line of this name; then adds the line."""
    fz = json.load(open(R_DIR + 'manifest.json')).get('kind_frozen', {})
    for f in ('frozen-size-fit.json', 'scope_facts.py'):
        if fz.get(f) != sha(H + f):
            sys.exit('refused %s: manifest.json has no kind_frozen hash of %s that equals the file' % (name, f))
    if os.path.exists(LEDGER) and any(json.loads(l).get('name') == name for l in open(LEDGER) if l.strip()):
        sys.exit('refused %s: held-reads.jsonl has a line of that name' % name)
    with open(LEDGER, 'a') as f:
        f.write(json.dumps(dict(name=name, group='kind', arm='frozen-size', tier='scope', control=False, time=time.strftime('%Y-%m-%dT%H:%M:%S'))) + '\n')


if not os.path.exists(H + 'frozen-size-fit.json'):
    freeze_size()
if 'cover_events' not in have:
    held_gate('kind-cover_events')
out = open(OUT, 'a')
R = [r for r in csv.DictReader(open(BASE + 'cover-rows.tsv'), delimiter='\t') if r['scope_forms'] != '']
all_rows = sum(1 for _ in csv.DictReader(open(BASE + 'cover-rows.tsv'), delimiter='\t'))


def ci(s, n):
    i = np.random.default_rng(SEED).integers(0, len(s), (2000, len(s)))
    v = s[i].sum(1) / np.maximum(n[i].sum(1), 1e-12)
    return [round(float(np.quantile(v, .025)), 3), round(float(np.quantile(v, .975)), 3)]


def read(rows, label):
    tasks = sorted({r['task'] for r in rows})
    ti = {t: i for i, t in enumerate(tasks)}
    t = np.array([ti[r['task']] for r in rows])
    y = np.array([CI[r['kind']] for r in rows])
    size = np.array([bucket(int(r['scope_forms'])) for r in rows])
    n = np.bincount(t, minlength=len(tasks)).astype(float)
    now = -np.log2(PI[y])
    res = dict(events=len(rows), tasks=len(tasks), kinds={k: int((y == CI[k]).sum()) for k in CLASSES}, bits_now=round(float(now.mean()), 3), bits_now_range=ci(np.bincount(t, now, minlength=len(tasks)), n),
               share_visit_kind_is_gold_kind=round(float(np.mean([r['visit_kind'] == r['kind'] for r in rows])), 3), share_resumed=round(float(np.mean([r['resume'] == '1' for r in rows])), 3), share_held=round(float(np.mean([r['held'] == '1' for r in rows])), 3),
               scope_forms_quantiles=[float(x) for x in np.quantile([int(r['scope_forms']) for r in rows], [.1, .5, .9])], size_buckets=dict(collections.Counter(size.tolist())))
    # the frozen fit's size chain
    fz = json.load(open(H + 'frozen-size-fit.json'))
    n0 = np.array(fz['n0'])
    p0 = (n0 + 1) / (n0.sum() + 4)
    P = np.zeros((len(rows), 4))
    for i, b in enumerate(size):
        c = np.array(fz['cells'].get(b, [0, 0, 0, 0]))
        P[i] = (c + M_ * p0) / (c.sum() + M_)
    bits = -np.log2(P[np.arange(len(rows)), y])
    res['frozen_size'] = dict(bits_cond=round(float(bits.mean()), 3), saving=round(float((now - bits).mean()), 3), saving_range=ci(np.bincount(t, now - bits, minlength=len(tasks)), n))
    for k in ('RULE',):
        m = y == CI[k]
        nk = np.bincount(t, m.astype(float), minlength=len(tasks))
        res['frozen_size_' + k] = dict(bits_now=round(float(now[m].mean()), 3), bits_cond=round(float(bits[m].mean()), 3), saving_range=ci(np.bincount(t, (now - bits) * m, minlength=len(tasks)), nk))
    # leave one task out over the events: marginal, and size
    T = np.zeros((len(tasks), 4))
    np.add.at(T, (t, y), 1.0)
    nl = T.sum(0) - T[t]
    pm = (nl + 1) / (nl.sum(1, keepdims=True) + 4)
    cells, c = np.unique(size, return_inverse=True)
    N = np.zeros((len(cells), 4))
    np.add.at(N, (c, y), 1.0)
    Q = np.zeros((len(tasks), len(cells), 4))
    np.add.at(Q, (t, c, y), 1.0)
    nc = N[c] - Q[t, c]
    pc = (nc + M_ * pm) / (nc.sum(1, keepdims=True) + M_)
    bm = -np.log2(pm[np.arange(len(rows)), y])
    bc = -np.log2(pc[np.arange(len(rows)), y])
    res['ceiling_loto'] = dict(label='ceiling only: leave-one-task-out on these events', bits_marginal=round(float(bm.mean()), 3), bits_size=round(float(bc.mean()), 3), saving_over_marginal=round(float((bm - bc).mean()), 3), saving_over_marginal_range=ci(np.bincount(t, bm - bc, minlength=len(tasks)), n))
    return res


if 'cover_events' not in have:
    emit('cover_events', {'rows_in_file': all_rows, 'rows_with_a_visit': len(R), 'base all': read([r for r in R if r['arm'].startswith('base')], 'base'), 'base first': read([r for r in R if r['arm'].startswith('base') and r['first'] == '1'], 'first'), 'base no resume': read([r for r in R if r['arm'].startswith('base') and r['resume'] == '0'], 'nr'), 'all arms': read(R, 'all')})
