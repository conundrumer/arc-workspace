"""A conditional logit over the options of each column pick (choices rows of phase cols: a column of the atom's
relation, or STOP) with structural features: P's log share, the column's position, whether a label in scope has the
column's type, the relation's kind, and the columns the atom names so far. Column types come from the gold relation's
types in relrows. Trained on TRAIN, scored on TEST in bits per pick against P.
python colfit.py TRAIN_CHOICES_RUN TRAIN_REL_RUN TEST_CHOICES_RUN TEST_REL_RUN"""
import math
import re
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler_paths  # noqa: E402,F401
from judge3.framed_jsonl import iter_json  # noqa: E402

NAMES = ['logp', 'stop', 'col0', 'pos_log', 'type_in_scope', 'type_count_log', 'type_unknown', 'derived', 'input', 'k1',
         'stop_named', 'stop_named0', 'stop_left_in_scope', 'stop_derived', 'stop_k1', 'back', 'after_gap']


def key(r):
    return (r['task'], r['case'], tuple(r['point']), r['k'])


def rel_types(run):
    out = {}
    for r in iter_json(run + '/relrows.jsonl.zst'):
        g = next((o for o in r['options'] if o['tok'] == r['gold']), None)
        out[key(r)] = (g or {}).get('types')
    return out


def features(r, types):
    named = [int(x) for x in re.findall(r'\(:(\d+)', r['text'])]
    last = named[-1] if named else -1
    st = r.get('scope_types') or []
    derived, inp = r['rtok'].startswith('&r'), r['rtok'] == 'input'
    cols = [int(o['tok'][1:]) for o in r['options'] if o['kind'] == 'column']
    left = sum(1 for c in cols if types and c < len(types) and types[c] in st)
    X = []
    for o in r['options']:
        if o['kind'] == 'column':
            c = int(o['tok'][1:])
            t = types[c] if types and c < len(types) else None
            n = st.count(t) if t else 0
            X.append([math.log(max(o['p'], 1e-9)), 0, c == 0, math.log1p(c), n > 0, math.log1p(n), t is None, derived, inp,
                      r['k'] == 1, 0, 0, 0, 0, 0, c < last, c > last + 1])
        else:
            X.append([math.log(max(o['p'], 1e-9)), 1, 0, 0, 0, 0, 0, 0, 0, 0, math.log1p(len(named)), not named, left > 0,
                      derived, r['k'] == 1, 0, 0])
    return np.array(X, dtype=float)


def load(run, relrun):
    types = rel_types(relrun)
    out = []
    for r in iter_json(run + '/choices.jsonl.zst'):
        toks = [o['tok'] for o in r['options']]
        if r['phase'] != 'cols' or r['gold'] not in toks or len(toks) < 2:
            continue
        out.append((features(r, types.get(key(r))), toks.index(r['gold']), r['gold'] == 'STOP'))
    return out


def bits(w, rows):
    tot = 0.0
    for X, g, _ in rows:
        s = X @ w
        s -= s.max()
        tot += -(s[g] - math.log(np.exp(s).sum())) / math.log(2)
    return tot / max(len(rows), 1)


def fit(rows, steps=300, lr=0.5, l2=1e-3):
    w = np.zeros(len(NAMES))
    w[0] = 1.0
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


if __name__ == '__main__':
    train, test = load(sys.argv[1], sys.argv[2]), load(sys.argv[3], sys.argv[4])
    p_only = np.zeros(len(NAMES))
    p_only[0] = 1.0
    print('rows: train %d, test %d' % (len(train), len(test)))
    print('P alone: train %.3f, test %.3f bits per pick' % (bits(p_only, train), bits(p_only, test)))
    w = fit(train)
    print('fit:     train %.3f, test %.3f bits per pick' % (bits(w, train), bits(w, test)))
    print(' '.join('%s=%.2f' % (n, x) for n, x in zip(NAMES, w)))
    for lab, sel in (('gold column', False), ('gold STOP', True)):
        rows = [x for x in test if x[2] == sel]
        print('  test %s: %d picks, P %.3f, fit %.3f' % (lab, len(rows), bits(p_only, rows), bits(w, rows)))
