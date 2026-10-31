"""A conditional logit over the options of each value pick (choices.jsonl.zst rows of phase val or fval) with structural
features: P's log share, the option's kind, a label's recency, whether a label's type is the column's type (the
column's type from the gold relation's types in relrows), and whether the atom already names the label. Trained on
TRAIN, scored on TEST in bits per pick against P. Also prints P's bits per pick for every phase of TEST.
python valfit.py TRAIN_CHOICES_RUN TRAIN_REL_RUN TEST_CHOICES_RUN TEST_REL_RUN"""
import collections
import math
import re
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler_paths  # noqa: E402,F401
from judge3.framed_jsonl import iter_json  # noqa: E402

NAMES = ['logp', 'fresh', 'zero', 'label', 'field', 'newest', 'recency_log', 'type_same', 'type_differs', 'in_atom']


def key(r):
    return (r['task'], r['case'], tuple(r['point']), r['k'])


def rel_types(run):
    out = {}
    for r in iter_json(run + '/relrows.jsonl.zst'):
        g = next((o for o in r['options'] if o['tok'] == r['gold']), None)
        out[key(r)] = (g or {}).get('types')
    return out


def features(r, types):
    m = re.findall(r'\(:(\d+)', r['text'])
    col = int(m[-1]) if m else None
    ctype = types[col] if types and col is not None and col < len(types) else None
    labs = [o for o in r['options'] if o['kind'] == 'label']
    idx = {o['tok']: int(o['tok'][1:]) for o in labs if o['tok'][1:].isdigit()}
    top = max(idx.values()) if idx else 0
    st = r.get('scope_types') or []
    X = []
    for o in r['options']:
        i = idx.get(o['tok'])
        lt = st[i] if i is not None and i < len(st) else None
        X.append([math.log(max(o['p'], 1e-9)), o['kind'] == 'fresh', o['kind'] == 'zero', o['kind'] == 'label',
                  o['kind'] == 'column', i is not None and i == top, math.log1p(top - i) if i is not None else 0.0,
                  lt is not None and ctype is not None and lt == ctype, lt is not None and ctype is not None and lt != ctype,
                  i is not None and re.search(r'\b%s\b' % o['tok'], r['text']) is not None])
    return np.array(X, dtype=float)


def load(run, relrun):
    types = rel_types(relrun)
    out, phase_bits = [], collections.defaultdict(list)
    for r in iter_json(run + '/choices.jsonl.zst'):
        toks = [o['tok'] for o in r['options']]
        if r['gold'] not in toks:
            continue
        g = r['options'][toks.index(r['gold'])]
        phase_bits[r['phase']].append(-math.log2(g['p']) if g['p'] > 0 else float('inf'))
        if r['phase'] in ('val', 'fval') and len(toks) > 1:
            out.append((features(r, types.get(key(r))), toks.index(r['gold'])))
    return out, phase_bits


def bits(w, rows):
    tot = 0.0
    for X, g in rows:
        s = X @ w
        s -= s.max()
        tot += -(s[g] - math.log(np.exp(s).sum())) / math.log(2)
    return tot / len(rows)


def fit(rows, steps=300, lr=0.5, l2=1e-3):
    w = np.zeros(len(NAMES))
    w[0] = 1.0
    for _ in range(steps):
        grad = l2 * w
        for X, g in rows:
            s = X @ w
            s -= s.max()
            p = np.exp(s)
            p /= p.sum()
            grad -= (X[g] - p @ X) / len(rows)
        w -= lr * grad
    return w


train, _ = load(sys.argv[1], sys.argv[2])
test, pb = load(sys.argv[3], sys.argv[4])
for ph, v in sorted(pb.items()):
    fin = [x for x in v if math.isfinite(x)]
    print('test %-9s %5d picks, P %.2f bits per pick (finite), %d with P = 0' % (ph, len(v), sum(fin) / max(1, len(fin)), len(v) - len(fin)))
p_only = np.zeros(len(NAMES))
p_only[0] = 1.0
print('value picks with a choice: train %d, test %d' % (len(train), len(test)))
print('P alone: train %.3f, test %.3f bits per pick' % (bits(p_only, train), bits(p_only, test)))
w = fit(train)
print('fit:     train %.3f, test %.3f bits per pick' % (bits(w, train), bits(w, test)))
print(' '.join('%s=%.2f' % (n, x) for n, x in zip(NAMES, w)))
