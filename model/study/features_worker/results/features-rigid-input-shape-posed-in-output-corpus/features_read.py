"""Measures over the rows of features_shape_posed.py.

Tasks whose output is, or holds, a D4 image of the whole input in some train pair are set apart: they leave every group and have a column of their own.

For each form:
  rates per group, and the same-pose rate;
  AUC of RIGID_DET tasks against plain, by the boolean and by the graded scores (pairs: share of train pairs with a hit; size: largest hit shape; share: classes hit over classes copied);
  bits, log2(precision / base rate) over the positive and plain tasks, at recall .5 and at the best bar with recall at least .3, each on the score with the highest AUC of the form among the three graded scores and the boolean;
  a 95% interval from a task-level bootstrap, stratified by group, with the bar set again in each resample;
  control: the same rates, with outputs from another plain task of matching size, mean over draws.

Two positive sets: "pos" is the RIGID_DET tasks with several poses, "all" adds the one-pose tasks.

  features_read.py OUT.json ROWS...
"""
import collections
import json
import math
import sys

import numpy as np

OUT = sys.argv[1]
rows = []
for p in sys.argv[2:]:
    rows += [json.loads(x) for x in open(p)]
seen = set()
rows = [r for r in rows if not (r['task'] in seen or seen.add(r['task']))]
names = list(rows[0]['forms'])
SCORES = dict(bool=lambda v: v[0], pairs=lambda v: v[2], size=lambda v: v[3], share=lambda v: (v[4] / v[5] if v[5] else 0))


def is_whole(r):
    return r['whole'][0] + r['whole'][1] > 0


kept = [r for r in rows if not is_whole(r)]
apart = [r for r in rows if is_whole(r)]
groups = collections.defaultdict(list)
for r in kept:
    groups[r['group']].append(r)
print('rows', len(rows), 'kept', len(kept), 'set apart', len(apart), {k: len(v) for k, v in groups.items()}, flush=True)
print('set apart by group', collections.Counter(r['group'] for r in apart), 'output is image', sum(r['whole'][0] > 0 for r in apart), 'holds', sum(r['whole'][1] > 0 for r in apart))


def auc(a, b):
    """AUC of a over b, ties at half, by ranks."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if not len(a) or not len(b):
        return float('nan')
    allv = np.concatenate([a, b])
    u, inv = np.unique(allv, return_inverse=True)
    c = np.bincount(inv, minlength=len(u))
    rank = np.cumsum(c) - (c - 1) / 2
    return float((rank[inv[:len(a)]].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b)))


def bits_at(pos, neg, min_recall, mode):
    """Bits at a recall bar. mode 'first': the highest bar with recall at least min_recall. mode 'best': the bar with most bits among those. None where no bar reaches it."""
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    base = len(pos) / (len(pos) + len(neg))
    best = None
    for bar in sorted({x for x in pos if x > 0}, reverse=True):
        tp, fp = int((pos >= bar).sum()), int((neg >= bar).sum())
        if tp / len(pos) < min_recall:
            continue
        b = math.log2(tp / (tp + fp) / base)
        got = (b, bar, tp, fp)
        if mode == 'first':
            return got
        if best is None or b > best[0]:
            best = got
    return best


def boot(pos, neg, f, n=1000, seed=7):
    rng = np.random.default_rng(seed)
    out = []
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    for _ in range(n):
        p = pos[rng.integers(0, len(pos), len(pos))]
        q = neg[rng.integers(0, len(neg), len(neg))]
        out.append(f(p, q))
    return out


def ci(xs):
    a = [0.0 if x is None else x for x in xs]
    return round(float(np.percentile(a, 2.5)), 3), round(float(np.percentile(a, 97.5)), 3)


result = {}
PLAIN = groups['plain']
sets = dict(pos=groups['positive'], all=groups['positive'] + groups['one-pose'])
for n in names:
    e = dict(rate={g: [sum(r['forms'][n][0] for r in v), len(v)] for g, v in groups.items()},
             same={g: [sum(r['forms'][n][1] for r in v), len(v)] for g, v in groups.items()},
             apart=[sum(r['forms'][n][0] for r in apart), len(apart)])
    e['control'] = {g: round(float(np.mean([np.mean([d[0] for d in r['control'][n]]) for r in v])), 4) for g, v in groups.items()}
    e['control_same'] = {g: round(float(np.mean([np.mean([d[1] for d in r['control'][n]]) for r in v])), 4) for g, v in groups.items()}
    for sname, S in sets.items():
        block = {}
        for sc, fn in SCORES.items():
            block['auc_' + sc] = round(auc([fn(r['forms'][n]) for r in S], [fn(r['forms'][n]) for r in PLAIN]), 3)
        bestsc = max(SCORES, key=lambda k: block['auc_' + k])
        fn = SCORES[bestsc]
        p, q = [fn(r['forms'][n]) for r in S], [fn(r['forms'][n]) for r in PLAIN]
        block['score'] = bestsc
        block['auc_ci'] = ci(boot(p, q, auc))
        for key, rec, mode in (('r5', .5, 'first'), ('r3', .3, 'best')):
            got = bits_at(p, q, rec, mode)
            block[key] = None if got is None else [round(got[0], 3), got[1], got[2], got[3]]
            res = boot(p, q, lambda a, b, rec=rec, mode=mode: (lambda g: None if g is None else g[0])(bits_at(a, b, rec, mode)), n=400)
            block[key + '_ci'] = ci(res)
            block[key + '_none'] = sum(x is None for x in res) / len(res)
        block['control_auc'] = round(auc([np.mean([d[0] for d in r['control'][n]]) for r in S], [np.mean([d[0] for d in r['control'][n]]) for r in PLAIN]), 3)
        e[sname] = block
    result[n] = e
    print(f"{n:17s} " + ' '.join(f"{g[:4]} {x[0]}/{x[1]}" for g, x in e['rate'].items()) + f" | same " + ' '.join(f"{x[0]}" for x in e['same'].values()) +
          f" | ctrl pos {e['control'].get('positive', 0):.3f} plain {e['control'].get('plain', 0):.3f}" +
          f" | pos AUC {e['pos']['auc_' + e['pos']['score']]:.3f}({e['pos']['score']}) {e['pos']['auc_ci']} r5 {e['pos']['r5']} r3 {e['pos']['r3']}" +
          f" | all AUC {e['all']['auc_' + e['all']['score']]:.3f}({e['all']['score']}) {e['all']['auc_ci']} r5 {e['all']['r5']} r3 {e['all']['r3']}", flush=True)
ms = np.array([r['ms']['all'] for r in rows])
parts = collections.Counter()
for r in rows:
    parts.update(r['ms']['parts'])
base = len(sets['pos']) / (len(sets['pos']) + len(PLAIN))
meta = dict(n=len(rows), groups={k: len(v) for k, v in groups.items()}, apart=len(apart), apart_groups=dict(collections.Counter(r['group'] for r in apart)),
            base_pos=base, base_all=len(sets['all']) / (len(sets['all']) + len(PLAIN)),
            ms_median=float(np.median(ms)), ms_p99=float(np.percentile(ms, 99)), ms_max=float(ms.max()), ms_parts={k: round(v / len(rows), 2) for k, v in parts.items()},
            exact_donor=sum(r['exact'] for r in rows) / sum(r['pairs'] * len(next(iter(r['control'].values()))) for r in rows))
print(meta)
json.dump(dict(meta=meta, forms=result), open(OUT, 'w'), indent=0)
