"""A conditional logit over the options of each relation-choice row (relrows.jsonl.zst) with structural features only:
P's log share, kind by atom index, the option's types that are in scope, arity, a relation the clause already read, and
a derived relation's recency. Trained on TRAIN's rows, scored on TEST's in bits per gold pick against P.
python relfit.py TRAIN_RUN TEST_RUN"""
import collections
import math
import re
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler_paths  # noqa: E402,F401
from judge3.framed_jsonl import iter_json  # noqa: E402

B_NAMES = ['b_ready', 'b_boxpos', 'b_follows_crop', 'b_follows_relative', 'b_repeat', 'b_fits_enum', 'b_listed']
USE_B = '--b' in sys.argv
if USE_B:
    sys.argv.remove('--b')
    sys.path += [sampler_paths.STUDY, sampler_paths.STUDY + '/features']
    from r14b import option_features  # noqa: E402
ORIENT = ['axis_of', 'axis_elem', 'dir_elem', 'opposite', 'perp', 'diag_dirs', 'dir8_elem', 'turn']
OTYPES = ['Dir', 'Axis', 'DiagDir', 'Dir8', 'Sense']
C_NAMES = ['c_%s' % r for r in ORIENT] + ['c_%s_%s' % (r, t) for r in ORIENT for t in OTYPES] + ['c_after_orient']
USE_C = '--c' in sys.argv
if USE_C:
    sys.argv.remove('--c')
NAMES = ['logp', 'lib', 'derived', 'op', 'lib_k1', 'derived_k1', 'op_k1', 'in_scope', 'in_scope_frac', 'none_in_scope',
         'arity', 'repeat', 'recency0', 'recency_log', 'no_types']


def b_feats(r, o):
    f = option_features(r, o)
    if f is None:
        return [0.0] * (len(B_NAMES) - 1) + [0.0]
    return [f[n[2:]] for n in B_NAMES[:-1]] + [1.0]


def c_feats(r, o, scope, prev):
    name = o['tok']
    f = [float(name == x) for x in ORIENT]
    f += [float(name == x and t in scope) for x in ORIENT for t in OTYPES]
    f.append(float(name in ORIENT and bool(prev & set(ORIENT))))
    return f


def features(r):
    scope = set(r['scope'])
    prev = set(re.findall(r'\((?:NOT \()?([^\s()]+)', ' '.join(r['prefix'])))
    slots = [int(o['tok'][2:]) for o in r['options'] if o['kind'] == 'derived' and o['tok'][2:].isdigit()]
    top = max(slots) if slots else 0
    X = []
    for o in r['options']:
        ts = o.get('types') or []
        hit = sum(t in scope for t in ts)
        k1 = r['k'] == 1
        rec = top - int(o['tok'][2:]) if o['kind'] == 'derived' and o['tok'][2:].isdigit() else None
        X.append([math.log(max(o['p'], 1e-9)), o['kind'] == 'lib', o['kind'] == 'derived', o['kind'] == 'op',
                  o['kind'] == 'lib' and k1, o['kind'] == 'derived' and k1, o['kind'] == 'op' and k1,
                  hit, hit / len(ts) if ts else 0.0, bool(ts) and hit == 0 and not k1, len(ts),
                  o['tok'] in prev, rec == 0, math.log1p(rec) if rec is not None else 0.0, not ts]
                 + (b_feats(r, o) if USE_B else []) + (c_feats(r, o, scope, prev) if USE_C else []))
    return np.array(X, dtype=float)


def load(run):
    out = []
    for r in iter_json(run + '/relrows.jsonl.zst'):
        toks = [o['tok'] for o in r['options']]
        if r['gold'] not in toks:
            continue
        out.append((features(r), toks.index(r['gold']), r['task']))
    return out


def bits(w, rows):
    tot = 0.0
    for X, g, _ in rows:
        s = X @ w
        s -= s.max()
        tot += -(s[g] - math.log(np.exp(s).sum())) / math.log(2)
    return tot / len(rows)


def fit(rows, steps=300, lr=0.5, l2=1e-3):
    w = np.zeros(len(NAMES))
    w[0] = 1.0  # start at P
    for _ in range(steps):
        grad = l2 * w
        for X, g, _ in rows:
            s = X @ w
            s -= s.max()
            p = np.exp(s)
            p /= p.sum()
            grad -= (X[g] - p @ X) / len(rows)
        w -= lr * grad
    return w


if USE_B:
    NAMES = NAMES + B_NAMES
if USE_C:
    NAMES = NAMES + C_NAMES
train, test = load(sys.argv[1]), load(sys.argv[2])
p_only = np.zeros(len(NAMES))
p_only[0] = 1.0
print('rows: train %d, test %d' % (len(train), len(test)))
print('P alone: train %.2f, test %.2f bits per pick' % (bits(p_only, train), bits(p_only, test)))
w = fit(train)
print('fit:     train %.2f, test %.2f bits per pick' % (bits(w, train), bits(w, test)))
print(' '.join('%s=%.2f' % (n, x) for n, x in zip(NAMES, w)))
by = collections.defaultdict(list)
for row in test:
    by[min(row[0].shape[0], 999) and ('k1' if row[0][row[1], 4] or row[0][row[1], 5] or row[0][row[1], 6] else 'k2+')].append(row)
for k, rows in sorted(by.items()):
    print('  test %s: %d picks, P %.2f, fit %.2f' % (k, len(rows), bits(p_only, rows), bits(w, rows)))
